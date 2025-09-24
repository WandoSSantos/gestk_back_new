"""
Modelos para Quadro Societário das Empresas

ETL 21 - Quadro Societário
Armazena informações de sócios, participações e quotas das empresas.
"""

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from .models import PessoaJuridica, PessoaFisica
import uuid


class QuadroSocietario(models.Model):
    """
    ETL 21 - Quadro Societário das Empresas
    
    Armazena informações de participação dos sócios nas empresas
    com relacionamento genérico para PF e PJ
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        PessoaJuridica,
        on_delete=models.CASCADE,
        related_name='quadro_societario',
        db_index=True,
        help_text="Empresa do quadro societário"
    )
    
    # Relacionamento genérico para sócio (PF ou PJ)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Tipo do sócio (PessoaFisica ou PessoaJuridica)"
    )
    object_id = models.UUIDField(help_text="ID do sócio")
    socio = GenericForeignKey('content_type', 'object_id')
    
    # Dados da participação
    participacao_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentual de participação do sócio"
    )
    quantidade_quotas = models.IntegerField(
        null=True,
        blank=True,
        help_text="Quantidade de quotas do sócio"
    )
    capital_social = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Capital social da empresa"
    )
    
    # Dados do Sybase
    id_legado_socio = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="ID do sócio no sistema legado"
    )
    id_legado_empresa = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="ID da empresa no sistema legado"
    )
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['empresa', 'ativo']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['id_legado_empresa', 'id_legado_socio']),
            models.Index(fields=['data_criacao']),
        ]
        unique_together = ['empresa', 'content_type', 'object_id']
        verbose_name = 'Quadro Societário'
        verbose_name_plural = 'Quadros Societários'
    
    def __str__(self):
        socio_nome = self.get_socio_nome()
        return f"{self.empresa.nome_fantasia} - {socio_nome} ({self.participacao_percentual}%)"
    
    def get_socio_nome(self):
        """Retorna o nome do sócio baseado no tipo"""
        if self.socio:
            if hasattr(self.socio, 'nome_completo'):
                return self.socio.nome_completo
            elif hasattr(self.socio, 'razao_social'):
                return self.socio.razao_social
        return "Sócio não encontrado"
    
    def get_socio_documento(self):
        """Retorna o documento do sócio"""
        if self.socio:
            if hasattr(self.socio, 'cpf'):
                return self.socio.cpf
            elif hasattr(self.socio, 'cnpj'):
                return self.socio.cnpj
        return None
    
    def get_socio_tipo(self):
        """Retorna o tipo do sócio"""
        if self.socio:
            if hasattr(self.socio, 'cpf'):
                return 'Pessoa Física'
            elif hasattr(self.socio, 'cnpj'):
                return 'Pessoa Jurídica'
        return 'Desconhecido'


class CapitalSocial(models.Model):
    """
    ETL 21 - Capital Social das Empresas
    
    Armazena histórico do capital social das empresas
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        PessoaJuridica,
        on_delete=models.CASCADE,
        related_name='capital_social_historico',
        db_index=True,
        help_text="Empresa do capital social"
    )
    valor_capital = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Valor do capital social"
    )
    data_referencia = models.DateField(
        db_index=True,
        help_text="Data de referência do capital social"
    )
    fonte = models.CharField(
        max_length=50,
        default='QUADRO_SOCIETARIO',
        help_text="Fonte dos dados (QUADRO_SOCIETARIO, CONTRATO, etc.)"
    )
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['empresa', 'data_referencia']),
            models.Index(fields=['data_referencia']),
            models.Index(fields=['fonte']),
        ]
        unique_together = ['empresa', 'data_referencia', 'fonte']
        verbose_name = 'Capital Social'
        verbose_name_plural = 'Capitais Sociais'
        ordering = ['-data_referencia']
    
    def __str__(self):
        return f"{self.empresa.nome_fantasia} - R$ {self.valor_capital:,.2f} ({self.data_referencia})"
