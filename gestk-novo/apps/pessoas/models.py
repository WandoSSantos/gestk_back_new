import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from simple_history.models import HistoricalRecords

class PessoaJuridica(models.Model):
    """Pessoas Jurídicas com isolamento por contabilidade"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    id_legado = models.CharField(_('ID Legado'), max_length=50, null=True, blank=True)
    matriz = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='filiais'
    )
    
    # Dados básicos
    cnpj = models.CharField(_('CNPJ'), max_length=14, unique=True)
    razao_social = models.CharField(_('Razão Social'), max_length=255)
    nome_fantasia = models.CharField(_('Nome Fantasia'), max_length=255, blank=True, null=True)
    
    # Endereço
    endereco = models.CharField(_('Endereço'), max_length=255, blank=True, null=True)
    numero = models.CharField(_('Número'), max_length=20, blank=True, null=True)
    complemento = models.CharField(_('Complemento'), max_length=100, blank=True, null=True)
    bairro = models.CharField(_('Bairro'), max_length=100, blank=True, null=True)
    cidade = models.CharField(_('Cidade'), max_length=100, blank=True, null=True)
    uf = models.CharField(_('UF'), max_length=2, blank=True, null=True)
    cep = models.CharField(_('CEP'), max_length=9, blank=True, null=True)
    pais = models.CharField(_('País'), max_length=100, blank=True, null=True, default='Brasil')
    
    # Contato
    telefone = models.CharField(_('Telefone'), max_length=20, blank=True, null=True)
    email = models.EmailField(_('E-mail'), blank=True, null=True)
    
    # Dados fiscais
    inscricao_estadual = models.CharField(_('Inscrição Estadual'), max_length=20, blank=True, null=True)
    inscricao_municipal = models.CharField(_('Inscrição Municipal'), max_length=20, blank=True, null=True)
    
    # Regime tributário
    REGIME_TRIBUTARIO_CHOICES = [
        ('1', 'Simples Nacional'),
        ('2', 'Lucro Presumido'),
        ('3', 'Lucro Real'),
        ('4', 'MEI - Microempreendedor Individual'),
    ]
    regime_tributario = models.CharField(
        _('Regime Tributário'), 
        max_length=1, 
        choices=REGIME_TRIBUTARIO_CHOICES,
        blank=True, 
        null=True
    )
    simples_nacional = models.BooleanField(_('Simples Nacional'), default=False)
    
    # Responsável legal
    responsavel_legal = models.CharField(_('Responsável Legal'), max_length=255, blank=True, null=True)
    cpf_responsavel = models.CharField(_('CPF do Responsável'), max_length=14, blank=True, null=True)
    
    # Dados empresariais
    data_inicio_atividades = models.DateField(_('Data de Início das Atividades'), blank=True, null=True)
    
    # CNAE
    cnae_principal = models.ForeignKey(
        'cadastros_gerais.CNAE', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='empresas_cnae_principal'
    )
    cnaes_secundarios = models.ManyToManyField(
        'cadastros_gerais.CNAE', 
        related_name='empresas_cnae_secundario', 
        blank=True
    )
    
    # Status
    ativo = models.BooleanField(_('Ativo'), default=True)
    created_at = models.DateTimeField(_('Data de Criação'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Data de Atualização'), auto_now=True)
    
    history = HistoricalRecords()
    
    @property
    def contrato_ativo(self):
        """
        Retorna a instância do contrato de serviço ativo para esta empresa.
        A lógica prioriza o contrato ativo mais recente sem data de término.
        """
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(self)
        hoje = timezone.now().date()
        
        # Busca contratos ativos sem data de término
        contratos = Contrato.objects.filter(
            content_type=content_type,
            object_id=self.id,
            ativo=True,
            data_inicio__lte=hoje,
            data_termino__isnull=True
        ).order_by('-data_inicio')

        # Se não encontrar, busca por contratos com data de término no futuro
        if not contratos.exists():
            contratos = Contrato.objects.filter(
                content_type=content_type,
                object_id=self.id,
                ativo=True,
                data_inicio__lte=hoje,
                data_termino__gte=hoje
            ).order_by('-data_inicio')

        return contratos.first()

    @property
    def contabilidade_atual(self):
        """
        Retorna a contabilidade atualmente responsável por esta empresa,
        com base no contrato ativo.
        """
        contrato = self.contrato_ativo
        if contrato:
            return contrato.contabilidade
        return None
    
    class Meta:
        verbose_name = _('Pessoa Jurídica')
        verbose_name_plural = _('Pessoas Jurídicas')
        db_table = 'pessoas_juridicas'
        ordering = ['razao_social']
        indexes = [
            models.Index(fields=['cnpj']),
            models.Index(fields=['razao_social']),
        ]
    
    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

class PessoaFisica(models.Model):
    """Pessoas Físicas com isolamento por contabilidade"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    id_legado = models.CharField(_('ID Legado'), max_length=50, null=True, blank=True)
    
    # Dados básicos
    cpf = models.CharField(_('CPF'), max_length=11, unique=True)
    nome_completo = models.CharField(_('Nome Completo'), max_length=255)
    data_nascimento = models.DateField(_('Data de Nascimento'), blank=True, null=True)
    
    # Endereço
    endereco = models.CharField(_('Endereço'), max_length=255, blank=True, null=True)
    numero = models.CharField(_('Número'), max_length=20, blank=True, null=True)
    complemento = models.CharField(_('Complemento'), max_length=100, blank=True, null=True)
    bairro = models.CharField(_('Bairro'), max_length=100, blank=True, null=True)
    cidade = models.CharField(_('Cidade'), max_length=100, blank=True, null=True)
    uf = models.CharField(_('UF'), max_length=2, blank=True, null=True)
    cep = models.CharField(_('CEP'), max_length=9, blank=True, null=True)
    
    # Contato
    telefone = models.CharField(_('Telefone'), max_length=20, blank=True, null=True)
    email = models.EmailField(_('E-mail'), blank=True, null=True)
    
    # Status
    ativo = models.BooleanField(_('Ativo'), default=True)
    created_at = models.DateTimeField(_('Data de Criação'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Data de Atualização'), auto_now=True)
    
    history = HistoricalRecords()
    
    @property
    def contrato_ativo(self):
        """
        Retorna a instância do contrato de serviço ativo para esta pessoa.
        A lógica prioriza o contrato ativo mais recente sem data de término.
        """
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(self)
        hoje = timezone.now().date()
        
        # Busca contratos ativos sem data de término
        contratos = Contrato.objects.filter(
            content_type=content_type,
            object_id=self.id,
            ativo=True,
            data_inicio__lte=hoje,
            data_termino__isnull=True
        ).order_by('-data_inicio')

        # Se não encontrar, busca por contratos com data de término no futuro
        if not contratos.exists():
            contratos = Contrato.objects.filter(
                content_type=content_type,
                object_id=self.id,
                ativo=True,
                data_inicio__lte=hoje,
                data_termino__gte=hoje
            ).order_by('-data_inicio')

        return contratos.first()

    @property
    def contabilidade_atual(self):
        """
        Retorna a contabilidade atualmente responsável por esta pessoa,
        com base no contrato ativo.
        """
        contrato = self.contrato_ativo
        if contrato:
            return contrato.contabilidade
        return None
    
    class Meta:
        verbose_name = _('Pessoa Física')
        verbose_name_plural = _('Pessoas Físicas')
        db_table = 'pessoas_fisicas'
        ordering = ['nome_completo']
        indexes = [
            models.Index(fields=['cpf']),
            models.Index(fields=['nome_completo']),
        ]
    
    def __str__(self):
        return f"{self.nome_completo} ({self.cpf})"


class Contrato(models.Model):
    """
    Representa o contrato de prestação de serviços entre uma Contabilidade e
    um cliente, que pode ser Pessoa Física ou Jurídica.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT, related_name='contratos')
    
    # Relação Genérica para o cliente
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.UUIDField()
    cliente = GenericForeignKey('content_type', 'object_id')
    
    # O id_legado do contrato deve ser único por contabilidade para garantir a idempotência
    id_legado = models.CharField(_('ID Legado do Contrato'), max_length=50, null=True, blank=True)
    
    data_inicio = models.DateField(_('Data de Início do Faturamento'), null=True, blank=True)
    data_termino = models.DateField(_('Data de Término do Contrato'), null=True, blank=True)
    dia_vencimento = models.IntegerField(_('Dia do Vencimento da Fatura'), null=True, blank=True)
    valor_honorario = models.DecimalField(_('Valor do Honorário'), max_digits=15, decimal_places=2, default=0)
    
    ativo = models.BooleanField(_('Ativo'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = _('Contrato')
        verbose_name_plural = _('Contratos')
        db_table = 'pessoas_contratos'
        unique_together = [('contabilidade', 'id_legado')]
        ordering = ['-created_at']
