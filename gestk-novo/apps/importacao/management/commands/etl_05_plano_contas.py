from django.db import transaction
from ._base import BaseETLCommand
from apps.core.models import Contabilidade
from apps.contabil.models import PlanoContas
import re
from itertools import islice
import sys

def batch_iterator(iterator, batch_size):
    """Itera sobre os dados em lotes de tamanho 'batch_size'."""
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            break
        yield batch

class Command(BaseETLCommand):
    help = 'ETL COMPLETO para carregar TODAS as contas do Plano de Contas, incluindo contas sem classificação.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('--- INICIANDO ETL COMPLETO DO PLANO DE CONTAS ---'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        self.stdout.write(self.style.WARNING("\n[1/5] Verificando dados existentes do Plano de Contas..."))
        contas_existentes = PlanoContas.objects.count()
        self.stdout.write(self.style.SUCCESS(f"✓ Contas existentes no banco: {contas_existentes:,}"))

        # Construir mapa histórico de contabilidades
        self.stdout.write(self.style.WARNING("\n[2/5] Construindo mapa histórico de contabilidades..."))
        historical_map = self.build_historical_contabilidade_map()

        connection = self.get_sybase_connection()
        if not connection: return

        self.stdout.write(self.style.WARNING("\n[3/5] Contando registros no Sybase..."))
        count_query = """
        SELECT COUNT(*) as total 
        FROM BETHADBA.CTCONTAS ct
        INNER JOIN BETHADBA.GEEMPRE ge ON ct.codi_emp = ge.codi_emp
        WHERE ge.cgce_emp IS NOT NULL AND ge.cgce_emp <> ''
        """
        result = self.execute_query(connection, count_query)
        total_registros = result[0]['total'] if result else 0
        self.stdout.write(self.style.SUCCESS(f"✓ Total de registros a processar: {total_registros:,}"))

        # Query modificada para incluir CNPJ/CPF e seguir a Regra de Ouro
        # TESTE: Limitando a 100 registros para verificação
        query = """
        SELECT TOP 100
            ct.codi_cta,
            ct.clas_cta,
            ct.nome_cta,
            ct.tipo_cta,
            ct.codi_emp,
            ge.cgce_emp
        FROM
            BETHADBA.CTCONTAS AS ct
        INNER JOIN BETHADBA.GEEMPRE ge ON ct.codi_emp = ge.codi_emp
        WHERE ge.cgce_emp IS NOT NULL AND ge.cgce_emp <> ''
        ORDER BY
            ct.codi_emp, ct.codi_cta
        """

        self.stdout.write(self.style.WARNING("\n[4/5] Iniciando importação das contas..."))
        cursor = connection.cursor()
        cursor.execute(query)
        data_iterator = iter(lambda: cursor.fetchone(), None)

        total_criados = 0
        total_atualizados = 0
        total_processados = 0
        total_sem_contabilidade = 0
        BATCH_SIZE = 1000
        contas_por_empresa = {}  # Para contar contas por empresa

        self.stdout.write("\nProcessando lotes:")
        self.stdout.write("-" * 70)
        
        for batch in batch_iterator(data_iterator, BATCH_SIZE):
            contas_para_criar = []
            
            for row in batch:
                total_processados += 1
                item = {
                    'codi_emp': row[4],
                    'codi_cta': row[0],
                    'clas_cta': row[1],
                    'nome_cta': row[2],
                    'tipo_cta': row[3],
                    'cgce_emp': row[5]
                }
                
                # Usar codi_cta como código se não houver classificação
                classificacao = str(item.get('clas_cta') or '').strip()
                if not classificacao or classificacao == '0':
                    classificacao = str(item.get('codi_cta', '')).strip()
                
                if not classificacao:
                    continue

                # Contar contas por empresa
                codi_emp = item.get('codi_emp')
                if codi_emp not in contas_por_empresa:
                    contas_por_empresa[codi_emp] = 0
                contas_por_empresa[codi_emp] += 1

                # Aplicar a Regra de Ouro: identificar contabilidade pelo CNPJ/CPF
                documento_limpo = self.limpar_documento(item.get('cgce_emp'))
                if not documento_limpo:
                    total_sem_contabilidade += 1
                    continue

                # Buscar contabilidade no mapa histórico
                contratos_empresa = historical_map.get(documento_limpo)
                if not contratos_empresa:
                    total_sem_contabilidade += 1
                    continue

                # Para cada período de contrato, criar a conta
                for data_inicio, data_termino, contabilidade in contratos_empresa:
                    tipo_conta = (str(item.get('tipo_cta') or 'A')).strip().upper()
                    nome_conta = str(item.get('nome_cta') or f'Conta {classificacao}').strip()
                    
                    # Determinar natureza baseada no nome ou código
                    natureza = "DEVEDORA"  # Padrão
                    nome_upper = nome_conta.upper()
                    if any(palavra in nome_upper for palavra in ['RECEITA', 'VENDA', 'FATURAMENTO', 'PASSIVO', 'CAPITAL']):
                        natureza = "CREDORA"
                    elif classificacao.startswith('2') or classificacao.startswith('3') or classificacao.startswith('4'):
                        natureza = "CREDORA"
                    
                    conta, created = PlanoContas.objects.update_or_create(
                        contabilidade=contabilidade,
                        codigo=classificacao,
                        defaults={
                            'id_legado': str(item.get('codi_cta')),
                            'nome': nome_conta,
                            'tipo_conta': tipo_conta,
                            'natureza': natureza,
                            'nivel': len(classificacao.split('.')),
                            'aceita_lancamento': (tipo_conta == 'A')
                        }
                    )
                    
                    if created:
                        total_criados += 1
                    else:
                        total_atualizados += 1
                
            # Mostrar progresso do lote
            percentual = (total_processados / total_registros * 100) if total_registros > 0 else 0
            self.stdout.write(
                f"Lote processado | "
                f"Processados: {total_processados:7,}/{total_registros:,} ({percentual:5.1f}%) | "
                f"Contas criadas: {total_criados:8,} | "
                f"Sem contabilidade: {total_sem_contabilidade:8,}"
            )
            
            # Mostrar barra de progresso simples
            if total_processados % 5000 == 0:
                barra_tamanho = 50
                barra_preenchida = int(barra_tamanho * percentual / 100)
                barra = '█' * barra_preenchida + '░' * (barra_tamanho - barra_preenchida)
                self.stdout.write(f"[{barra}] {percentual:.1f}%")
                self.stdout.write("-" * 70)

        connection.close()
        
        self.stdout.write("-" * 70)
        self.stdout.write(self.style.SUCCESS(f"\n✓ Importação concluída. {total_criados:,} contas criadas, {total_atualizados:,} contas atualizadas."))
        self.stdout.write(self.style.WARNING(f"⚠ {total_sem_contabilidade:,} registros sem contabilidade identificada."))
        
        # Mostrar estatísticas por empresa
        self.stdout.write("\nTop 10 empresas com mais contas no Sybase:")
        for emp, count in sorted(contas_por_empresa.items(), key=lambda x: x[1], reverse=True)[:10]:
            self.stdout.write(f"  Empresa {emp}: {count:,} contas")

        # Segunda passada: Vincular contas-pai
        self.stdout.write(self.style.WARNING("\n[5/5] Vinculando contas-pai (hierarquia)..."))
        try:
            with transaction.atomic():
                mapa_contas = {
                    (conta.contabilidade_id, conta.codigo): conta.id 
                    for conta in PlanoContas.objects.all()
                }
                
                self.stdout.write(f"Mapa de contas carregado: {len(mapa_contas):,} entradas")
                
                contas_atualizadas = 0
                contas_total = PlanoContas.objects.count()
                contas_processadas = 0
                
                for conta in PlanoContas.objects.select_related('contabilidade').iterator():
                    contas_processadas += 1
                    
                    # Tentar extrair hierarquia da classificação
                    partes = re.split(r'[.\s]', conta.codigo)
                    partes_pai = [p for p in partes if p]
                    
                    if len(partes_pai) > 1:
                        # Tentar várias formas de encontrar o pai
                        for i in range(len(partes_pai)-1, 0, -1):
                            classificacao_pai = '.'.join(partes_pai[:i])
                            id_pai = mapa_contas.get((conta.contabilidade_id, classificacao_pai))
                            
                            if id_pai and conta.conta_pai_id != id_pai:
                                conta.conta_pai_id = id_pai
                                conta.save(update_fields=['conta_pai_id'])
                                contas_atualizadas += 1
                                break
                    
                    # Mostrar progresso a cada 10000 contas
                    if contas_processadas % 10000 == 0:
                        percentual = (contas_processadas / contas_total * 100) if contas_total > 0 else 0
                        self.stdout.write(f"Processadas: {contas_processadas:,}/{contas_total:,} ({percentual:.1f}%) | Vínculos criados: {contas_atualizadas:,}")
                
                self.stdout.write(self.style.SUCCESS(f"\n✓ Vinculação concluída. {contas_atualizadas:,} contas vinculadas a suas contas-pai."))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Erro ao vincular contas-pai: {e}"))
            
        # Estatísticas finais
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('--- ESTATÍSTICAS FINAIS ---'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        total_contas = PlanoContas.objects.count()
        total_contabilidades = Contabilidade.objects.count()
        contas_com_pai = PlanoContas.objects.exclude(conta_pai__isnull=True).count()
        contas_analiticas = PlanoContas.objects.filter(tipo_conta='A').count()
        contas_sinteticas = PlanoContas.objects.filter(tipo_conta='S').count()
        
        self.stdout.write(f'✓ Total de contas criadas: {total_contas:,}')
        self.stdout.write(f'✓ Total de contabilidades: {total_contabilidades:,}')
        self.stdout.write(f'✓ Média de contas por contabilidade: {total_contas // total_contabilidades if total_contabilidades > 0 else 0:,}')
        self.stdout.write(f'✓ Contas com hierarquia (pai): {contas_com_pai:,}')
        self.stdout.write(f'✓ Contas analíticas: {contas_analiticas:,}')
        self.stdout.write(f'✓ Contas sintéticas: {contas_sinteticas:,}')
        
        # Mostrar algumas contas como exemplo
        self.stdout.write('\nExemplos de contas importadas:')
        contas_exemplo = PlanoContas.objects.order_by('?')[:5]  # 5 contas aleatórias
        for conta in contas_exemplo:
            pai_nome = conta.conta_pai.nome if conta.conta_pai else 'Sem pai'
            self.stdout.write(f'  - [{conta.codigo}] {conta.nome} (Tipo: {conta.tipo_conta}, Pai: {pai_nome})')
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('--- ETL COMPLETO DO PLANO DE CONTAS FINALIZADO COM SUCESSO! ---'))
        self.stdout.write(self.style.SUCCESS('=' * 70))