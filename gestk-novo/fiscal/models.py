import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

class NotaFiscal(models.Model):
    """Modelo para notas fiscais de entrada, saída e serviços."""
    TIPO_CHOICES = [
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída'),
        ('SERVICO', 'Serviço'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT, related_name='notas_fiscais')
    
    # Parceiros específicos para PJ e PF (apenas um deve estar preenchido)
    parceiro_pj = models.ForeignKey('pessoas.PessoaJuridica', on_delete=models.PROTECT, null=True, blank=True, related_name='notas_fiscais')
    parceiro_pf = models.ForeignKey('pessoas.PessoaFisica', on_delete=models.PROTECT, null=True, blank=True, related_name='notas_fiscais')

    tipo_nota = models.CharField(_('Tipo de Nota'), max_length=10, choices=TIPO_CHOICES)
    chave_acesso = models.CharField(_('Chave de Acesso'), max_length=44, unique=True, null=True, blank=True)
    numero_documento = models.CharField(_('Número do Documento'), max_length=20)
    serie = models.CharField(_('Série'), max_length=10)
    data_emissao = models.DateTimeField(_('Data de Emissão'))
    data_entrada_saida = models.DateField(_('Data de Entrada/Saída'), null=True, blank=True)
    
    valor_total = models.DecimalField(_('Valor Total da Nota'), max_digits=15, decimal_places=2)
    situacao = models.CharField(_('Situação'), max_length=50, blank=True, null=True)
    
    # Campos para idempotência do ETL
    id_legado_nota = models.CharField(_('ID Legado da Nota'), max_length=50, null=True, blank=True)
    id_legado_empresa = models.CharField(_('ID Legado da Empresa'), max_length=50, null=True, blank=True)
    id_legado_cli_for = models.CharField(_('ID Legado Cliente/Fornecedor'), max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    @property
    def parceiro(self):
        """Retorna o parceiro (PJ ou PF) que está preenchido."""
        return self.parceiro_pj or self.parceiro_pf
    
    def clean(self):
        """Valida que apenas um tipo de parceiro está preenchido."""
        from django.core.exceptions import ValidationError
        if self.parceiro_pj and self.parceiro_pf:
            raise ValidationError("Não é possível ter parceiro PJ e PF ao mesmo tempo.")
        if not self.parceiro_pj and not self.parceiro_pf:
            raise ValidationError("É necessário informar um parceiro (PJ ou PF).")

    class Meta:
        verbose_name = _('Nota Fiscal')
        verbose_name_plural = _('Notas Fiscais')
        db_table = 'fiscal_notas_fiscais'
        indexes = [
            models.Index(fields=['contabilidade', 'parceiro_pj']),
            models.Index(fields=['contabilidade', 'parceiro_pf']),
            models.Index(fields=['contabilidade', 'data_emissao']),
            models.Index(fields=['chave_acesso']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(parceiro_pj__isnull=False) | models.Q(parceiro_pf__isnull=False),
                name='fiscal_notafiscal_tem_parceiro'
            ),
            models.CheckConstraint(
                check=~(models.Q(parceiro_pj__isnull=False) & models.Q(parceiro_pf__isnull=False)),
                name='fiscal_notafiscal_apenas_um_parceiro'
            ),
        ]
        

class NotaFiscalItem(models.Model):
    """Itens de uma nota fiscal, podendo ser produtos ou serviços."""
    TIPO_ITEM_CHOICES = [
        ('PRODUTO', 'Produto'),
        ('SERVICO', 'Serviço'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nota_fiscal = models.ForeignKey(NotaFiscal, on_delete=models.CASCADE, related_name='itens')

    # Campo para idempotência do ETL
    sequencial_item = models.IntegerField(_('Sequencial do Item no Legado'), null=True, blank=True)

    tipo_item = models.CharField(_('Tipo do Item'), max_length=10, choices=TIPO_ITEM_CHOICES)
    descricao = models.CharField(_('Descrição'), max_length=255)
    
    cfop = models.CharField(_('CFOP'), max_length=10, null=True, blank=True)
    cst = models.CharField(_('CST'), max_length=10, null=True, blank=True)
    ncm = models.CharField(_('NCM'), max_length=10, null=True, blank=True, help_text="Nomenclatura Comum do Mercosul. Nulo para serviços.")
    
    quantidade = models.DecimalField(_('Quantidade'), max_digits=15, decimal_places=4)
    valor_unitario = models.DecimalField(_('Valor Unitário'), max_digits=15, decimal_places=4)
    valor_total = models.DecimalField(_('Valor Total do Item'), max_digits=15, decimal_places=2)

    # Campos Fiscais Adicionais da Documentação
    base_icms = models.DecimalField(_('Base de Cálculo ICMS'), max_digits=15, decimal_places=2, default=0)
    aliquota_icms = models.DecimalField(_('Alíquota ICMS'), max_digits=5, decimal_places=2, default=0)
    valor_icms = models.DecimalField(_('Valor do ICMS'), max_digits=15, decimal_places=2, default=0)
    base_icms_st = models.DecimalField(_('Base de Cálculo ICMS ST'), max_digits=15, decimal_places=2, default=0)
    aliquota_icms_st = models.DecimalField(_('Alíquota ICMS ST'), max_digits=5, decimal_places=2, default=0)
    valor_icms_st = models.DecimalField(_('Valor do ICMS ST'), max_digits=15, decimal_places=2, default=0)
    
    base_ipi = models.DecimalField(_('Base de Cálculo IPI'), max_digits=15, decimal_places=2, default=0)
    aliquota_ipi = models.DecimalField(_('Alíquota IPI'), max_digits=5, decimal_places=2, default=0)
    valor_ipi = models.DecimalField(_('Valor do IPI'), max_digits=15, decimal_places=2, default=0)

    base_pis = models.DecimalField(_('Base de Cálculo PIS'), max_digits=15, decimal_places=2, default=0)
    aliquota_pis = models.DecimalField(_('Alíquota PIS'), max_digits=5, decimal_places=2, default=0)
    valor_pis = models.DecimalField(_('Valor do PIS'), max_digits=15, decimal_places=2, default=0)
    cst_pis = models.CharField(_('CST PIS'), max_length=10, null=True, blank=True)

    base_cofins = models.DecimalField(_('Base de Cálculo COFINS'), max_digits=15, decimal_places=2, default=0)
    aliquota_cofins = models.DecimalField(_('Alíquota COFINS'), max_digits=5, decimal_places=2, default=0)
    valor_cofins = models.DecimalField(_('Valor do COFINS'), max_digits=15, decimal_places=2, default=0)
    cst_cofins = models.CharField(_('CST COFINS'), max_length=10, null=True, blank=True)

    valor_desconto = models.DecimalField(_('Valor do Desconto'), max_digits=15, decimal_places=2, default=0)
    valor_frete = models.DecimalField(_('Valor do Frete'), max_digits=15, decimal_places=2, default=0)
    valor_seguro = models.DecimalField(_('Valor do Seguro'), max_digits=15, decimal_places=2, default=0)
    valor_outras_despesas = models.DecimalField(_('Outras Despesas Acessórias'), max_digits=15, decimal_places=2, default=0)

    informacoes_adicionais = models.TextField(_('Informações Adicionais'), null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = _('Item da Nota Fiscal')
        verbose_name_plural = _('Itens da Nota Fiscal')
        db_table = 'fiscal_notas_fiscais_itens'
        unique_together = ('nota_fiscal', 'sequencial_item') # Garante que não haja sequenciais repetidos na mesma nota
