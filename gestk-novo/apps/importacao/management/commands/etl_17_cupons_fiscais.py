from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from tqdm import tqdm
from datetime import datetime
from apps.importacao.management.commands._base import BaseETLCommand
from apps.pessoas.models import PessoaFisica, PessoaJuridica
from apps.fiscal.models import NotaFiscal, NotaFiscalItem


class Command(BaseETLCommand):
    help = 'ETL 17: Importação de Cupons Fiscais (CFE e ECF)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== ETL 17: CUPONS FISCAIS ==='))
        
        # Construir mapa histórico de contabilidades
        self.stdout.write("\n[1/5] Construindo mapa histórico de contabilidades...")
        historical_map = self.build_historical_contabilidade_map()
        
        # Conectar ao Sybase
        connection = self.get_sybase_connection()
        if not connection:
            return

        # Query com TODOS os dados necessários (cupons + itens)
        query_completa = """
        SELECT         
            emp.nome_emp,  
            emp.cgce_emp,
            ef.codi_emp, 
            ef.I_CFE,
            ef.chave_cfe,
            pd.codi_pdi,
            pd.desc_pdi,
            pd.cncm_pdi,
            efe.quantidade,
            efe.valor_unitario,
            efe.VALOR_PRODUTO,
            ef.DATA_CFE
        FROM BETHADBA.EFCUPOM_FISCAL_ELETRONICO ef
        INNER JOIN BETHADBA.GEEMPRE emp ON emp.codi_emp = ef.codi_emp
        INNER JOIN BETHADBA.EFCUPOM_FISCAL_ELETRONICO_ESTOQUE efe ON efe.codi_emp = ef.codi_emp AND efe.I_CFE = ef.I_CFE
        INNER JOIN BETHADBA.EFPRODUTOS pd ON pd.codi_emp = efe.codi_emp AND pd.codi_pdi = efe.codi_pdi
        WHERE ef.chave_cfe IS NOT NULL AND ef.chave_cfe != '' 
            AND ef.DATA_CFE >= '2019-01-01'
        ORDER BY ef.codi_emp, ef.I_CFE, efe.codi_pdi
        """

        self.stdout.write("Executando query de cupons fiscais...")
        cursor = connection.cursor()
        
        # Configurações de importação
        BATCH_SIZE = 1000  # Cupons por bloco
        MAX_CUPONS = 10000  # Limite para teste (10 mil cupons)
        
        # ABORDAGEM ULTRA OTIMIZADA - Cupons únicos primeiro
        self.stdout.write("Executando query otimizada de cupons únicos...")
        
        # PASSO 1: Buscar apenas cupons únicos (sem itens)
        query_cupons = f"""
        SELECT TOP {MAX_CUPONS}
            emp.nome_emp,  
            emp.cgce_emp,
            ef.codi_emp, 
            ef.I_CFE,
            ef.chave_cfe,
            ef.DATA_CFE
        FROM BETHADBA.EFCUPOM_FISCAL_ELETRONICO ef
        INNER JOIN BETHADBA.GEEMPRE emp ON emp.codi_emp = ef.codi_emp
        WHERE ef.chave_cfe IS NOT NULL AND ef.chave_cfe != '' 
            AND ef.DATA_CFE >= '2019-01-01'
        ORDER BY ef.codi_emp, ef.I_CFE
        """
        
        self.stdout.write(f"[2/5] Processando {MAX_CUPONS:,} cupons únicos...")
        
        cursor.execute(query_cupons)
        data_cupons = cursor.fetchall()
        
        if not data_cupons:
            self.stdout.write("Nenhum cupom encontrado. Finalizando...")
            return
        
        # Mapear colunas dos cupons
        columns_cupons = [column[0] for column in cursor.description]
        cupons_dict = [dict(zip(columns_cupons, row)) for row in data_cupons]
        
        self.stdout.write(f"[3/5] Processando {len(cupons_dict):,} cupons únicos...")
        
        # Estatísticas
        total_notas_criadas = 0
        total_notas_atualizadas = 0
        total_itens_criados = 0
        total_sem_contabilidade = 0
        total_erros = 0

        # Criar pessoa genérica UMA VEZ (otimização)
        pessoa, created = PessoaFisica.objects.get_or_create(
            cpf='00000000000',
            defaults={'nome': 'CLIENTE CUPOM FISCAL'}
        )

        # Processar cada cupom (SEM itens por enquanto - apenas notas)
        for cupom_data in tqdm(cupons_dict, desc="Processando cupons"):
            try:
                # Aplicar Regra de Ouro: identificar contabilidade pelo CNPJ da empresa emitente
                cgce_empresa = cupom_data['cgce_emp']
                documento_limpo = self.limpar_documento(cgce_empresa)
                
                if not documento_limpo:
                    total_sem_contabilidade += 1
                    continue
                
                # Buscar contabilidade no mapa histórico
                contratos_empresa = historical_map.get(documento_limpo)
                if not contratos_empresa:
                    total_sem_contabilidade += 1
                    continue
                
                # Encontrar a contabilidade correta para a data do cupom
                data_cupom = cupom_data['DATA_CFE']
                if not data_cupom:
                    total_sem_contabilidade += 1
                    continue
                
                # Buscar contabilidade diretamente no mapa
                contabilidade = None
                for data_inicio, data_termino, contab in contratos_empresa:
                    if data_inicio and data_termino and data_inicio <= data_cupom <= data_termino:
                        contabilidade = contab
                        break
                
                if not contabilidade:
                    total_sem_contabilidade += 1
                    continue
                
                # Buscar itens do cupom
                query_itens = f"""
                SELECT 
                    pd.codi_pdi,
                    pd.desc_pdi,
                    pd.cncm_pdi,
                    efe.quantidade,
                    efe.valor_unitario,
                    efe.VALOR_PRODUTO
                FROM BETHADBA.EFCUPOM_FISCAL_ELETRONICO_ESTOQUE efe
                INNER JOIN BETHADBA.EFPRODUTOS pd ON pd.codi_emp = efe.codi_emp AND pd.codi_pdi = efe.codi_pdi
                WHERE efe.codi_emp = {cupom_data['codi_emp']} AND efe.I_CFE = {cupom_data['I_CFE']}
                ORDER BY efe.codi_pdi
                """
                
                cursor.execute(query_itens)
                itens_data = cursor.fetchall()
                
                # Calcular valor total do cupom
                valor_total_cupom = Decimal('0.00')
                for item_row in itens_data:
                    valor_item = Decimal(str(item_row[5] or 0))  # VALOR_PRODUTO
                    valor_total_cupom += valor_item
                
                # Criar NotaFiscal com valor total calculado
                with transaction.atomic():
                    nota_fiscal, created = NotaFiscal.objects.update_or_create(
                        contabilidade=contabilidade,
                        chave_acesso=cupom_data['chave_cfe'],
                        defaults={
                            'numero_documento': str(cupom_data['I_CFE']),
                            'serie': 'CFE',
                            'data_emissao': cupom_data['DATA_CFE'],
                            'data_entrada_saida': cupom_data['DATA_CFE'],
                            'situacao': 'AUTORIZADA',
                            'tipo_nota': 'SAIDA',
                            'valor_total': valor_total_cupom,
                            'parceiro_pf': pessoa,
                            'id_legado_nota': f"{cupom_data['codi_emp']}-{cupom_data['I_CFE']}",
                            'id_legado_empresa': str(cupom_data['codi_emp']),
                            'id_legado_cli_for': str(cupom_data['I_CFE']),
                        }
                    )
                    
                    if created:
                        total_notas_criadas += 1
                    else:
                        total_notas_atualizadas += 1
                    
                    # Limpar itens existentes para reprocessar
                    NotaFiscalItem.objects.filter(nota_fiscal=nota_fiscal).delete()
                    
                    # Criar itens do cupom
                    for i, item_row in enumerate(itens_data, 1):
                        NotaFiscalItem.objects.create(
                            nota_fiscal=nota_fiscal,
                            sequencial_item=i,
                            tipo_item='PRODUTO',
                            descricao=item_row[1] or '',  # desc_pdi
                            cfop='5102',
                            ncm=str(item_row[2] or ''),  # cncm_pdi
                            quantidade=Decimal(str(item_row[3] or 0)),  # quantidade
                            valor_unitario=Decimal(str(item_row[4] or 0)),  # valor_unitario
                            valor_total=Decimal(str(item_row[5] or 0)),  # VALOR_PRODUTO
                        )
                        total_itens_criados += 1
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao processar cupom {cupom_data.get('chave_cfe', 'N/A')}: {e}"))
                total_erros += 1
                continue
        
        # Fechar conexão
        connection.close()
        
        # Resumo final
        self.stdout.write(self.style.SUCCESS(f"\n[4/5] RESUMO FINAL:"))
        self.stdout.write(f"  ✓ Cupons processados: {len(cupons_dict):,}")
        self.stdout.write(f"  ✓ Notas fiscais criadas: {total_notas_criadas:,}")
        self.stdout.write(f"  ✓ Notas fiscais atualizadas: {total_notas_atualizadas:,}")
        self.stdout.write(f"  ✓ Itens criados: {total_itens_criados:,}")
        self.stdout.write(f"  ✗ Sem contabilidade: {total_sem_contabilidade:,}")
        self.stdout.write(f"  ✗ Erros: {total_erros:,}")
        
        self.stdout.write(self.style.SUCCESS("\n=== ETL 17 CONCLUÍDA (COMPLETA) ==="))