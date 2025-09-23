from django.db import transaction
from tqdm import tqdm
from ._base import BaseETLCommand
from funcionarios.models import Rescisao, Rubrica, RescisaoRubrica
from decimal import Decimal

class Command(BaseETLCommand):
    help = 'ETL para importar Rubricas de Rescisão seguindo a Regra de Ouro'

    def add_arguments(self, parser):
        parser.add_argument(
            '--teste',
            action='store_true',
            help='Executa apenas um teste com 10 rescisões'
        )

    def handle(self, *args, **options):
        modo_teste = options['teste']
        
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL de Rubricas de Rescisão ---'))
        if modo_teste:
            self.stdout.write(self.style.WARNING('🧪 MODO TESTE ATIVADO - Apenas 10 rescisões'))
        self.stdout.flush()
        
        connection = self.get_sybase_connection()
        if not connection: return

        try:
            self.stdout.write(self.style.HTTP_INFO('\n[1/4] Construindo mapas de referência...'))
            self.stdout.flush()
            rescisoes_map = self.build_rescisoes_map()
            rubricas_map = self.build_rubricas_map()
            self.stdout.write(self.style.SUCCESS("✓ Mapas construídos."))
            self.stdout.flush()

            self.stdout.write(self.style.HTTP_INFO('\n[2/4] Extraindo rubricas das rescisões...'))
            self.stdout.flush()
            rubricas_data = self.extract_rubricas_corretas(connection, modo_teste)
            if not rubricas_data:
                self.stdout.write(self.style.WARNING('Nenhuma rubrica de rescisão encontrada.'))
                self.stdout.flush()
                return
            self.stdout.write(self.style.SUCCESS(f"✓ {len(rubricas_data):,} registros de rubricas extraídos."))
            self.stdout.flush()
            
            self.stdout.write(self.style.HTTP_INFO('\n[3/4] Processando e carregando dados...'))
            self.stdout.flush()
            stats = self.processar_dados_corretos(rubricas_data, rescisoes_map, rubricas_map)

        finally:
            connection.close()
        
        self.stdout.write(self.style.SUCCESS('\n--- Resumo do ETL ---'))
        self.stdout.write(f"  - Rubricas Criadas: {stats['criados']}")
        self.stdout.write(f"  - Rubricas Atualizadas: {stats['atualizados']}")
        self.stdout.write(f"  - Sem Contabilidade: {stats['sem_contabilidade']}")
        self.stdout.write(f"  - Sem Rescisão: {stats['sem_rescisao']}")
        self.stdout.write(f"  - Sem Rubrica: {stats['sem_rubrica']}")
        self.stdout.write(f"  - Erros: {stats['erros']}")
        self.stdout.write(self.style.SUCCESS('--- ETL Finalizado ---'))
        self.stdout.flush()

    def build_rescisoes_map(self):
        self.stdout.write("  - Carregando mapa de rescisões...", ending='\r')
        self.stdout.flush()
        rescisoes_map = {r.id_legado: r for r in Rescisao.objects.all()}
        self.stdout.write(self.style.SUCCESS(f"  - Mapa de rescisões: {len(rescisoes_map)} registros"))
        self.stdout.flush()
        return rescisoes_map

    def build_rubricas_map(self):
        self.stdout.write("  - Carregando mapa de rubricas...", ending='\r')
        self.stdout.flush()
        rubricas_map = {}
        for r in Rubrica.objects.select_related('contabilidade'):
            rubricas_map[(r.contabilidade.id, r.id_legado)] = r
        self.stdout.write(self.style.SUCCESS(f"  - Mapa de rubricas: {len(rubricas_map)} registros"))
        self.stdout.flush()
        return rubricas_map

    def extract_rubricas_corretas(self, connection, modo_teste):
        """
        Query CORRETA seguindo a Regra de Ouro:
        
        ESTRATÉGIA:
        1. Usar FORESCISOES como base (rescisões específicas)
        2. JOIN com GEEMPRE para obter cgce_emp (CNPJ/CPF)
        3. JOIN com FOMOVTOSERV para pegar movimentos financeiros
        4. JOIN com FOEVENTOS para pegar tipos de rubricas
        5. Filtrar apenas movimentos de rescisão (TIPO_PROCES = 11)
        6. Criar ID_LEGADO composto: codi_emp-i_empregados
        """
        limit_clause = "TOP 10" if modo_teste else "TOP 1000"
        
        query = f"""
        SELECT {limit_clause}
            fs.i_calculos,
            m.i_eventos,
            e.nome as descricao_rubrica,
            e.prov_desc as tipo_rubrica,
            SUM(m.valor_cal) as valor_total,
            fs.codi_emp,
            fs.i_empregados,
            fs.demissao,
            ge.cgce_emp,
            -- Criar ID_LEGADO composto para correspondência
            CAST(fs.codi_emp AS VARCHAR) + '-' + CAST(fs.i_empregados AS VARCHAR) as id_legado_composto
        FROM bethadba.FORESCISOES fs
        INNER JOIN bethadba.GEEMPRE ge ON ge.codi_emp = fs.codi_emp
        INNER JOIN bethadba.FOMOVTOSERV m ON 
            m.codi_emp = fs.codi_emp AND 
            m.i_empregados = fs.i_empregados AND
            m.i_calculos = fs.i_calculos AND
            m.TIPO_PROCES = 11
        INNER JOIN bethadba.FOEVENTOS e ON m.i_eventos = e.i_eventos
        WHERE fs.demissao >= '2019-01-01'
            AND m.valor_cal != 0
        GROUP BY fs.i_calculos, m.i_eventos, e.nome, e.prov_desc, 
                 fs.codi_emp, fs.i_empregados, fs.demissao, ge.cgce_emp
        HAVING SUM(m.valor_cal) != 0
        ORDER BY fs.i_calculos, m.i_eventos
        """
        return self.execute_query(connection, query)

    def processar_dados_corretos(self, data, rescisoes_map, rubricas_map):
        """Processamento CORRETO seguindo a Regra de Ouro: CNPJ/CPF + contabilidade_id."""
        stats = {
            'criados': 0,
            'atualizados': 0,
            'erros': 0,
            'sem_rescisao': 0,
            'sem_rubrica': 0,
            'sem_contabilidade': 0
        }
        
        # Controle de duplicatas por rescisão usando CNPJ/CPF + contabilidade_id
        rubricas_processadas = set()
        
        for row in tqdm(data, desc="Processando Rubricas"):
            try:
                # 1. Obter cgce_emp (CNPJ/CPF) da query
                cgce_emp = row['cgce_emp']
                if not cgce_emp:
                    stats['sem_contabilidade'] += 1
                    continue
                
                # 2. Limpar documento
                documento_limpo = self.limpar_documento(cgce_emp)
                if not documento_limpo:
                    stats['sem_contabilidade'] += 1
                    continue
                
                # 3. Buscar Contabilidade usando a Regra de Ouro
                # Primeiro, buscar o CODI_EMP no Sybase para obter o CNPJ/CPF
                codi_emp = row['codi_emp']
                event_date = row['demissao']
                
                # Usar o método da classe base que já implementa a Regra de Ouro
                historical_map = self.build_historical_contabilidade_map()
                contabilidade = self.get_contabilidade_for_date(historical_map, codi_emp, event_date)
                
                if not contabilidade:
                    stats['sem_contabilidade'] += 1
                    continue
                
                # 4. Buscar rescisão usando CNPJ/CPF + contabilidade_id (NÃO id_legado)
                rescisao = None
                for r in rescisoes_map.values():
                    if (r.contabilidade_id == contabilidade.id and 
                        r.vinculo and r.vinculo.empresa):
                        # Verificar se o CNPJ/CPF da empresa bate
                        empresa_doc = None
                        if hasattr(r.vinculo.empresa, 'cnpj') and r.vinculo.empresa.cnpj:
                            empresa_doc = self.limpar_documento(r.vinculo.empresa.cnpj)
                        elif hasattr(r.vinculo.empresa, 'cpf') and r.vinculo.empresa.cpf:
                            empresa_doc = self.limpar_documento(r.vinculo.empresa.cpf)
                        
                        if empresa_doc == documento_limpo:
                            rescisao = r
                            break
                
                if not rescisao:
                    stats['sem_rescisao'] += 1
                    continue
                
                # 5. Verificar duplicata usando CNPJ/CPF + contabilidade_id + i_eventos
                chave_rubrica = f"{documento_limpo}_{contabilidade.id}_{row['i_eventos']}_{row['tipo_rubrica']}"
                if chave_rubrica in rubricas_processadas:
                    continue
                
                rubricas_processadas.add(chave_rubrica)
                
                # 6. Buscar rubrica correspondente
                id_legado_rubrica = str(row['i_eventos'])
                rubrica_key = (contabilidade.id, id_legado_rubrica)
                rubrica = rubricas_map.get(rubrica_key)
                if not rubrica:
                    stats['sem_rubrica'] += 1
                    continue
                
                # 7. Validar valor
                try:
                    valor = Decimal(str(row['valor_total'] or 0))
                    if valor <= 0:
                        continue
                except (ValueError, TypeError):
                    stats['erros'] += 1
                    continue
                
                # 8. Criar/atualizar RescisaoRubrica usando CNPJ/CPF + contabilidade_id
                with transaction.atomic():
                    rr, created = RescisaoRubrica.objects.update_or_create(
                        rescisao=rescisao,
                        rubrica=rubrica,
                        tipo=row['tipo_rubrica'],
                        descricao=row['descricao_rubrica'],
                        defaults={'valor': valor}
                    )

                    if created:
                        stats['criados'] += 1
                    else:
                        stats['atualizados'] += 1
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao processar rubrica: {e}"))
                stats['erros'] += 1
        
        return stats
