import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

class PlanoContas(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT, related_name='planos_contas')
    id_legado = models.CharField(_('ID Legado'), max_length=50, null=True, blank=True)
    codigo = models.CharField(_('Código'), max_length=50)
    nome = models.CharField(_('Nome'), max_length=255)
    conta_pai = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='contas_filhas')
    nivel = models.IntegerField(_('Nível'))
    aceita_lancamento = models.BooleanField(_('Aceita Lançamento'), default=True)
    tipo_conta = models.CharField(_('Tipo de Conta'), max_length=20) # ANALITICA, SINTETICA
    natureza = models.CharField(_('Natureza'), max_length=10) # DEVEDORA, CREDORA
    ativo = models.BooleanField(_('Ativo'), default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = _('Plano de Conta')
        verbose_name_plural = _('Planos de Contas')
        db_table = 'contabil_plano_contas'
        unique_together = ('contabilidade', 'codigo')

class LancamentoContabil(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT, related_name='lancamentos_contabeis')
    contrato = models.ForeignKey('pessoas.Contrato', on_delete=models.PROTECT, related_name='lancamentos_contabeis', null=True, blank=True)
    numero_lancamento = models.CharField(_('Número do Lançamento'), max_length=50)
    data_lancamento = models.DateField(_('Data do Lançamento'))
    historico = models.TextField(_('Histórico'))
    valor_total = models.DecimalField(_('Valor Total'), max_digits=15, decimal_places=2)
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = _('Lançamento Contábil')
        verbose_name_plural = _('Lançamentos Contábeis')
        db_table = 'contabil_lancamentos'
        indexes = [
            models.Index(fields=['contabilidade', 'data_lancamento']),
        ]

class Partida(models.Model):
    TIPO_CHOICES = [
        ('D', 'Débito'),
        ('C', 'Crédito'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lancamento = models.ForeignKey(LancamentoContabil, on_delete=models.CASCADE, related_name='partidas')
    conta = models.ForeignKey(PlanoContas, on_delete=models.PROTECT, related_name='partidas')
    tipo = models.CharField(_('Tipo'), max_length=1, choices=TIPO_CHOICES)
    valor = models.DecimalField(_('Valor'), max_digits=15, decimal_places=2)
    history = HistoricalRecords()

    class Meta:
        verbose_name = _('Partida')
        verbose_name_plural = _('Partidas')
        db_table = 'contabil_partidas'
