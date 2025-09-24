"""
Comando para configurar ambiente de desenvolvimento do GESTK
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.core.models import Contabilidade, Usuario
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Configura ambiente de desenvolvimento do GESTK'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Resetar banco de dados antes de configurar'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('🚀 Configurando ambiente de desenvolvimento do GESTK...')
        
        if options['reset']:
            self.reset_database()
        
        # 1. Criar contabilidade GESTK (empresa criadora)
        contabilidade_gestk = self.criar_contabilidade_gestk()
        
        # 2. Criar superusuário do sistema
        superuser = self.criar_superusuario_gestk(contabilidade_gestk)
        
        # 3. Criar contabilidade de teste
        contabilidade_teste = self.criar_contabilidade_teste()
        
        # 4. Criar usuários de teste
        self.criar_usuarios_teste(contabilidade_teste)
        
        self.stdout.write(
            self.style.SUCCESS('✅ Ambiente de desenvolvimento configurado com sucesso!')
        )
        
        self.mostrar_resumo(superuser, contabilidade_gestk, contabilidade_teste)
    
    def reset_database(self):
        """Resetar banco de dados"""
        self.stdout.write('🗑️ Resetando banco de dados...')
        
        # Limpar dados existentes
        Usuario.objects.all().delete()
        Contabilidade.objects.all().delete()
        
        self.stdout.write('✅ Banco de dados resetado')
    
    def criar_contabilidade_gestk(self):
        """Criar contabilidade GESTK (empresa criadora)"""
        self.stdout.write('🏢 Criando contabilidade GESTK...')
        
        contabilidade, created = Contabilidade.objects.get_or_create(
            cnpj='00000000000100',  # CNPJ especial para empresa criadora
            defaults={
                'razao_social': 'GESTK - Sistema de Gestão Contábil LTDA',
                'nome_fantasia': 'GESTK',
                'endereco': 'Rua da Tecnologia, 123 - Centro',
                'telefone': '(11) 99999-9999',
                'email': 'contato@gestk.com.br',
                'ativo': True,
            }
        )
        
        if created:
            self.stdout.write('✅ Contabilidade GESTK criada')
        else:
            self.stdout.write('ℹ️ Contabilidade GESTK já existe')
        
        return contabilidade
    
    def criar_superusuario_gestk(self, contabilidade):
        """Criar superusuário do sistema GESTK"""
        self.stdout.write('👤 Criando superusuário do sistema...')
        
        User = get_user_model()
        
        with transaction.atomic():
            # Criar usuário Django
            user, created = User.objects.get_or_create(
                username='wando',
                defaults={
                    'email': 'juridico@office-ce.com.br',
                    'first_name': 'Wando',
                    'last_name': 'Sistema',
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password('H33tsupa!')
                user.save()
                
                # Configurar como superusuário GESTK
                user.tipo_usuario = 'superuser'
                user.contabilidade = contabilidade
                user.modulos_acessiveis = [
                    'gestao', 'dashboards', 'fiscal', 'contabil', 
                    'rh', 'administracao', 'etl'
                ]
                user.pode_executar_etl = True
                user.pode_administrar_usuarios = True
                user.pode_ver_dados_sensiveis = True
                user.save()
                
                self.stdout.write('✅ Superusuário GESTK criado')
            else:
                self.stdout.write('ℹ️ Superusuário GESTK já existe')
        
        return user
    
    def criar_contabilidade_teste(self):
        """Criar contabilidade de teste"""
        self.stdout.write('🏢 Criando contabilidade de teste...')
        
        contabilidade, created = Contabilidade.objects.get_or_create(
            cnpj='12345678000199',
            defaults={
                'razao_social': 'Contabilidade Silva & Associados LTDA',
                'nome_fantasia': 'Silva & Associados',
                'endereco': 'Rua das Flores, 456 - Centro',
                'telefone': '(11) 3333-4444',
                'email': 'contato@silvaassociados.com.br',
                'ativo': True,
            }
        )
        
        if created:
            self.stdout.write('✅ Contabilidade de teste criada')
        else:
            self.stdout.write('ℹ️ Contabilidade de teste já existe')
        
        return contabilidade
    
    def criar_usuarios_teste(self, contabilidade):
        """Criar usuários de teste"""
        self.stdout.write('👥 Criando usuários de teste...')
        
        User = get_user_model()
        
        # Usuário administrador da contabilidade
        admin_user, created = User.objects.get_or_create(
            username='admin_contabilidade',
            defaults={
                'email': 'admin@silvaassociados.com.br',
                'first_name': 'Admin',
                'last_name': 'Contabilidade',
                'is_staff': True,
                'is_active': True,
            }
        )
        
        if created:
            admin_user.set_password('admin123')
            admin_user.contabilidade = contabilidade
            admin_user.tipo_usuario = 'admin'
            admin_user.modulos_acessiveis = ['gestao', 'dashboards', 'fiscal', 'contabil', 'rh']
            admin_user.pode_executar_etl = True
            admin_user.pode_administrar_usuarios = True
            admin_user.pode_ver_dados_sensiveis = True
            admin_user.save()
            
            self.stdout.write('✅ Usuário admin da contabilidade criado')
        
        # Usuário operacional
        operacional_user, created = User.objects.get_or_create(
            username='operacional',
            defaults={
                'email': 'operacional@silvaassociados.com.br',
                'first_name': 'Usuário',
                'last_name': 'Operacional',
                'is_staff': False,
                'is_active': True,
            }
        )
        
        if created:
            operacional_user.set_password('operacional123')
            operacional_user.contabilidade = contabilidade
            operacional_user.tipo_usuario = 'operacional'
            operacional_user.modulos_acessiveis = ['gestao', 'dashboards']
            operacional_user.pode_executar_etl = False
            operacional_user.pode_administrar_usuarios = False
            operacional_user.pode_ver_dados_sensiveis = False
            operacional_user.save()
            
            self.stdout.write('✅ Usuário operacional criado')
        
        # Usuário ETL
        etl_user, created = User.objects.get_or_create(
            username='etl_user',
            defaults={
                'email': 'etl@silvaassociados.com.br',
                'first_name': 'Usuário',
                'last_name': 'ETL',
                'is_staff': False,
                'is_active': True,
            }
        )
        
        if created:
            etl_user.set_password('etl123')
            etl_user.contabilidade = contabilidade
            etl_user.tipo_usuario = 'etl'
            etl_user.modulos_acessiveis = ['etl']
            etl_user.pode_executar_etl = True
            etl_user.pode_administrar_usuarios = False
            etl_user.pode_ver_dados_sensiveis = False
            etl_user.save()
            
            self.stdout.write('✅ Usuário ETL criado')
    
    def mostrar_resumo(self, superuser, contabilidade_gestk, contabilidade_teste):
        """Mostrar resumo da configuração"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📋 RESUMO DA CONFIGURAÇÃO')
        self.stdout.write('='*60)
        
        self.stdout.write(f'\n🏢 CONTABILIDADE GESTK (Sistema):')
        self.stdout.write(f'   Razão Social: {contabilidade_gestk.razao_social}')
        self.stdout.write(f'   CNPJ: {contabilidade_gestk.cnpj}')
        self.stdout.write(f'   Email: {contabilidade_gestk.email}')
        
        self.stdout.write(f'\n👤 SUPERUSUÁRIO DO SISTEMA:')
        self.stdout.write(f'   Username: {superuser.username}')
        self.stdout.write(f'   Email: {superuser.email}')
        self.stdout.write(f'   Tipo: {superuser.get_tipo_usuario_display()}')
        self.stdout.write(f'   Senha: H33tsupa!')
        
        self.stdout.write(f'\n🏢 CONTABILIDADE DE TESTE:')
        self.stdout.write(f'   Razão Social: {contabilidade_teste.razao_social}')
        self.stdout.write(f'   CNPJ: {contabilidade_teste.cnpj}')
        
        self.stdout.write(f'\n👥 USUÁRIOS DE TESTE:')
        self.stdout.write(f'   admin_contabilidade / admin123 (Admin)')
        self.stdout.write(f'   operacional / operacional123 (Operacional)')
        self.stdout.write(f'   etl_user / etl123 (ETL)')
        
        self.stdout.write(f'\n🔗 ACESSO AO SISTEMA:')
        self.stdout.write(f'   Django Admin: http://localhost:8000/admin/')
        self.stdout.write(f'   API: http://localhost:8000/api/')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write('✅ Configuração concluída!')
        self.stdout.write('='*60)
