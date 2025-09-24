import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

class Contabilidade(models.Model):
    """Modelo principal para multi-tenancy - representa escritórios de contabilidade"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    razao_social = models.TextField(_('Razão Social'))
    nome_fantasia = models.TextField(_('Nome Fantasia'), blank=True, null=True)
    cnpj = models.CharField(_('CNPJ'), max_length=14, unique=True)
    id_legado = models.IntegerField(_('ID Legado'), unique=True, null=True, blank=True, help_text="ID da empresa no sistema Sybase (BETHADBA.HRCONTRATO.CODI_EMP)")
    endereco = models.CharField(_('Endereço'), max_length=255, blank=True, null=True)
    telefone = models.CharField(_('Telefone'), max_length=20, blank=True, null=True)
    email = models.EmailField(_('E-mail'), blank=True, null=True)
    ativo = models.BooleanField(_('Ativo'), default=True)
    created_at = models.DateTimeField(_('Data de Criação'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Data de Atualização'), auto_now=True)
    
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = _('Contabilidade')
        verbose_name_plural = _('Contabilidades')
        db_table = 'core_contabilidades'
        ordering = ['razao_social']
        indexes = [
            models.Index(fields=['cnpj']),
            models.Index(fields=['ativo']),
            models.Index(fields=['id_legado']),
        ]
    
    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

class Usuario(AbstractUser):
    """
    Usuário customizado do GESTK com referência obrigatória à contabilidade (tenant)
    """
    # Tipos de usuário
    TIPO_USUARIO_CHOICES = [
        ('superuser', 'Superusuário'),
        ('admin', 'Administrador'),
        ('operacional', 'Operacional'),
        ('etl', 'ETL'),
        ('readonly', 'Somente Leitura'),
    ]
    
    # Módulos do sistema
    MODULO_CHOICES = [
        ('gestao', 'Gestão'),
        ('dashboards', 'Dashboards'),
        ('fiscal', 'Fiscal'),
        ('contabil', 'Contábil'),
        ('rh', 'Recursos Humanos'),
        ('administracao', 'Administração'),
        ('etl', 'ETL'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relacionamento com contabilidade (obrigatório)
    contabilidade = models.ForeignKey(
        Contabilidade, 
        on_delete=models.CASCADE,
        related_name='usuarios',
        verbose_name=_('Contabilidade'),
        null=True, blank=True  # Temporário para superusuários
    )
    
    # Dados pessoais
    cpf = models.CharField(_('CPF'), max_length=11, unique=True, null=True, blank=True)
    ativo = models.BooleanField(_('Ativo'), default=True)
    
    # Sistema de permissões customizado
    tipo_usuario = models.CharField(
        _('Tipo de Usuário'),
        max_length=20,
        choices=TIPO_USUARIO_CHOICES,
        default='operacional'
    )
    
    modulos_acessiveis = models.JSONField(
        _('Módulos Acessíveis'),
        default=list,
        help_text="Lista de módulos que o usuário pode acessar"
    )
    
    # Permissões específicas
    pode_executar_etl = models.BooleanField(
        _('Pode Executar ETL'),
        default=False,
        help_text="Pode executar comandos de ETL"
    )
    
    pode_administrar_usuarios = models.BooleanField(
        _('Pode Administrar Usuários'),
        default=False,
        help_text="Pode criar/editar usuários da contabilidade"
    )
    
    pode_ver_dados_sensiveis = models.BooleanField(
        _('Pode Ver Dados Sensíveis'),
        default=False,
        help_text="Pode visualizar dados sensíveis (salários, etc.)"
    )
    
    # Campos de segurança
    token_version = models.IntegerField(
        _('Versão do Token'),
        default=1,
        help_text="Versão do token para invalidação global"
    )
    
    mfa_enabled = models.BooleanField(
        _('MFA Habilitado'),
        default=False,
        help_text="Autenticação de dois fatores habilitada"
    )
    
    mfa_secret = models.CharField(
        _('Secret MFA'),
        max_length=32,
        blank=True,
        help_text="Chave secreta para MFA"
    )
    
    # Campos de auditoria
    data_ultima_atividade = models.DateTimeField(
        _('Última Atividade'),
        null=True, blank=True
    )
    
    ip_ultimo_acesso = models.GenericIPAddressField(
        _('IP do Último Acesso'),
        null=True, blank=True
    )
    
    # Fix para conflito de related_name
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('Groups'),
        blank=True,
        help_text=_('The groups this user belongs to.'),
        related_name='gestk_usuario_set',
        related_query_name='gestk_usuario',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('User permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='gestk_usuario_set',
        related_query_name='gestk_usuario',
    )
    
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = _('Usuário')
        verbose_name_plural = _('Usuários')
        db_table = 'core_usuarios'
        indexes = [
            models.Index(fields=['contabilidade', 'username']),
            models.Index(fields=['cpf']),
            models.Index(fields=['tipo_usuario']),
            models.Index(fields=['ativo']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.get_tipo_usuario_display()})"
    
    def tem_acesso_modulo(self, modulo):
        """Verifica se o usuário tem acesso a um módulo específico"""
        return modulo in self.modulos_acessiveis
    
    def pode_executar_comando_etl(self, comando):
        """Verifica se pode executar um comando ETL específico"""
        if not self.pode_executar_etl:
            return False
        
        # Lista de comandos ETL permitidos por tipo de usuário
        comandos_permitidos = {
            'superuser': ['*'],
            'admin': ['etl_*'],
            'etl': ['etl_*'],
        }
        
        return any(
            comando.startswith(permitido.replace('*', ''))
            for permitido in comandos_permitidos.get(self.tipo_usuario, [])
        )
    
    def is_superuser_gestk(self):
        """Verifica se é superusuário do GESTK (não apenas Django)"""
        return self.tipo_usuario == 'superuser'
    
    def is_admin_gestk(self):
        """Verifica se é administrador do GESTK"""
        return self.tipo_usuario == 'admin'
    
    def is_etl_user(self):
        """Verifica se é usuário de ETL"""
        return self.tipo_usuario == 'etl'
