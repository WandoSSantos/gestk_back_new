from rest_framework import serializers
from apps.core.models import Contabilidade, Usuario
from apps.pessoas.models import PessoaJuridica, PessoaFisica, Contrato
from apps.pessoas.models_quadro_societario import QuadroSocietario
from apps.contabil.models import LancamentoContabil, PlanoContas
from apps.fiscal.models import NotaFiscal
from apps.funcionarios.models import Funcionario
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta, date

class IndicadoresDemograficosSerializer(serializers.Serializer):
    """Serializer para indicadores demográficos"""
    total_colaboradores = serializers.IntegerField()
    colaboradores_ativos = serializers.IntegerField()
    colaboradores_inativos = serializers.IntegerField()
    turnover_mensal = serializers.FloatField()
    turnover_anual = serializers.FloatField()
    media_idade = serializers.FloatField()
    percentual_masculino = serializers.FloatField()
    percentual_feminino = serializers.FloatField()

class EvolucaoColaboradoresSerializer(serializers.Serializer):
    """Serializer para evolução mensal de colaboradores"""
    mes_ano = serializers.CharField()
    total_colaboradores = serializers.IntegerField()
    admissões = serializers.IntegerField()
    demissões = serializers.IntegerField()
    saldo_liquido = serializers.IntegerField()

class DistribuicaoEtariaSerializer(serializers.Serializer):
    """Serializer para distribuição etária"""
    faixa_etaria = serializers.CharField()
    total_colaboradores = serializers.IntegerField()
    percentual = serializers.FloatField()

class DistribuicaoEscolaridadeSerializer(serializers.Serializer):
    """Serializer para distribuição por escolaridade"""
    escolaridade = serializers.CharField()
    total_colaboradores = serializers.IntegerField()
    percentual = serializers.FloatField()

class DistribuicaoCargoSerializer(serializers.Serializer):
    """Serializer para distribuição por cargo"""
    cargo = serializers.CharField()
    total_colaboradores = serializers.IntegerField()
    percentual = serializers.FloatField()

class DistribuicaoGeneroSerializer(serializers.Serializer):
    """Serializer para distribuição por gênero"""
    genero = serializers.CharField()
    total_colaboradores = serializers.IntegerField()
    percentual = serializers.FloatField()

class IndicadoresFiscaisSerializer(serializers.Serializer):
    """Serializer para indicadores fiscais"""
    total_faturamento = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_impostos = serializers.DecimalField(max_digits=15, decimal_places=2)
    percentual_impostos = serializers.FloatField()
    total_notas_fiscais = serializers.IntegerField()
    media_valor_nota = serializers.DecimalField(max_digits=15, decimal_places=2)

class ProdutoServicoSerializer(serializers.Serializer):
    """Serializer para produtos/serviços mais relevantes"""
    descricao = serializers.CharField()
    total_vendas = serializers.DecimalField(max_digits=15, decimal_places=2)
    quantidade = serializers.IntegerField()
    percentual_faturamento = serializers.FloatField()

class ClienteFornecedorSerializer(serializers.Serializer):
    """Serializer para clientes/fornecedores relevantes"""
    nome = serializers.CharField()
    documento = serializers.CharField()
    total_transacoes = serializers.DecimalField(max_digits=15, decimal_places=2)
    quantidade_transacoes = serializers.IntegerField()
    percentual_faturamento = serializers.FloatField()

class GeolocalizacaoSerializer(serializers.Serializer):
    """Serializer para geolocalização por UF"""
    uf = serializers.CharField()
    total_faturamento = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_notas = serializers.IntegerField()
    percentual_faturamento = serializers.FloatField()

class ImpostoSerializer(serializers.Serializer):
    """Serializer para impostos devidos"""
    tipo_imposto = serializers.CharField()
    valor_devido = serializers.DecimalField(max_digits=15, decimal_places=2)
    percentual_faturamento = serializers.FloatField()

class IndicadoresContabeisSerializer(serializers.Serializer):
    """Serializer para indicadores contábeis"""
    total_ativo = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_passivo = serializers.DecimalField(max_digits=15, decimal_places=2)
    patrimonio_liquido = serializers.DecimalField(max_digits=15, decimal_places=2)
    receita_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    despesa_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    resultado_exercicio = serializers.DecimalField(max_digits=15, decimal_places=2)

class EvolucaoContabilSerializer(serializers.Serializer):
    """Serializer para evolução contábil mensal"""
    mes_ano = serializers.CharField()
    receita_mensal = serializers.DecimalField(max_digits=15, decimal_places=2)
    despesa_mensal = serializers.DecimalField(max_digits=15, decimal_places=2)
    resultado_mensal = serializers.DecimalField(max_digits=15, decimal_places=2)

class GrupoContaSerializer(serializers.Serializer):
    """Serializer para valor por grupo e conta"""
    grupo = serializers.CharField()
    conta = serializers.CharField()
    valor_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    percentual_total = serializers.FloatField()

class TopContaSerializer(serializers.Serializer):
    """Serializer para top 5 contas por valor"""
    conta = serializers.CharField()
    valor_total = serializers.DecimalField(max_digits=15, decimal_places=2)
    percentual_total = serializers.FloatField()
    natureza = serializers.CharField()

class IndicadoresFinanceirosSerializer(serializers.Serializer):
    """Serializer para indicadores financeiros"""
    liquidez_corrente = serializers.FloatField()
    liquidez_seca = serializers.FloatField()
    margem_bruta = serializers.FloatField()
    margem_liquida = serializers.FloatField()
    roe = serializers.FloatField()  # Return on Equity
    roi = serializers.FloatField()  # Return on Investment

class IndicadoresOperacionaisSerializer(serializers.Serializer):
    """Serializer para indicadores operacionais"""
    giro_estoque = serializers.FloatField()
    prazo_medio_recebimento = serializers.FloatField()
    prazo_medio_pagamento = serializers.FloatField()
    ciclo_operacional = serializers.FloatField()

class IndicadoresPatrimoniaisSerializer(serializers.Serializer):
    """Serializer para indicadores patrimoniais"""
    endividamento_total = serializers.FloatField()
    endividamento_curto_prazo = serializers.FloatField()
    composicao_endividamento = serializers.FloatField()
    imobilizacao_patrimonio = serializers.FloatField()

class DREComposicaoSerializer(serializers.Serializer):
    """Serializer para composição da DRE"""
    receita_bruta = serializers.DecimalField(max_digits=15, decimal_places=2)
    deducoes = serializers.DecimalField(max_digits=15, decimal_places=2)
    receita_liquida = serializers.DecimalField(max_digits=15, decimal_places=2)
    custo_mercadorias = serializers.DecimalField(max_digits=15, decimal_places=2)
    lucro_bruto = serializers.DecimalField(max_digits=15, decimal_places=2)
    despesas_operacionais = serializers.DecimalField(max_digits=15, decimal_places=2)
    resultado_operacional = serializers.DecimalField(max_digits=15, decimal_places=2)
    resultado_financeiro = serializers.DecimalField(max_digits=15, decimal_places=2)
    resultado_antes_ir = serializers.DecimalField(max_digits=15, decimal_places=2)
    imposto_renda = serializers.DecimalField(max_digits=15, decimal_places=2)
    resultado_liquido = serializers.DecimalField(max_digits=15, decimal_places=2)
