"""
Modelos CORRIGIDOS para ETL 19 - Logs Unificados (NORMALIZADOS)
Importação de atividades, importações e lançamentos por usuário
"""

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from apps.core.models import Contabilidade
from apps.pessoas.models import PessoaJuridica, PessoaFisica
import uuid


class BaseModeloMultitenant(models.Model):
    """
    Modelo base para todas as tabelas de administração
    
    Características:
    - contabilidade_id obrigatório para isolamento multitenant
    - Índices otimizados para performance
    - Validações de integridade
    - Auditoria automática
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey(
        Contabilidade, 
        on_delete=models.CASCADE,
        db_index=True,
        help_text="Contabilidade responsável pelos dados"
    )
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['contabilidade', 'data_criacao']),
        ]


class LogAtividade(BaseModeloMultitenant):
    """
    ETL 19 - Logs de atividades dos usuários (GELOGUSER) - NORMALIZADO
    
    Mapeia logs do GELOGUSER para o sistema GESTK
    com relacionamentos adequados e isolamento multitenant rigoroso
    """
    id_legado = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="ID único do log no sistema legado (usua_log + data_log + tini_log)"
    )
    usuario = models.ForeignKey(
        'administracao.Usuario',
        on_delete=models.CASCADE,
        db_index=True,
        help_text="Usuário que realizou a atividade"
    )
    empresa = models.ForeignKey(
        PessoaJuridica,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        help_text="Empresa relacionada à atividade"
    )
    data_atividade = models.DateField(
        db_index=True,
        help_text="Data da atividade (data_log)"
    )
    hora_inicial = models.TimeField(
        help_text="Hora de início da atividade (tini_log)"
    )
    hora_final = models.TimeField(
        null=True, 
        blank=True,
        help_text="Hora de fim da atividade (tfim_log)"
    )
    data_fim = models.DateField(
        null=True, 
        blank=True,
        db_index=True,
        help_text="Data de fim da atividade (dfim_log)"
    )
    sistema_modulo = models.IntegerField(
        null=True, 
        blank=True,
        db_index=True,
        help_text="Sistema/módulo acessado (sist_log)"
    )
    tempo_sessao_minutos = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Tempo total da atividade em minutos (calculado)"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['contabilidade', 'usuario', 'data_atividade']),
            models.Index(fields=['contabilidade', 'empresa', 'data_atividade']),
            models.Index(fields=['usuario', 'data_atividade']),
            models.Index(fields=['sistema_modulo', 'data_atividade']),
            models.Index(fields=['empresa', 'data_atividade']),
        ]
        unique_together = ['contabilidade', 'id_legado']
        verbose_name = 'Log de Atividade'
        verbose_name_plural = 'Logs de Atividade'
    
    def __str__(self):
        return f"{self.usuario.nome_usuario} - {self.empresa.nome_fantasia if self.empresa else 'N/A'} - {self.data_atividade}"


class LogImportacao(BaseModeloMultitenant):
    """
    ETL 19 - Logs de importações (EFSAIDAS, EFENTRADAS, EFSERVICOS) - NORMALIZADO
    
    Registra importações realizadas pelos usuários
    com relacionamentos adequados e agrupamento por tipo e período
    """
    id_legado = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="ID único da importação no sistema legado"
    )
    usuario = models.ForeignKey(
        'administracao.Usuario',
        on_delete=models.CASCADE,
        db_index=True,
        help_text="Usuário que realizou a importação"
    )
    empresa = models.ForeignKey(
        PessoaJuridica,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        help_text="Empresa relacionada à importação"
    )
    tipo_importacao = models.CharField(
        max_length=20,
        db_index=True,
        choices=[
            ('SAIDA', 'Saída'),
            ('ENTRADA', 'Entrada'),
            ('SERVICO', 'Serviço'),
        ],
        help_text="Tipo da importação realizada"
    )
    data_importacao = models.DateField(
        db_index=True,
        help_text="Data da importação"
    )
    quantidade_registros = models.IntegerField(
        default=1,
        help_text="Quantidade de registros importados"
    )
    valor_total = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Valor total da importação"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['contabilidade', 'usuario', 'data_importacao']),
            models.Index(fields=['contabilidade', 'tipo_importacao', 'data_importacao']),
            models.Index(fields=['usuario', 'tipo_importacao', 'data_importacao']),
            models.Index(fields=['empresa', 'data_importacao']),
        ]
        unique_together = ['contabilidade', 'id_legado']
        verbose_name = 'Log de Importação'
        verbose_name_plural = 'Logs de Importação'
    
    def __str__(self):
        return f"{self.usuario.nome_usuario} - {self.tipo_importacao} - {self.empresa.nome_fantasia if self.empresa else 'N/A'} - {self.data_importacao}"


class LogLancamento(BaseModeloMultitenant):
    """
    ETL 19 - Logs de lançamentos contábeis (CTLANCTO) - NORMALIZADO
    
    Registra lançamentos realizados pelos usuários
    com relacionamentos adequados e auditoria completa
    """
    id_legado = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="ID único do lançamento no sistema legado"
    )
    usuario = models.ForeignKey(
        'administracao.Usuario',
        on_delete=models.CASCADE,
        db_index=True,
        help_text="Usuário que realizou o lançamento"
    )
    empresa = models.ForeignKey(
        PessoaJuridica,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        help_text="Empresa relacionada ao lançamento"
    )
    data_lancamento = models.DateField(
        db_index=True,
        help_text="Data do lançamento (data_lan)"
    )
    origem_registro = models.IntegerField(
        db_index=True,
        help_text="Origem do registro (origem_reg: 0=automático, !=0=manual)"
    )
    tipo_operacao = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Tipo da operação realizada"
    )
    valor = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Valor do lançamento (vlor_lan)"
    )
    conta_debito = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Conta de débito (cdeb_lan)"
    )
    conta_credito = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Conta de crédito (ccre_lan)"
    )
    historico = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Histórico do lançamento (chis_lan)"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['contabilidade', 'usuario', 'data_lancamento']),
            models.Index(fields=['contabilidade', 'data_lancamento']),
            models.Index(fields=['usuario', 'data_lancamento']),
            models.Index(fields=['origem_registro', 'data_lancamento']),
            models.Index(fields=['empresa', 'data_lancamento']),
        ]
        unique_together = ['contabilidade', 'id_legado']
        verbose_name = 'Log de Lançamento'
        verbose_name_plural = 'Logs de Lançamento'
    
    def __str__(self):
        return f"{self.usuario.nome_usuario} - {self.empresa.nome_fantasia if self.empresa else 'N/A'} - {self.data_lancamento} - {self.tipo_operacao or 'Lançamento'}"


class EstatisticaUsuario(BaseModeloMultitenant):
    """
    Tabela de estatísticas consolidadas por usuário e empresa - NORMALIZADO
    
    Agrega dados de atividades, importações e lançamentos
    para consultas rápidas e relatórios
    """
    usuario = models.ForeignKey(
        'administracao.Usuario',
        on_delete=models.CASCADE,
        db_index=True,
        help_text="Usuário das estatísticas"
    )
    empresa = models.ForeignKey(
        PessoaJuridica,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        help_text="Empresa das estatísticas"
    )
    periodo_referencia = models.DateField(
        db_index=True,
        help_text="Período de referência das estatísticas (YYYY-MM-01)"
    )
    
    # Estatísticas de Atividades
    total_atividades = models.IntegerField(default=0)
    tempo_total_minutos = models.IntegerField(default=0)
    modulos_acessados = models.JSONField(default=list)
    
    # Estatísticas de Importações
    total_importacoes = models.IntegerField(default=0)
    importacoes_saidas = models.IntegerField(default=0)
    importacoes_entradas = models.IntegerField(default=0)
    importacoes_servicos = models.IntegerField(default=0)
    valor_total_importacoes = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Estatísticas de Lançamentos
    total_lancamentos = models.IntegerField(default=0)
    lancamentos_manuais = models.IntegerField(default=0)
    lancamentos_automaticos = models.IntegerField(default=0)
    valor_total_lancamentos = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['contabilidade', 'usuario', 'periodo_referencia']),
            models.Index(fields=['contabilidade', 'empresa', 'periodo_referencia']),
            models.Index(fields=['usuario', 'periodo_referencia']),
            models.Index(fields=['empresa', 'periodo_referencia']),
        ]
        unique_together = ['contabilidade', 'usuario', 'empresa', 'periodo_referencia']
        verbose_name = 'Estatística do Usuário'
        verbose_name_plural = 'Estatísticas dos Usuários'
    
    def __str__(self):
        return f"{self.usuario.nome_usuario} - {self.empresa.nome_fantasia if self.empresa else 'Geral'} - {self.periodo_referencia}"
