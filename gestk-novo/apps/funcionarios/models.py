import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords
from django.contrib.contenttypes.fields import GenericForeignKey

# -----------------------------------------------------------------------------
# CADASTROS AUXILIARES DE RH
# -----------------------------------------------------------------------------

class Sindicato(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT)
    nome = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=14, null=True, blank=True)
    ativo = models.BooleanField(default=True)
    # history removido

class ConvencaoColetiva(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT)
    sindicato = models.ForeignKey(Sindicato, on_delete=models.PROTECT)
    descricao = models.CharField(max_length=255)
    vigencia_inicio = models.DateField()
    vigencia_fim = models.DateField()
    ativo = models.BooleanField(default=True)
    # history removido

class Cargo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT)
    id_legado = models.CharField(_('ID Legado'), max_length=50, null=True, blank=True)
    empresa = models.ForeignKey('pessoas.PessoaJuridica', on_delete=models.PROTECT, null=True, blank=True)
    nome = models.CharField(max_length=255)
    cbo_2002 = models.CharField(max_length=10, null=True, blank=True)
    ativo = models.BooleanField(default=True)
    # history removido

class Departamento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT)
    id_legado = models.CharField(_('ID Legado'), max_length=50, null=True, blank=True)
    empresa = models.ForeignKey('pessoas.PessoaJuridica', on_delete=models.PROTECT, null=True, blank=True)
    nome = models.CharField(max_length=255)
    ativo = models.BooleanField(default=True)
    # history removido

class CentroCusto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT)
    id_legado = models.CharField(_('ID Legado'), max_length=50, null=True, blank=True)
    empresa = models.ForeignKey('pessoas.PessoaJuridica', on_delete=models.PROTECT, null=True, blank=True)
    nome = models.CharField(max_length=255)
    ativo = models.BooleanField(default=True)
    # history removido

# ... e assim por diante para todos os modelos de RH ...

# -----------------------------------------------------------------------------
# ESTRUTURA CENTRAL DO FUNCIONÁRIO
# -----------------------------------------------------------------------------

class Funcionario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT)
    pessoa_fisica = models.ForeignKey('pessoas.PessoaFisica', on_delete=models.PROTECT)
    id_legado = models.CharField(max_length=50, null=True, blank=True)
    ativo = models.BooleanField(default=True)
    # history removido

    class Meta:
        unique_together = ('contabilidade', 'pessoa_fisica', 'id_legado')

class VinculoEmpregaticio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.PROTECT, related_name='vinculos')
    
    # Relação Genérica para a Empresa (Empregador)
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.PROTECT, null=True)
    object_id = models.UUIDField(null=True)
    empresa = GenericForeignKey('content_type', 'object_id')

    matricula = models.CharField(max_length=20)
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT)
    departamento = models.ForeignKey(Departamento, on_delete=models.PROTECT, null=True, blank=True)
    data_admissao = models.DateField()
    data_demissao = models.DateField(null=True, blank=True)
    salario_base = models.DecimalField(max_digits=15, decimal_places=2)
    ativo = models.BooleanField(default=True)
    # history removido
    
# -----------------------------------------------------------------------------
# GESTÃO DE FÉRIAS E RESCISÃO
# -----------------------------------------------------------------------------

class Ferias(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vinculo = models.ForeignKey(VinculoEmpregaticio, on_delete=models.PROTECT, related_name='ferias')
    periodo_aquisitivo_inicio = models.DateField()
    periodo_aquisitivo_fim = models.DateField()
    data_inicio_gozo = models.DateField()
    dias_gozo = models.IntegerField()
    status = models.CharField(max_length=20)
    # history removido

class Rescisao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT, related_name='rescisoes')
    vinculo = models.OneToOneField('VinculoEmpregaticio', on_delete=models.PROTECT, related_name='rescisao')
    data_rescisao = models.DateField()
    motivo_codigo = models.CharField(max_length=10)
    salario_base = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    proventos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    descontos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    valor_liquido = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fgts = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    irrf = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    aviso_previo = models.CharField(max_length=20, null=True, blank=True)
    data_aviso = models.DateField(null=True, blank=True)
    aviso_indenizado = models.BooleanField(default=False)
    data_pagamento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20)
    observacoes = models.TextField(null=True, blank=True)
    id_legado = models.CharField(max_length=50, null=True, blank=True)
    # history removido

    class Meta:
        verbose_name = 'Rescisão'
        verbose_name_plural = 'Rescisões'
        unique_together = ('contabilidade', 'vinculo')

