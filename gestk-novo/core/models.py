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
    """Usuário do sistema com referência obrigatória à contabilidade (tenant)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey(
        Contabilidade, 
        on_delete=models.CASCADE,
        related_name='usuarios',
        verbose_name=_('Contabilidade')
    )
    cpf = models.CharField(_('CPF'), max_length=11, unique=True)
    ativo = models.BooleanField(_('Ativo'), default=True)
    
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = _('Usuário')
        verbose_name_plural = _('Usuários')
        db_table = 'core_usuarios'
        indexes = [
            models.Index(fields=['contabilidade', 'username']),
            models.Index(fields=['cpf']),
        ]
