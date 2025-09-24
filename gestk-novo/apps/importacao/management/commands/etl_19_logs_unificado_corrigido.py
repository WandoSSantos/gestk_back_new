"""
ETL 19 - Logs Unificados (Atividades, Importações e Lançamentos) - NORMALIZADO

Importa dados de logs do sistema legado com identificação por CNPJ:
- GELOGUSER → LogAtividade (atividades dos usuários)
- EFSAIDAS, EFENTRADAS, EFSERVICOS → LogImportacao (importações)
- CTLANCTO → LogLancamento (lançamentos contábeis)
- Estatisticas consolidadas → EstatisticaUsuario

Estratégia NORMALIZADA:
- Relacionamentos adequados (Usuario, PessoaJuridica)
- Identificação por CNPJ (não ID legado)
- Regra de ouro para mapeamento multitenant
- Processamento em lotes para performance
- Idempotência para execução múltipla
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import datetime, date, timedelta
from decimal import Decimal
import time
import hashlib

from importacao.management.commands._base import BaseETLCommand
from administracao.models import Usuario, UsuarioContabilidade
from pessoas.models import PessoaJuridica


class Command(BaseETLCommand):
    help = 'ETL 19 - Importa logs unificados NORMALIZADOS (atividades, importações, lançamentos) com identificação por CNPJ'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executar sem salvar dados no banco',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limitar número de registros para processar (padrão: sem limite)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Tamanho do lote para processamento (padrão: 1000)',
        )
        parser.add_argument(
            '--tipo',
            choices=['atividades', 'importacoes', 'lancamentos', 'todos'],
            default='todos',
            help='Tipo de dados para importar (padrão: todos)',
        )
        parser.add_argument(
            '--data-inicio',
            type=str,
            default='2019-01-01',
            help='Data de início para importação (formato: YYYY-MM-DD)',
        )
        parser.add_argument(
            '--data-fim',
            type=str,
            default=None,
            help='Data de fim para importação (formato: YYYY-MM-DD)',
        )
        parser.add_argument(
            '--progress-interval',
            type=int,
            default=100,
            help='Intervalo para exibir progresso no terminal (padrão: 100)',
        )

    def handle(self, *args, **options):
        """Ponto de entrada principal do ETL 19 unificado NORMALIZADO"""
        self.dry_run = options['dry_run']
        self.limit = options['limit']
        self.batch_size = options['batch_size']
        self.tipo = options['tipo']
        self.data_inicio = options['data_inicio']
        self.data_fim = options['data_fim'] or datetime.now().strftime('%Y-%m-%d')
        self.progress_interval = options['progress_interval']
        
        # Inicializar estatísticas
        self.stats = {
            'atividades_processadas': 0,
            'atividades_criadas': 0,
            'importacoes_processadas': 0,
            'importacoes_criadas': 0,
            'lancamentos_processados': 0,
            'lancamentos_criados': 0,
            'estatisticas_criadas': 0,
            'erros': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'sybase_queries': 0,
            'contabilidade_found': 0,
            'contabilidade_not_found': 0,
            'tempo_inicio': time.time(),
            'tempo_fim': 0,
        }

        if self.dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhum dado será salvo no banco'))
        
        self.stdout.write(self.style.SUCCESS('=== ETL 19 - LOGS UNIFICADOS NORMALIZADOS (IDENTIFICAÇÃO POR CNPJ) ==='))
        self.stdout.write(f'Período: {self.data_inicio} a {self.data_fim}')
        self.stdout.write(f'Tipo: {self.tipo}')
        
        try:
            # 1. Construir mapa histórico de contabilidades
            self.stdout.write('\n[1] Construindo mapa histórico de contabilidades...')
            historical_map = self.build_historical_contabilidade_map_cached()

            # 2. Conectar ao Sybase
            connection = self.get_sybase_connection()
            if not connection:
                return

            # 3. Processar cada tipo de dados
            if self.tipo in ['atividades', 'todos']:
                self.stdout.write('\n[2] Processando logs de atividades (GELOGUSER)...')
                self.processar_atividades(connection, historical_map)

            if self.tipo in ['importacoes', 'todos']:
                self.stdout.write('\n[3] Processando logs de importações (EFSAIDAS, EFENTRADAS, EFSERVICOS)...')
                self.processar_importacoes(connection, historical_map)

            if self.tipo in ['lancamentos', 'todos']:
                self.stdout.write('\n[4] Processando logs de lançamentos (CTLANCTO)...')
                self.processar_lancamentos(connection, historical_map)

            # 5. Gerar estatísticas consolidadas
            if self.tipo == 'todos':
                self.stdout.write('\n[5] Gerando estatísticas consolidadas...')
                self.gerar_estatisticas_consolidadas()

            # 6. Relatório final
            self.stdout.write('\n[6] Relatório final...')
            self.gerar_relatorio_final()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro durante execução: {e}'))
            raise
        finally:
            self.close_sybase_connection()

    def processar_atividades(self, connection, historical_map):
        """Processa logs de atividades do GELOGUSER"""
        query = f"""
        SELECT 
            gl.usua_log,
            gl.data_log,
            gl.tini_log,
            gl.tfim_log,
            gl.dfim_log,
            gl.sist_log,
            ge.cgce_emp,
            ge.nome_emp
        FROM BETHADBA.GELOGUSER gl
        INNER JOIN BETHADBA.GEEMPRE ge ON gl.codi_emp = ge.codi_emp
        WHERE gl.data_log BETWEEN '{self.data_inicio}' AND '{self.data_fim}'
        AND ge.cgce_emp IS NOT NULL AND ge.cgce_emp != ''
        ORDER BY gl.data_log, gl.usua_log
        """
        
        if self.limit:
            query = query.replace('SELECT', f'SELECT TOP {self.limit}')
        
        cursor = connection.cursor()
        cursor.execute(query)
        atividades_data = cursor.fetchall()
        
        if not atividades_data:
            self.stdout.write(self.style.WARNING('Nenhuma atividade encontrada no período especificado'))
            return
        
        self.stdout.write(f'Encontradas {len(atividades_data):,} atividades para processar')
        
        # Processar em lotes
        for i in range(0, len(atividades_data), self.batch_size):
            lote = atividades_data[i:i + self.batch_size]
            self.processar_lote_atividades(lote, historical_map)
            
            if (i // self.batch_size + 1) % self.progress_interval == 0:
                self.stdout.write(f'Processadas {i + len(lote):,} atividades...')

    def processar_lote_atividades(self, lote, historical_map):
        """Processa um lote de atividades NORMALIZADO"""
        for atividade in lote:
            try:
                self.stats['atividades_processadas'] += 1
                
                usua_log, data_log, tini_log, tfim_log, dfim_log, sist_log, cgce_emp, nome_emp = atividade
                
                # Gerar ID único para o log
                id_legado = self.gerar_id_legado_atividade(usua_log, data_log, tini_log)
                
                # NOVA ESTRATÉGIA NORMALIZADA: Buscar usuário e empresa
                usuario, empresa, contabilidade = self.buscar_objetos_relacionados(
                    usua_log, cgce_emp, data_log, historical_map
                )
                
                if not usuario or not empresa or not contabilidade:
                    self.stats['erros'] += 1
                    continue
                
                # Calcular tempo de sessão em minutos
                tempo_minutos = self.calcular_tempo_sessao(data_log, tini_log, dfim_log, tfim_log)
                
                if not self.dry_run:
                    # Importar modelo normalizado
                    from administracao.models_etl19_corrigido import LogAtividade
                    
                    # Criar ou atualizar log de atividade NORMALIZADO
                    log_atividade, created = LogAtividade.objects.get_or_create(
                        contabilidade=contabilidade,
                        id_legado=id_legado,
                        defaults={
                            'usuario': usuario,
                            'empresa': empresa,
                            'data_atividade': data_log,
                            'hora_inicial': tini_log,
                            'hora_final': tfim_log,
                            'data_fim': dfim_log,
                            'sistema_modulo': sist_log,
                            'tempo_sessao_minutos': tempo_minutos,
                        }
                    )
                    
                    if created:
                        self.stats['atividades_criadas'] += 1
                
            except Exception as e:
                self.stats['erros'] += 1
                if self.stats['erros'] <= 10:  # Limitar logs de erro
                    self.stdout.write(self.style.ERROR(f'Erro ao processar atividade: {e}'))

    def processar_importacoes(self, connection, historical_map):
        """Processa logs de importações (EFSAIDAS, EFENTRADAS, EFSERVICOS)"""
        tipos_importacao = [
            ('EFSAIDAS', 'SAIDA', 'dsai_sai'),
            ('EFENTRADAS', 'ENTRADA', 'dent_ent'),
            ('EFSERVICOS', 'SERVICO', 'dser_ser'),
        ]
        
        for tabela, tipo, campo_data in tipos_importacao:
            self.stdout.write(f'Processando {tipo}...')
            self.processar_tipo_importacao(connection, historical_map, tabela, tipo, campo_data)

    def processar_tipo_importacao(self, connection, historical_map, tabela, tipo, campo_data):
        """Processa um tipo específico de importação NORMALIZADO"""
        query = f"""
        SELECT 
            ef.codi_usu,
            ef.{campo_data} as data_importacao,
            ge.cgce_emp,
            ge.nome_emp,
            COUNT(*) as quantidade,
            SUM(COALESCE(ef.vcon_{tipo.lower()[:3]}, 0)) as valor_total
        FROM BETHADBA.{tabela} ef
        INNER JOIN BETHADBA.GEEMPRE ge ON ef.codi_emp = ge.codi_emp
        WHERE ef.{campo_data} BETWEEN '{self.data_inicio}' AND '{self.data_fim}'
        AND ge.cgce_emp IS NOT NULL AND ge.cgce_emp != ''
        GROUP BY ef.codi_usu, ef.{campo_data}, ge.cgce_emp, ge.nome_emp
        ORDER BY ef.{campo_data}, ef.codi_usu
        """
        
        if self.limit:
            query = query.replace('SELECT', f'SELECT TOP {self.limit}')
        
        cursor = connection.cursor()
        cursor.execute(query)
        importacoes_data = cursor.fetchall()
        
        if not importacoes_data:
            self.stdout.write(self.style.WARNING(f'Nenhuma importação de {tipo} encontrada'))
            return
        
        self.stdout.write(f'Encontradas {len(importacoes_data):,} importações de {tipo}')
        
        # Processar em lotes
        for i in range(0, len(importacoes_data), self.batch_size):
            lote = importacoes_data[i:i + self.batch_size]
            self.processar_lote_importacoes(lote, historical_map, tipo)
            
            if (i // self.batch_size + 1) % self.progress_interval == 0:
                self.stdout.write(f'Processadas {i + len(lote):,} importações de {tipo}...')

    def processar_lote_importacoes(self, lote, historical_map, tipo):
        """Processa um lote de importações NORMALIZADO"""
        for importacao in lote:
            try:
                self.stats['importacoes_processadas'] += 1
                
                codi_usu, data_importacao, cgce_emp, nome_emp, quantidade, valor_total = importacao
                
                # Gerar ID único para a importação
                id_legado = self.gerar_id_legado_importacao(codi_usu, data_importacao, cgce_emp, tipo)
                
                # NOVA ESTRATÉGIA NORMALIZADA: Buscar usuário e empresa
                usuario, empresa, contabilidade = self.buscar_objetos_relacionados(
                    codi_usu, cgce_emp, data_importacao, historical_map
                )
                
                if not usuario or not empresa or not contabilidade:
                    self.stats['erros'] += 1
                    continue
                
                if not self.dry_run:
                    # Importar modelo normalizado
                    from administracao.models_etl19_corrigido import LogImportacao
                    
                    # Criar ou atualizar log de importação NORMALIZADO
                    log_importacao, created = LogImportacao.objects.get_or_create(
                        contabilidade=contabilidade,
                        id_legado=id_legado,
                        defaults={
                            'usuario': usuario,
                            'empresa': empresa,
                            'tipo_importacao': tipo,
                            'data_importacao': data_importacao,
                            'quantidade_registros': quantidade,
                            'valor_total': valor_total,
                        }
                    )
                    
                    if created:
                        self.stats['importacoes_criadas'] += 1
                
            except Exception as e:
                self.stats['erros'] += 1
                if self.stats['erros'] <= 10:
                    self.stdout.write(self.style.ERROR(f'Erro ao processar importação: {e}'))

    def processar_lancamentos(self, connection, historical_map):
        """Processa logs de lançamentos do CTLANCTO"""
        query = f"""
        SELECT 
            ct.codi_usu,
            ct.data_lan,
            ct.origem_reg,
            ct.vlor_lan,
            ct.cdeb_lan,
            ct.ccre_lan,
            ct.chis_lan,
            ge.cgce_emp,
            ge.nome_emp
        FROM BETHADBA.CTLANCTO ct
        INNER JOIN BETHADBA.GEEMPRE ge ON ct.codi_emp = ge.codi_emp
        WHERE ct.data_lan BETWEEN '{self.data_inicio}' AND '{self.data_fim}'
        AND ge.cgce_emp IS NOT NULL AND ge.cgce_emp != ''
        ORDER BY ct.data_lan, ct.codi_usu
        """
        
        if self.limit:
            query = query.replace('SELECT', f'SELECT TOP {self.limit}')
        
        cursor = connection.cursor()
        cursor.execute(query)
        lancamentos_data = cursor.fetchall()
        
        if not lancamentos_data:
            self.stdout.write(self.style.WARNING('Nenhum lançamento encontrado no período especificado'))
            return
        
        self.stdout.write(f'Encontrados {len(lancamentos_data):,} lançamentos para processar')
        
        # Processar em lotes
        for i in range(0, len(lancamentos_data), self.batch_size):
            lote = lancamentos_data[i:i + self.batch_size]
            self.processar_lote_lancamentos(lote, historical_map)
            
            if (i // self.batch_size + 1) % self.progress_interval == 0:
                self.stdout.write(f'Processados {i + len(lote):,} lançamentos...')

    def processar_lote_lancamentos(self, lote, historical_map):
        """Processa um lote de lançamentos NORMALIZADO"""
        for lancamento in lote:
            try:
                self.stats['lancamentos_processados'] += 1
                
                codi_usu, data_lan, origem_reg, vlor_lan, cdeb_lan, ccre_lan, chis_lan, cgce_emp, nome_emp = lancamento
                
                # Gerar ID único para o lançamento
                id_legado = self.gerar_id_legado_lancamento(codi_usu, data_lan, cgce_emp, origem_reg)
                
                # NOVA ESTRATÉGIA NORMALIZADA: Buscar usuário e empresa
                usuario, empresa, contabilidade = self.buscar_objetos_relacionados(
                    codi_usu, cgce_emp, data_lan, historical_map
                )
                
                if not usuario or not empresa or not contabilidade:
                    self.stats['erros'] += 1
                    continue
                
                # Determinar tipo de operação
                tipo_operacao = 'MANUAL' if origem_reg != 0 else 'AUTOMATICO'
                
                if not self.dry_run:
                    # Importar modelo normalizado
                    from administracao.models_etl19_corrigido import LogLancamento
                    
                    # Criar ou atualizar log de lançamento NORMALIZADO
                    log_lancamento, created = LogLancamento.objects.get_or_create(
                        contabilidade=contabilidade,
                        id_legado=id_legado,
                        defaults={
                            'usuario': usuario,
                            'empresa': empresa,
                            'data_lancamento': data_lan,
                            'origem_registro': origem_reg,
                            'tipo_operacao': tipo_operacao,
                            'valor': vlor_lan,
                            'conta_debito': cdeb_lan,
                            'conta_credito': ccre_lan,
                            'historico': chis_lan,
                        }
                    )
                    
                    if created:
                        self.stats['lancamentos_criados'] += 1
                
            except Exception as e:
                self.stats['erros'] += 1
                if self.stats['erros'] <= 10:
                    self.stdout.write(self.style.ERROR(f'Erro ao processar lançamento: {e}'))

    def buscar_objetos_relacionados(self, usuario_nome, cnpj_empresa, data_evento, historical_map):
        """
        NOVA FUNÇÃO NORMALIZADA: Busca usuário, empresa e contabilidade
        
        Retorna: (usuario, empresa, contabilidade) ou (None, None, None) se erro
        """
        try:
            # 1. Buscar usuário
            try:
                usuario = Usuario.objects.get(nome_usuario=usuario_nome)
            except Usuario.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Usuário {usuario_nome} não encontrado. Pulando registro.'))
                return None, None, None
            
            # 2. Buscar empresa
            try:
                empresa = PessoaJuridica.objects.get(cnpj=cnpj_empresa)
            except PessoaJuridica.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Empresa {cnpj_empresa} não encontrada. Pulando registro.'))
                return None, None, None
            
            # 3. Buscar vínculo usuário-empresa-contabilidade
            vinculos = UsuarioContabilidade.objects.filter(
                usuario=usuario,
                empresa_cnpj=cnpj_empresa,
                ativo=True
            )
            
            if not vinculos.exists():
                self.stdout.write(self.style.WARNING(f'Usuário {usuario_nome} não tem vínculo com empresa {cnpj_empresa}. Pulando registro.'))
                return None, None, None
            
            # 4. Validar se o vínculo está ativo na data do evento
            vinculo_valido = None
            for vinculo in vinculos:
                if (vinculo.data_inicio <= data_evento and 
                    (vinculo.data_fim is None or data_evento <= vinculo.data_fim)):
                    vinculo_valido = vinculo
                    break
            
            if not vinculo_valido:
                self.stdout.write(self.style.WARNING(f'Vínculo do usuário {usuario_nome} com empresa {cnpj_empresa} não está ativo na data {data_evento}. Pulando registro.'))
                return None, None, None
            
            # 5. Retornar objetos relacionados
            return usuario, empresa, vinculo_valido.contabilidade
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao buscar objetos relacionados para usuário {usuario_nome}, empresa {cnpj_empresa}: {e}'))
            return None, None, None

    def gerar_estatisticas_consolidadas(self):
        """Gera estatísticas consolidadas NORMALIZADAS"""
        self.stdout.write('Gerando estatísticas consolidadas...')
        
        # Importar modelos normalizados
        from administracao.models_etl19_corrigido import LogAtividade, LogImportacao, LogLancamento, EstatisticaUsuario
        
        # Agrupar por usuário, empresa e mês
        from django.db.models import Sum, Count
        from datetime import datetime
        
        # Processar atividades
        atividades_stats = LogAtividade.objects.values(
            'contabilidade', 'usuario', 'empresa'
        ).annotate(
            total_atividades=Count('id'),
            tempo_total_minutos=Sum('tempo_sessao_minutos'),
        )
        
        # Processar importações
        importacoes_stats = LogImportacao.objects.values(
            'contabilidade', 'usuario', 'empresa', 'tipo_importacao'
        ).annotate(
            total_importacoes=Count('id'),
            valor_total_importacoes=Sum('valor_total'),
        )
        
        # Processar lançamentos
        lancamentos_stats = LogLancamento.objects.values(
            'contabilidade', 'usuario', 'empresa', 'origem_registro'
        ).annotate(
            total_lancamentos=Count('id'),
            valor_total_lancamentos=Sum('valor'),
        )
        
        # Consolidar estatísticas por usuário/empresa
        stats_consolidadas = {}
        
        # Processar atividades
        for stat in atividades_stats:
            key = (stat['contabilidade'], stat['usuario'], stat['empresa'])
            if key not in stats_consolidadas:
                stats_consolidadas[key] = {
                    'contabilidade_id': stat['contabilidade'],
                    'usuario_id': stat['usuario'],
                    'empresa_id': stat['empresa'],
                    'total_atividades': 0,
                    'tempo_total_minutos': 0,
                    'total_importacoes': 0,
                    'importacoes_saidas': 0,
                    'importacoes_entradas': 0,
                    'importacoes_servicos': 0,
                    'valor_total_importacoes': 0,
                    'total_lancamentos': 0,
                    'lancamentos_manuais': 0,
                    'lancamentos_automaticos': 0,
                    'valor_total_lancamentos': 0,
                }
            
            stats_consolidadas[key]['total_atividades'] = stat['total_atividades']
            stats_consolidadas[key]['tempo_total_minutos'] = stat['tempo_total_minutos'] or 0
        
        # Processar importações
        for stat in importacoes_stats:
            key = (stat['contabilidade'], stat['usuario'], stat['empresa'])
            if key not in stats_consolidadas:
                stats_consolidadas[key] = {
                    'contabilidade_id': stat['contabilidade'],
                    'usuario_id': stat['usuario'],
                    'empresa_id': stat['empresa'],
                    'total_atividades': 0,
                    'tempo_total_minutos': 0,
                    'total_importacoes': 0,
                    'importacoes_saidas': 0,
                    'importacoes_entradas': 0,
                    'importacoes_servicos': 0,
                    'valor_total_importacoes': 0,
                    'total_lancamentos': 0,
                    'lancamentos_manuais': 0,
                    'lancamentos_automaticos': 0,
                    'valor_total_lancamentos': 0,
                }
            
            stats_consolidadas[key]['total_importacoes'] += stat['total_importacoes']
            stats_consolidadas[key]['valor_total_importacoes'] += stat['valor_total_importacoes'] or 0
            
            if stat['tipo_importacao'] == 'SAIDA':
                stats_consolidadas[key]['importacoes_saidas'] = stat['total_importacoes']
            elif stat['tipo_importacao'] == 'ENTRADA':
                stats_consolidadas[key]['importacoes_entradas'] = stat['total_importacoes']
            elif stat['tipo_importacao'] == 'SERVICO':
                stats_consolidadas[key]['importacoes_servicos'] = stat['total_importacoes']
        
        # Processar lançamentos
        for stat in lancamentos_stats:
            key = (stat['contabilidade'], stat['usuario'], stat['empresa'])
            if key not in stats_consolidadas:
                stats_consolidadas[key] = {
                    'contabilidade_id': stat['contabilidade'],
                    'usuario_id': stat['usuario'],
                    'empresa_id': stat['empresa'],
                    'total_atividades': 0,
                    'tempo_total_minutos': 0,
                    'total_importacoes': 0,
                    'importacoes_saidas': 0,
                    'importacoes_entradas': 0,
                    'importacoes_servicos': 0,
                    'valor_total_importacoes': 0,
                    'total_lancamentos': 0,
                    'lancamentos_manuais': 0,
                    'lancamentos_automaticos': 0,
                    'valor_total_lancamentos': 0,
                }
            
            stats_consolidadas[key]['total_lancamentos'] += stat['total_lancamentos']
            stats_consolidadas[key]['valor_total_lancamentos'] += stat['valor_total_lancamentos'] or 0
            
            if stat['origem_registro'] == 0:
                stats_consolidadas[key]['lancamentos_automaticos'] = stat['total_lancamentos']
            else:
                stats_consolidadas[key]['lancamentos_manuais'] = stat['total_lancamentos']
        
        # Criar registros de estatísticas NORMALIZADOS
        from core.models import Contabilidade
        
        for key, stats in stats_consolidadas.items():
            try:
                contabilidade = Contabilidade.objects.get(id=stats['contabilidade_id'])
                usuario = Usuario.objects.get(id=stats['usuario_id'])
                empresa = PessoaJuridica.objects.get(id=stats['empresa_id'])
                
                # Usar primeiro dia do mês como período de referência
                periodo_referencia = datetime.now().replace(day=1).date()
                
                if not self.dry_run:
                    estatistica, created = EstatisticaUsuario.objects.get_or_create(
                        contabilidade=contabilidade,
                        usuario=usuario,
                        empresa=empresa,
                        periodo_referencia=periodo_referencia,
                        defaults=stats
                    )
                    
                    if created:
                        self.stats['estatisticas_criadas'] += 1
                
            except Exception as e:
                self.stats['erros'] += 1
                if self.stats['erros'] <= 10:
                    self.stdout.write(self.style.ERROR(f'Erro ao criar estatística: {e}'))

    def gerar_id_legado_atividade(self, usuario, data, hora):
        """Gera ID único para atividade"""
        return hashlib.md5(f"ATIVIDADE_{usuario}_{data}_{hora}".encode()).hexdigest()[:50]

    def gerar_id_legado_importacao(self, usuario, data, cnpj, tipo):
        """Gera ID único para importação"""
        return hashlib.md5(f"IMPORTACAO_{usuario}_{data}_{cnpj}_{tipo}".encode()).hexdigest()[:50]

    def gerar_id_legado_lancamento(self, usuario, data, cnpj, origem):
        """Gera ID único para lançamento"""
        return hashlib.md5(f"LANCAMENTO_{usuario}_{data}_{cnpj}_{origem}".encode()).hexdigest()[:50]

    def calcular_tempo_sessao(self, data_inicio, hora_inicio, data_fim, hora_fim):
        """Calcula tempo de sessão em minutos"""
        try:
            if not data_fim or not hora_fim:
                return None
            
            # Converter para datetime
            dt_inicio = datetime.combine(data_inicio, hora_inicio)
            dt_fim = datetime.combine(data_fim, hora_fim)
            
            # Calcular diferença em minutos
            diferenca = dt_fim - dt_inicio
            return int(diferenca.total_seconds() / 60)
        except:
            return None

    def gerar_relatorio_final(self):
        """Gera relatório final da importação"""
        self.stats['tempo_fim'] = time.time()
        tempo_total = self.stats['tempo_fim'] - self.stats['tempo_inicio']
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('RELATÓRIO FINAL - ETL 19 LOGS UNIFICADOS NORMALIZADOS')
        self.stdout.write('='*80)
        
        if self.tipo in ['atividades', 'todos']:
            self.stdout.write(f'📊 ATIVIDADES:')
            self.stdout.write(f'  - Processadas: {self.stats["atividades_processadas"]:,}')
            self.stdout.write(f'  - Criadas: {self.stats["atividades_criadas"]:,}')
        
        if self.tipo in ['importacoes', 'todos']:
            self.stdout.write(f'📊 IMPORTAÇÕES:')
            self.stdout.write(f'  - Processadas: {self.stats["importacoes_processadas"]:,}')
            self.stdout.write(f'  - Criadas: {self.stats["importacoes_criadas"]:,}')
        
        if self.tipo in ['lancamentos', 'todos']:
            self.stdout.write(f'📊 LANÇAMENTOS:')
            self.stdout.write(f'  - Processados: {self.stats["lancamentos_processados"]:,}')
            self.stdout.write(f'  - Criados: {self.stats["lancamentos_criados"]:,}')
        
        if self.tipo == 'todos':
            self.stdout.write(f'📊 ESTATÍSTICAS:')
            self.stdout.write(f'  - Criadas: {self.stats["estatisticas_criadas"]:,}')
        
        self.stdout.write(f'❌ ERROS: {self.stats["erros"]:,}')
        self.stdout.write(f'⏱️  TEMPO TOTAL: {tempo_total:.2f} segundos')
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  MODO DRY-RUN: Nenhum dado foi salvo no banco'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Importação NORMALIZADA concluída com sucesso!'))
        
        self.stdout.write('='*80)