class HistoricoSalario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vinculo = models.ForeignKey('VinculoEmpregaticio', on_delete=models.PROTECT, related_name='historico_salarios')
    salario_novo = models.DecimalField(max_digits=15, decimal_places=2)
    data_mudanca = models.DateField()
    motivo = models.CharField(max_length=255, null=True, blank=True)
    # history removido

class HistoricoCargo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vinculo = models.ForeignKey('VinculoEmpregaticio', on_delete=models.PROTECT, related_name='historico_cargos')
    cargo_novo = models.ForeignKey('Cargo', on_delete=models.PROTECT)
    data_mudanca = models.DateField()
    # history removido

class Rubrica(models.Model):
    TIPO_CHOICES = [
        ('P', 'Provento'),
        ('D', 'Desconto'),
        ('B', 'Base'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.PROTECT)
    id_legado = models.CharField(_('ID Legado'), max_length=50, null=True, blank=True)
    nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    incide_inss = models.BooleanField(default=False)
    incide_irrf = models.BooleanField(default=False)
    incide_fgts = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    # history removido

    class Meta:
        unique_together = ('contabilidade', 'id_legado')

class RescisaoRubrica(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rescisao = models.ForeignKey('Rescisao', on_delete=models.CASCADE, related_name='rubricas')
    rubrica = models.ForeignKey('Rubrica', on_delete=models.PROTECT)
    tipo = models.CharField(max_length=1, choices=Rubrica.TIPO_CHOICES)
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        verbose_name = 'Rubrica de Rescisão'
        verbose_name_plural = 'Rubricas de Rescisão'
        unique_together = ('rescisao', 'rubrica', 'tipo', 'descricao')

class PeriodoAquisitivoFerias(models.Model):
    SITUACAO_CHOICES = [
        ('A', 'Aberto'),
        ('F', 'Fechado'),
        ('P', 'Programado'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vinculo = models.ForeignKey(VinculoEmpregaticio, on_delete=models.PROTECT, related_name='periodos_aquisitivos')
    id_legado = models.CharField(_('ID Legado'), max_length=50)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    dias_direito = models.IntegerField(default=30)
    situacao = models.CharField(max_length=1, choices=SITUACAO_CHOICES, default='A')
    # history removido

    class Meta:
        unique_together = ('vinculo', 'id_legado')

class GozoFerias(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    periodo_aquisitivo = models.ForeignKey(PeriodoAquisitivoFerias, on_delete=models.CASCADE, related_name='gozos')
    id_legado = models.CharField(max_length=255)
    
    # Datas
    data_inicio_gozo = models.DateField(null=True, blank=True)
    data_fim_gozo = models.DateField(null=True, blank=True)
    dias_gozo = models.IntegerField(default=0)
    dias_abono = models.IntegerField(default=0)

    # Valores (podem ser expandidos conforme necessidade)
    valor_ferias = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    valor_abono = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # history removido
    
    class Meta:
        verbose_name = 'Gozo de Férias'
        verbose_name_plural = 'Gozos de Férias'
        unique_together = ('periodo_aquisitivo', 'id_legado')


class Afastamento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.CASCADE, related_name='afastamentos')
    vinculo = models.ForeignKey(VinculoEmpregaticio, on_delete=models.CASCADE, related_name='afastamentos')
    id_legado = models.CharField(max_length=255) # I_AFASTAMENTOS do Sybase

    # Datas
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    previsao_fim = models.DateField(null=True, blank=True) # DATA_FIM_TMP
    dias_afastado = models.IntegerField(default=0, help_text="Número de dias do afastamento.")

    # Motivo (simplificado por enquanto, podemos criar um model separado depois)
    motivo_afastamento = models.CharField(max_length=255, null=True, blank=True) # Mapear de I_AFASTAMENTOS para uma descrição
    codigo_doenca = models.CharField(max_length=50, null=True, blank=True, help_text="CID")

    # Atestado Médico
    nome_medico = models.CharField(max_length=255, null=True, blank=True)
    crm_medico = models.CharField(max_length=50, null=True, blank=True)

    observacoes = models.TextField(null=True, blank=True)

    # Campos de auditoria
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    # history removido

    class Meta:
        verbose_name = 'Afastamento'
        verbose_name_plural = 'Afastamentos'
        ordering = ['-data_inicio']
        unique_together = ('contabilidade', 'vinculo', 'id_legado')

    def __str__(self):
        return f"Afastamento de {self.vinculo.funcionario.pessoa_fisica.nome_razao_social} a partir de {self.data_inicio}"
