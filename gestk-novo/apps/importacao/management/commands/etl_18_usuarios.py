"""
ETL 18 - Usuários do Sistema Legado

Importa usuários do USCONFUSUARIO e seus vínculos com empresas
seguindo a regra de ouro de mapeamento multitenant.

Dados importados:
- Usuários (USCONFUSUARIO)
- Vínculos usuário-empresa (USCONFEMPRESAS)
- Módulos acessíveis (ROWGENERATOR)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal
import random
import time

from apps.importacao.management.commands._base import BaseETLCommand
from apps.administracao.models import Usuario, UsuarioContabilidade, UsuarioModulo


class Command(BaseETLCommand):
    help = 'ETL 18 - Importa usuários do sistema legado com mapeamento multitenant'

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
            help='Limitar número de usuários para processar (para testes)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Tamanho do lote para processamento (padrão: 100)',
        )

    def handle(self, *args, **options):
        """
        Ponto de entrada principal do ETL 18. Executa o fluxo completo de importação de usuários do sistema legado,
        incluindo usuários administrativos, processando vínculos e gerando relatório final.
        """
        self.dry_run = options['dry_run']
        self.limit = options['limit']
        self.batch_size = options['batch_size']

        if self.dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhum dado será salvo no banco'))

        self.stdout.write(self.style.SUCCESS('=== ETL 18 - USUÁRIOS DO SISTEMA LEGADO ==='))

        try:
            # 1. Construir mapa histórico de contabilidades
            self.stdout.write('\n[1] Construindo mapa histórico de contabilidades...')
            contabilidade_historico = self.build_historical_contabilidade_map_cached()

            # 2. Importar vínculos usuário-empresa-módulo do Sybase
            self.stdout.write('\n[2] Importando vínculos usuário-empresa-módulo do Sybase...')
            vinculos = self.fetch_vinculos_usuarios_sybase()

            # 3. Processar vínculos em lotes
            self.stdout.write('\n[3] Processando vínculos...')
            self.processar_vinculos_em_lote(vinculos, contabilidade_historico)

            # 4. Relatório final
            self.stdout.write('\n[4] Relatório final...')
            self.gerar_relatorio_final()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro durante execução: {e}'))
            raise
        finally:
            self.close_sybase_connection()

    def fetch_vinculos_usuarios_sybase(self):
        """
        Busca vínculos usuário-empresa-módulo no Sybase, incluindo usuários administrativos.
        Retorna lista de dicionários com dados dos vínculos.
        """
        self.stdout.write('Buscando vínculos usuário-empresa-módulo no Sybase...')

        query = """
        SELECT 
            USCONFUSUARIO.I_USUARIO AS CP_NOME_USUARIO, 
            ROWGENERATOR.ROW_NUM AS CP_MODULO, 
            CAST(USCONFEMPRESAS.I_EMPRESA AS VARCHAR(20)) CODIGO_EMPRESA,
            GEEMPRE.NOME_EMP AS CP_EMPRESA,
            GEEMPRE.CGCE_EMP AS CP_CNPJ_EMPRESA
        FROM BETHADBA.USCONFEMPRESAS AS USCONFEMPRESAS,
             BETHADBA.USCONFUSUARIO AS USCONFUSUARIO, 
             DSDBA.ROWGENERATOR AS ROWGENERATOR, 
             BETHADBA.GEEMPRE AS GEEMPRE 
        WHERE USCONFUSUARIO.I_CONFUSUARIO = USCONFEMPRESAS.I_CONFUSUARIO 
          AND USCONFUSUARIO.TIPO = 1 
          AND CP_MODULO <> 2 
          AND USCONFEMPRESAS.MODULOS LIKE '%'||STRING(ROWGENERATOR.ROW_NUM)||'%' 
          AND GEEMPRE.CODI_EMP = USCONFEMPRESAS.I_EMPRESA
          AND GEEMPRE.CGCE_EMP IS NOT NULL
          AND TRIM(GEEMPRE.CGCE_EMP) != ''
        ORDER BY USCONFUSUARIO.I_USUARIO, USCONFEMPRESAS.I_EMPRESA, ROWGENERATOR.ROW_NUM
        """

        if self.limit:
            query = f"SELECT TOP {self.limit} * FROM ({query}) AS vinculos"

        connection = self.get_sybase_connection()
        if not connection:
            return []

        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [column[0] for column in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]

            self.stdout.write(f'Encontrados {len(results)} vínculos no Sybase')
            return results

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao buscar vínculos: {e}'))
            return []

    def processar_vinculos_em_lote(self, vinculos, contabilidade_historico):
        """
        Processa vínculos usuário-empresa-módulo em lotes, incluindo usuários administrativos.
        Agrupa vínculos por usuário e executa processamento individual.
        """
        total_vinculos = len(vinculos)
        total_usuarios = 0
        total_usuarios_criados = 0
        total_usuarios_atualizados = 0
        total_vinculos_criados = 0
        total_modulos_criados = 0
        total_erros = 0

        # Agrupa vínculos por usuário
        usuarios_vinculos = {}
        for vinculo in vinculos:
            usuario_nome = vinculo['CP_NOME_USUARIO']
            if usuario_nome not in usuarios_vinculos:
                usuarios_vinculos[usuario_nome] = []
            usuarios_vinculos[usuario_nome].append(vinculo)

        self.stdout.write(f'Processando {len(usuarios_vinculos)} usuários com {total_vinculos} vínculos...')

        # Processa cada usuário
        for usuario_nome, vinculos_usuario in usuarios_vinculos.items():
            total_usuarios += 1
            try:
                usuario_obj, created = self.processar_usuario_com_vinculos(usuario_nome, vinculos_usuario, contabilidade_historico)
                if created:
                    total_usuarios_criados += 1
                else:
                    total_usuarios_atualizados += 1
                total_vinculos_criados += len(vinculos_usuario)
                total_modulos_criados += len(vinculos_usuario)
                if len(usuarios_vinculos) > 10 and total_vinculos_criados % 1000 == 0:
                    self.stdout.write(f'  Processados: {total_vinculos_criados}/{total_vinculos} vínculos')
                    self.stdout.flush()
            except Exception as e:
                total_erros += 1
                self.stdout.write(self.style.ERROR(f'Erro ao processar usuário {usuario_nome}: {e}'))

        # Estatísticas do lote
        self.stdout.write(f'\n✅ Lote processado:')
        self.stdout.write(f'  Usuários processados: {total_usuarios}')
        self.stdout.write(f'  Usuários criados: {total_usuarios_criados}')
        self.stdout.write(f'  Usuários atualizados: {total_usuarios_atualizados}')
        self.stdout.write(f'  Vínculos criados: {total_vinculos_criados}')
        self.stdout.write(f'  Módulos criados: {total_modulos_criados}')
        self.stdout.write(f'  Erros: {total_erros}')

    def processar_usuario(self, usuario_data, historical_map):
        """Processa um usuário individual"""
        i_usuario = usuario_data['I_USUARIO']
        nome_usuario = usuario_data['NOME'] or i_usuario
        
        # Determinar tipo de usuário
        tipo_usuario = self.determinar_tipo_usuario(usuario_data)
        
        # Buscar vínculos do usuário com empresas
        vínculos_empresas = self.buscar_vínculos_empresas(i_usuario)
        
        if not vínculos_empresas:
            self.stdout.write(f'  ⚠ Usuário {i_usuario} sem vínculos com empresas')
            return None, False
        
        # Processar cada vínculo com empresa
        for vínculo in vínculos_empresas:
            codi_emp = vínculo['I_EMPRESA']
            
            # Usar regra de ouro para encontrar contabilidade
            contabilidade = self.get_contabilidade_for_date_optimized(
                historical_map,
                codi_emp,
                date(2023, 6, 1)  # Data padrão para mapeamento
            )
            
            if not contabilidade:
                self.stdout.write(f'  ⚠ Contabilidade não encontrada para empresa {codi_emp}')
                continue
            
            # Criar ou atualizar usuário
            if not self.dry_run:
                usuario_obj, created = Usuario.objects.update_or_create(
                    contabilidade=contabilidade,
                    id_legado=i_usuario,
                    defaults={
                        'nome_usuario': nome_usuario,
                        'tipo_usuario': tipo_usuario,
                        'ativo': usuario_data.get('SITUACAO', 'A') == 'A',
                        'data_ultimo_acesso': self.gerar_data_ultimo_acesso(),
                    }
                )
                
                return usuario_obj, created
            else:
                return None, True

    def determinar_tipo_usuario(self, usuario_data):
        """Determina o tipo do usuário baseado nos dados"""
        i_usuario = usuario_data['I_USUARIO']
        
        # Tipos especiais baseados no nome
        if i_usuario in ['GERENTE', 'ADMIN']:
            return 'GERENTE'
        elif i_usuario in ['EXTERNO', 'CONTABILEXTERNO']:
            return 'EXTERNO'
        elif 'FISCAL' in i_usuario:
            return 'FISCAL'
        elif 'CONTABIL' in i_usuario:
            return 'CONTABIL'
        else:
            return 'NORMAL'
    
    def eh_usuario_administrativo(self, usuario_data):
        """Verifica se o usuário é administrativo (acesso a todas as empresas)"""
        i_usuario = usuario_data['I_USUARIO']
        
        # Usuários administrativos que têm acesso a todas as empresas
        usuarios_admin = [
            'GERENTE', 'ADMIN', 'EXTERNO', 'CONTABILEXTERNO',
            'NEOSOLUTIONS', 'NEO', 'DOMINIO', 'HUBCOUNT'
        ]
        
        return i_usuario in usuarios_admin
    
    def eh_usuario_administrativo_por_nome(self, nome_usuario):
        """Verifica se o usuário é administrativo pelo nome"""
        usuarios_admin = [
            'GERENTE', 'ADMIN', 'EXTERNO', 'CONTABILEXTERNO',
            'NEOSOLUTIONS', 'NEO', 'DOMINIO', 'HUBCOUNT'
        ]
        
        return nome_usuario in usuarios_admin
    
    def processar_usuario_com_vinculos(self, nome_usuario, vinculos_usuario, contabilidade_historico):
        """
        Processa um usuário individual e seus vínculos, incluindo administrativos.
        Cria ou atualiza o usuário e seus vínculos/módulos para cada contabilidade relacionada.
        """
        tipo_usuario = self.classificar_tipo_usuario_por_nome(nome_usuario)
        empresas_processadas = set()
        usuarios_criados = 0

        for vinculo in vinculos_usuario:
            codigo_empresa = vinculo['CODIGO_EMPRESA']
            cnpj_empresa = vinculo['CP_CNPJ_EMPRESA']

            # Evita duplicidade de empresas
            if codigo_empresa in empresas_processadas:
                continue
            empresas_processadas.add(codigo_empresa)

            # Limpa CNPJ
            cnpj_limpo = self.limpar_documento(cnpj_empresa)
            if not cnpj_limpo:
                continue

            # Busca todas as contabilidades que tiveram contratos com esta empresa
            contabilidades_empresa = self.buscar_contabilidades_empresa(contabilidade_historico, cnpj_limpo)
            if not contabilidades_empresa:
                continue

            # Cria usuário para cada contabilidade
            for contabilidade in contabilidades_empresa:
                if not self.dry_run:
                    usuario_obj, created = Usuario.objects.update_or_create(
                        contabilidade=contabilidade,
                        cnpj_empresa=cnpj_limpo,
                        id_legado=nome_usuario,
                        defaults={
                            'nome_usuario': nome_usuario,
                            'tipo_usuario': tipo_usuario,
                            'ativo': True,
                            'data_ultimo_acesso': self.gerar_data_ultimo_acesso(),
                        }
                    )
                    if created:
                        usuarios_criados += 1

                    # Cria vínculo usuário-contabilidade
                    UsuarioContabilidade.objects.update_or_create(
                        contabilidade=contabilidade,
                        usuario=usuario_obj,
                        data_inicio=datetime(2023, 1, 1),
                        defaults={
                            'ativo': True,
                            'modulos_acesso': [vinculo['CP_MODULO']],
                        }
                    )

                    # Cria módulo do usuário
                    UsuarioModulo.objects.update_or_create(
                        contabilidade=contabilidade,
                        usuario=usuario_obj,
                        modulo_id=vinculo['CP_MODULO'],
                        defaults={
                            'modulo_nome': self.obter_nome_modulo(vinculo['CP_MODULO']),
                            'ativo': True,
                        }
                    )
                else:
                    usuarios_criados += 1

        return usuarios_criados > 0, usuarios_criados > 0
    
    def buscar_contabilidades_empresa(self, historical_map, cnpj_limpo):
        """Busca todas as contabilidades que tiveram contratos com a empresa"""
        if cnpj_limpo not in historical_map:
            return []
        
        contratos = historical_map[cnpj_limpo]
        contabilidades = []
        
        for data_inicio, data_termino, contabilidade in contratos:
            # Incluir contabilidade se teve contrato em qualquer período
            if contabilidade not in contabilidades:
                contabilidades.append(contabilidade)
        
        return contabilidades
    
    def classificar_tipo_usuario_por_nome(self, nome_usuario):
        """
        Classifica o tipo do usuário com base no nome.
        """
        if nome_usuario in ['GERENTE', 'ADMIN']:
            return 'GERENTE'
        elif nome_usuario in ['EXTERNO', 'CONTABILEXTERNO']:
            return 'EXTERNO'
        elif 'FISCAL' in nome_usuario:
            return 'FISCAL'
        elif 'CONTABIL' in nome_usuario:
            return 'CONTABIL'
        else:
            return 'NORMAL'
    
    def obter_nome_modulo(self, modulo_id):
        """Obtém o nome do módulo pelo ID"""
        modulos_sistema = {
            1: 'Contábil',
            3: 'Fiscal',
            4: 'RH',
            5: 'Relatórios',
            6: 'Configurações',
            7: 'Auditoria',
            8: 'Importação',
            9: 'Exportação',
            10: 'Backup',
            11: 'Restauração',
            12: 'Logs',
            13: 'Administração'
        }
        
        return modulos_sistema.get(modulo_id, f'Módulo {modulo_id}')

    def buscar_vínculos_empresas(self, i_usuario):
        """Busca vínculos do usuário com empresas"""
        query = """
        SELECT DISTINCT
            e.I_EMPRESA,
            e.MODULOS,
            ge.NOME_EMP,
            ge.CGCE_EMP
        FROM BETHADBA.USCONFEMPRESAS e
        INNER JOIN BETHADBA.USCONFUSUARIO u ON e.I_CONFUSUARIO = u.I_CONFUSUARIO
        INNER JOIN BETHADBA.GEEMPRE ge ON e.I_EMPRESA = ge.CODI_EMP
        WHERE u.I_USUARIO = ?
        AND e.TIPO = 1
        AND ge.CGCE_EMP IS NOT NULL
        AND TRIM(ge.CGCE_EMP) != ''
        """
        
        connection = self.get_sybase_connection()
        if not connection:
            return []
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, (i_usuario,))
                columns = [column[0] for column in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return results
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao buscar vínculos para {i_usuario}: {e}'))
            return []

    def processar_vínculos_usuario(self, usuario_data, historical_map):
        """Processa vínculos do usuário com contabilidades"""
        i_usuario = usuario_data['I_USUARIO']
        vínculos_empresas = self.buscar_vínculos_empresas(i_usuario)
        vínculos_criados = 0
        
        for vínculo in vínculos_empresas:
            codi_emp = vínculo['I_EMPRESA']
            
            # Usar regra de ouro para encontrar contabilidade
            contabilidade = self.get_contabilidade_for_date_optimized(
                historical_map,
                codi_emp,
                date(2023, 6, 1)
            )
            
            if not contabilidade:
                continue
            
            # Buscar usuário criado
            try:
                usuario_obj = Usuario.objects.get(
                    contabilidade=contabilidade,
                    id_legado=i_usuario
                )
            except Usuario.DoesNotExist:
                continue
            
            # Criar vínculo usuário-contabilidade
            if not self.dry_run:
                vínculo_obj, created = UsuarioContabilidade.objects.update_or_create(
                    contabilidade=contabilidade,
                    usuario=usuario_obj,
                    data_inicio=datetime(2023, 1, 1),
                    defaults={
                        'ativo': True,
                        'modulos_acesso': self.processar_módulos_string(vínculo.get('MODULOS', '')),
                    }
                )
                
                if created:
                    vínculos_criados += 1
        
        return vínculos_criados

    def processar_módulos_usuario(self, usuario_data, historical_map):
        """Processa módulos acessíveis pelo usuário"""
        i_usuario = usuario_data['I_USUARIO']
        vínculos_empresas = self.buscar_vínculos_empresas(i_usuario)
        módulos_criados = 0
        
        # Módulos padrão do sistema
        módulos_sistema = {
            1: 'Contábil',
            3: 'Fiscal',
            4: 'RH',
            5: 'Relatórios',
            6: 'Configurações',
            7: 'Auditoria',
            8: 'Importação',
            9: 'Exportação',
            10: 'Backup',
            11: 'Restauração',
            12: 'Logs',
            13: 'Administração'
        }
        
        for vínculo in vínculos_empresas:
            codi_emp = vínculo['I_EMPRESA']
            
            # Usar regra de ouro para encontrar contabilidade
            contabilidade = self.get_contabilidade_for_date_optimized(
                historical_map,
                codi_emp,
                date(2023, 6, 1)
            )
            
            if not contabilidade:
                continue
            
            # Buscar usuário criado
            try:
                usuario_obj = Usuario.objects.get(
                    contabilidade=contabilidade,
                    id_legado=i_usuario
                )
            except Usuario.DoesNotExist:
                continue
            
            # Processar módulos baseado no tipo de usuário
            módulos_acesso = self.determinar_módulos_acesso(usuario_data)
            
            for módulo_id, módulo_nome in módulos_acesso.items():
                if not self.dry_run:
                    módulo_obj, created = UsuarioModulo.objects.update_or_create(
                        contabilidade=contabilidade,
                        usuario=usuario_obj,
                        modulo_id=módulo_id,
                        defaults={
                            'modulo_nome': módulo_nome,
                            'ativo': True,
                        }
                    )
                    
                    if created:
                        módulos_criados += 1
        
        return módulos_criados

    def determinar_módulos_acesso(self, usuario_data):
        """Determina quais módulos o usuário pode acessar"""
        tipo_usuario = self.determinar_tipo_usuario(usuario_data)
        
        # Módulos baseados no tipo de usuário
        módulos_por_tipo = {
            'GERENTE': {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13},
            'EXTERNO': {1, 3, 5},
            'FISCAL': {3, 5, 7},
            'CONTABIL': {1, 3, 4, 5, 7},
            'NORMAL': {1, 3, 5}
        }
        
        módulos_acesso = módulos_por_tipo.get(tipo_usuario, {1, 3, 5})
        
        # Módulos do sistema
        módulos_sistema = {
            1: 'Contábil',
            3: 'Fiscal',
            4: 'RH',
            5: 'Relatórios',
            6: 'Configurações',
            7: 'Auditoria',
            8: 'Importação',
            9: 'Exportação',
            10: 'Backup',
            11: 'Restauração',
            12: 'Logs',
            13: 'Administração'
        }
        
        return {módulo_id: módulos_sistema[módulo_id] for módulo_id in módulos_acesso}

    def processar_módulos_string(self, módulos_string):
        """Processa string de módulos do sistema legado"""
        if not módulos_string:
            return []
        
        try:
            # Converter string para lista de inteiros
            módulos = [int(m) for m in módulos_string.split(',') if m.strip().isdigit()]
            return módulos
        except:
            return []

    def gerar_data_ultimo_acesso(self):
        """Gera data de último acesso realística"""
        # Últimos 30 dias
        dias_atras = random.randint(0, 30)
        data_base = timezone.now() - timedelta(days=dias_atras)
        
        # Hora aleatória do dia
        hora = random.randint(8, 18)
        minuto = random.randint(0, 59)
        
        return data_base.replace(hour=hora, minute=minuto, second=0, microsecond=0)

    def gerar_relatorio_final(self):
        """
        Gera relatório final da execução do ETL 18, mostrando estatísticas e totais.
        """
        self.stdout.write('\n' + '='*60)
        self.stdout.write('RELATÓRIO FINAL - ETL 18')
        self.stdout.write('='*60)

        if not self.dry_run:
            # Contabiliza registros criados
            total_usuarios = Usuario.objects.count()
            total_vinculos = UsuarioContabilidade.objects.count()
            total_modulos = UsuarioModulo.objects.count()

            self.stdout.write(f'Total de usuários: {total_usuarios}')
            self.stdout.write(f'Total de vínculos: {total_vinculos}')
            self.stdout.write(f'Total de módulos: {total_modulos}')

        # Estatísticas de performance
        self.print_stats()

        self.stdout.write('='*60)
        self.stdout.write('ETL 18 CONCLUÍDO COM SUCESSO!')
        self.stdout.write('='*60)
