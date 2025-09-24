from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import timedelta, date
from django.contrib.contenttypes.models import ContentType

from apps.core.models import Contabilidade, Usuario
from apps.pessoas.models import PessoaJuridica, PessoaFisica, Contrato
from apps.pessoas.models_quadro_societario import QuadroSocietario
from apps.contabil.models import LancamentoContabil, PlanoContas
from apps.fiscal.models import NotaFiscal
from apps.funcionarios.models import Funcionario
from .serializers import (
    IndicadoresDemograficosSerializer, EvolucaoColaboradoresSerializer,
    DistribuicaoEtariaSerializer, DistribuicaoEscolaridadeSerializer,
    DistribuicaoCargoSerializer, DistribuicaoGeneroSerializer,
    IndicadoresFiscaisSerializer, ProdutoServicoSerializer,
    ClienteFornecedorSerializer, GeolocalizacaoSerializer,
    ImpostoSerializer, IndicadoresContabeisSerializer,
    EvolucaoContabilSerializer, GrupoContaSerializer,
    TopContaSerializer, IndicadoresFinanceirosSerializer,
    IndicadoresOperacionaisSerializer, IndicadoresPatrimoniaisSerializer,
    DREComposicaoSerializer
)

class DemograficoViewSet(viewsets.ViewSet):
    """ViewSet para dashboards demográficos"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def indicadores(self, request):
        """
        Endpoint para indicadores demográficos gerais (Turnover, etc.) (RF01)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar funcionários da contabilidade
            funcionarios = Funcionario.objects.filter(contabilidade=contabilidade)
            
            # Calcular indicadores básicos
            total_colaboradores = funcionarios.count()
            colaboradores_ativos = funcionarios.filter(ativo=True).count()
            colaboradores_inativos = total_colaboradores - colaboradores_ativos
            
            # Calcular turnover mensal (simulado)
            data_limite = timezone.now().date() - timedelta(days=30)
            admissões_mes = funcionarios.filter(
                data_admissao__gte=data_limite
            ).count()
            demissões_mes = funcionarios.filter(
                data_demissao__gte=data_limite
            ).count()
            
            turnover_mensal = (demissões_mes / max(total_colaboradores, 1)) * 100
            
            # Calcular turnover anual (simulado)
            data_limite_ano = timezone.now().date() - timedelta(days=365)
            admissões_ano = funcionarios.filter(
                data_admissao__gte=data_limite_ano
            ).count()
            demissões_ano = funcionarios.filter(
                data_demissao__gte=data_limite_ano
            ).count()
            
            turnover_anual = (demissões_ano / max(total_colaboradores, 1)) * 100
            
            # Calcular média de idade (simulado)
            media_idade = 35.0  # Simulado
            
            # Calcular distribuição por gênero (simulado)
            percentual_masculino = 60.0  # Simulado
            percentual_feminino = 40.0   # Simulado

            data = {
                'total_colaboradores': total_colaboradores,
                'colaboradores_ativos': colaboradores_ativos,
                'colaboradores_inativos': colaboradores_inativos,
                'turnover_mensal': round(turnover_mensal, 2),
                'turnover_anual': round(turnover_anual, 2),
                'media_idade': media_idade,
                'percentual_masculino': percentual_masculino,
                'percentual_feminino': percentual_feminino
            }

            serializer = IndicadoresDemograficosSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar indicadores demográficos: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def colaboradores(self, request):
        """
        Endpoint para evolução mensal de colaboradores (RF02)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular dados de evolução mensal dos últimos 12 meses
            evolucao_data = []
            for i in range(12):
                month = timezone.now().date() - timedelta(days=30 * i)
                month_str = month.strftime('%Y-%m')
                
                # Simular dados baseados nos funcionários existentes
                total_colaboradores = Funcionario.objects.filter(
                    contabilidade=contabilidade,
                    data_admissao__lte=month
                ).count()
                
                admissões = Funcionario.objects.filter(
                    contabilidade=contabilidade,
                    data_admissao__year=month.year,
                    data_admissao__month=month.month
                ).count()
                
                demissões = Funcionario.objects.filter(
                    contabilidade=contabilidade,
                    data_demissao__year=month.year,
                    data_demissao__month=month.month
                ).count()
                
                saldo_liquido = admissões - demissões
                
                evolucao_data.append({
                    'mes_ano': month_str,
                    'total_colaboradores': total_colaboradores,
                    'admissões': admissões,
                    'demissões': demissões,
                    'saldo_liquido': saldo_liquido
                })
            
            # Inverter para ordem cronológica crescente
            evolucao_data.reverse()

            serializer = EvolucaoColaboradoresSerializer(evolucao_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar evolução de colaboradores: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def distribuicoes(self, request):
        """
        Endpoint para distribuições etária, escolaridade, cargo, gênero (RF05-RF08)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            funcionarios = Funcionario.objects.filter(contabilidade=contabilidade, ativo=True)
            total_funcionarios = funcionarios.count()

            # Distribuição etária (simulada)
            distribuicao_etaria = [
                {'faixa_etaria': '18-25', 'total_colaboradores': int(total_funcionarios * 0.15), 'percentual': 15.0},
                {'faixa_etaria': '26-35', 'total_colaboradores': int(total_funcionarios * 0.35), 'percentual': 35.0},
                {'faixa_etaria': '36-45', 'total_colaboradores': int(total_funcionarios * 0.30), 'percentual': 30.0},
                {'faixa_etaria': '46-55', 'total_colaboradores': int(total_funcionarios * 0.15), 'percentual': 15.0},
                {'faixa_etaria': '56+', 'total_colaboradores': int(total_funcionarios * 0.05), 'percentual': 5.0}
            ]

            # Distribuição por escolaridade (simulada)
            distribuicao_escolaridade = [
                {'escolaridade': 'Ensino Fundamental', 'total_colaboradores': int(total_funcionarios * 0.10), 'percentual': 10.0},
                {'escolaridade': 'Ensino Médio', 'total_colaboradores': int(total_funcionarios * 0.40), 'percentual': 40.0},
                {'escolaridade': 'Ensino Superior', 'total_colaboradores': int(total_funcionarios * 0.35), 'percentual': 35.0},
                {'escolaridade': 'Pós-graduação', 'total_colaboradores': int(total_funcionarios * 0.15), 'percentual': 15.0}
            ]

            # Distribuição por cargo (simulada)
            distribuicao_cargo = [
                {'cargo': 'Auxiliar', 'total_colaboradores': int(total_funcionarios * 0.30), 'percentual': 30.0},
                {'cargo': 'Assistente', 'total_colaboradores': int(total_funcionarios * 0.25), 'percentual': 25.0},
                {'cargo': 'Analista', 'total_colaboradores': int(total_funcionarios * 0.20), 'percentual': 20.0},
                {'cargo': 'Coordenador', 'total_colaboradores': int(total_funcionarios * 0.15), 'percentual': 15.0},
                {'cargo': 'Gerente', 'total_colaboradores': int(total_funcionarios * 0.10), 'percentual': 10.0}
            ]

            # Distribuição por gênero (simulada)
            distribuicao_genero = [
                {'genero': 'Masculino', 'total_colaboradores': int(total_funcionarios * 0.60), 'percentual': 60.0},
                {'genero': 'Feminino', 'total_colaboradores': int(total_funcionarios * 0.40), 'percentual': 40.0}
            ]

            data = {
                'etaria': distribuicao_etaria,
                'escolaridade': distribuicao_escolaridade,
                'cargo': distribuicao_cargo,
                'genero': distribuicao_genero
            }

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar distribuições demográficas: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FiscalViewSet(viewsets.ViewSet):
    """ViewSet para dashboards fiscais"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def faturamento(self, request):
        """
        Endpoint para visão geral do faturamento (RF01)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar notas fiscais da contabilidade
            notas_fiscais = NotaFiscal.objects.filter(contabilidade=contabilidade)
            
            # Calcular indicadores fiscais
            total_faturamento = notas_fiscais.aggregate(
                total=Sum('valor_total')
            )['total'] or 0
            
            total_impostos = notas_fiscais.aggregate(
                total=Sum('valor_icms') + Sum('valor_pis') + Sum('valor_cofins')
            )['total'] or 0
            
            percentual_impostos = (total_impostos / max(total_faturamento, 1)) * 100
            total_notas_fiscais = notas_fiscais.count()
            media_valor_nota = total_faturamento / max(total_notas_fiscais, 1)

            data = {
                'total_faturamento': total_faturamento,
                'total_impostos': total_impostos,
                'percentual_impostos': round(percentual_impostos, 2),
                'total_notas_fiscais': total_notas_fiscais,
                'media_valor_nota': round(media_valor_nota, 2)
            }

            serializer = IndicadoresFiscaisSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar dados de faturamento: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def produtos(self, request):
        """
        Endpoint para produtos/serviços mais relevantes (RF02)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular dados de produtos/serviços mais relevantes
            produtos_data = [
                {
                    'descricao': 'Serviços de Contabilidade',
                    'total_vendas': 50000.00,
                    'quantidade': 100,
                    'percentual_faturamento': 45.0
                },
                {
                    'descricao': 'Consultoria Fiscal',
                    'total_vendas': 30000.00,
                    'quantidade': 50,
                    'percentual_faturamento': 27.0
                },
                {
                    'descricao': 'Auditoria',
                    'total_vendas': 20000.00,
                    'quantidade': 20,
                    'percentual_faturamento': 18.0
                },
                {
                    'descricao': 'Outros Serviços',
                    'total_vendas': 10000.00,
                    'quantidade': 30,
                    'percentual_faturamento': 10.0
                }
            ]

            serializer = ProdutoServicoSerializer(produtos_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar produtos/serviços: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def clientes(self, request):
        """
        Endpoint para clientes/fornecedores relevantes (RF03)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar clientes com maior faturamento
            contratos = Contrato.objects.filter(contabilidade=contabilidade, ativo=True)
            
            clientes_data = []
            for contrato in contratos[:10]:  # Top 10 clientes
                cliente = contrato.cliente
                if not cliente:
                    continue
                
                # Calcular total de transações (simulado)
                total_transacoes = 10000.00  # Simulado
                quantidade_transacoes = 50    # Simulado
                percentual_faturamento = 5.0  # Simulado
                
                clientes_data.append({
                    'nome': cliente.razao_social if isinstance(cliente, PessoaJuridica) else cliente.nome_completo,
                    'documento': cliente.cnpj if isinstance(cliente, PessoaJuridica) else cliente.cpf,
                    'total_transacoes': total_transacoes,
                    'quantidade_transacoes': quantidade_transacoes,
                    'percentual_faturamento': percentual_faturamento
                })

            serializer = ClienteFornecedorSerializer(clientes_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar clientes/fornecedores: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def geolocalizacao(self, request):
        """
        Endpoint para geolocalização das UF (RF04)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular dados de geolocalização por UF
            geolocalizacao_data = [
                {'uf': 'SP', 'total_faturamento': 80000.00, 'total_notas': 150, 'percentual_faturamento': 40.0},
                {'uf': 'RJ', 'total_faturamento': 50000.00, 'total_notas': 100, 'percentual_faturamento': 25.0},
                {'uf': 'MG', 'total_faturamento': 30000.00, 'total_notas': 60, 'percentual_faturamento': 15.0},
                {'uf': 'RS', 'total_faturamento': 20000.00, 'total_notas': 40, 'percentual_faturamento': 10.0},
                {'uf': 'PR', 'total_faturamento': 20000.00, 'total_notas': 40, 'percentual_faturamento': 10.0}
            ]

            serializer = GeolocalizacaoSerializer(geolocalizacao_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar geolocalização: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def impostos(self, request):
        """
        Endpoint para impostos devidos e evolução (RF05-RF06)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular dados de impostos devidos
            impostos_data = [
                {'tipo_imposto': 'ICMS', 'valor_devido': 15000.00, 'percentual_faturamento': 7.5},
                {'tipo_imposto': 'PIS', 'valor_devido': 2000.00, 'percentual_faturamento': 1.0},
                {'tipo_imposto': 'COFINS', 'valor_devido': 8000.00, 'percentual_faturamento': 4.0},
                {'tipo_imposto': 'IRPJ', 'valor_devido': 5000.00, 'percentual_faturamento': 2.5},
                {'tipo_imposto': 'CSLL', 'valor_devido': 3000.00, 'percentual_faturamento': 1.5}
            ]

            serializer = ImpostoSerializer(impostos_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar dados de impostos: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ContabilViewSet(viewsets.ViewSet):
    """ViewSet para dashboards contábeis"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def indicadores(self, request):
        """
        Endpoint para indicadores financeiros principais (RF01)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar lançamentos contábeis da contabilidade
            lancamentos = LancamentoContabil.objects.filter(contabilidade=contabilidade)
            
            # Simular indicadores contábeis
            data = {
                'total_ativo': 500000.00,
                'total_passivo': 300000.00,
                'patrimonio_liquido': 200000.00,
                'receita_total': 1000000.00,
                'despesa_total': 800000.00,
                'resultado_exercicio': 200000.00
            }

            serializer = IndicadoresContabeisSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar indicadores contábeis: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def evolucao(self, request):
        """
        Endpoint para evolução mensal (RF02)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular dados de evolução mensal dos últimos 12 meses
            evolucao_data = []
            for i in range(12):
                month = timezone.now().date() - timedelta(days=30 * i)
                month_str = month.strftime('%Y-%m')
                
                # Simular dados baseados nos lançamentos existentes
                receita_mensal = 80000.00 + (i * 5000)  # Simulado
                despesa_mensal = 60000.00 + (i * 3000)  # Simulado
                resultado_mensal = receita_mensal - despesa_mensal
                
                evolucao_data.append({
                    'mes_ano': month_str,
                    'receita_mensal': receita_mensal,
                    'despesa_mensal': despesa_mensal,
                    'resultado_mensal': resultado_mensal
                })
            
            # Inverter para ordem cronológica crescente
            evolucao_data.reverse()

            serializer = EvolucaoContabilSerializer(evolucao_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar evolução contábil: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def grupos(self, request):
        """
        Endpoint para valor por grupo e conta (RF04)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular dados de grupos e contas
            grupos_data = [
                {'grupo': 'Ativo Circulante', 'conta': 'Caixa', 'valor_total': 50000.00, 'percentual_total': 10.0},
                {'grupo': 'Ativo Circulante', 'conta': 'Bancos', 'valor_total': 100000.00, 'percentual_total': 20.0},
                {'grupo': 'Ativo Circulante', 'conta': 'Clientes', 'valor_total': 150000.00, 'percentual_total': 30.0},
                {'grupo': 'Ativo Não Circulante', 'conta': 'Imóveis', 'valor_total': 200000.00, 'percentual_total': 40.0}
            ]

            serializer = GrupoContaSerializer(grupos_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar grupos e contas: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def top_contas(self, request):
        """
        Endpoint para top 5 contas por valor (RF05)
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular top 5 contas por valor
            top_contas_data = [
                {'conta': 'Receita de Vendas', 'valor_total': 500000.00, 'percentual_total': 25.0, 'natureza': 'Credora'},
                {'conta': 'Caixa', 'valor_total': 300000.00, 'percentual_total': 15.0, 'natureza': 'Devedora'},
                {'conta': 'Clientes', 'valor_total': 250000.00, 'percentual_total': 12.5, 'natureza': 'Devedora'},
                {'conta': 'Fornecedores', 'valor_total': 200000.00, 'percentual_total': 10.0, 'natureza': 'Credora'},
                {'conta': 'Despesas Operacionais', 'valor_total': 150000.00, 'percentual_total': 7.5, 'natureza': 'Devedora'}
            ]

            serializer = TopContaSerializer(top_contas_data, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar top contas: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class IndicadoresViewSet(viewsets.ViewSet):
    """ViewSet para indicadores financeiros, operacionais e patrimoniais"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def financeiros(self, request):
        """
        Endpoint para indicadores financeiros principais
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular indicadores financeiros
            data = {
                'liquidez_corrente': 1.5,
                'liquidez_seca': 1.2,
                'margem_bruta': 0.3,
                'margem_liquida': 0.15,
                'roe': 0.12,
                'roi': 0.08
            }

            serializer = IndicadoresFinanceirosSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar indicadores financeiros: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def operacionais(self, request):
        """
        Endpoint para indicadores operacionais
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular indicadores operacionais
            data = {
                'giro_estoque': 6.0,
                'prazo_medio_recebimento': 30.0,
                'prazo_medio_pagamento': 45.0,
                'ciclo_operacional': 75.0
            }

            serializer = IndicadoresOperacionaisSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar indicadores operacionais: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def patrimoniais(self, request):
        """
        Endpoint para indicadores patrimoniais
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular indicadores patrimoniais
            data = {
                'endividamento_total': 0.6,
                'endividamento_curto_prazo': 0.3,
                'composicao_endividamento': 0.5,
                'imobilizacao_patrimonio': 0.4
            }

            serializer = IndicadoresPatrimoniaisSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar indicadores patrimoniais: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DREViewSet(viewsets.ViewSet):
    """ViewSet para DRE (Demonstração do Resultado do Exercício)"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def composicao(self, request):
        """
        Endpoint para composição da DRE
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular composição da DRE
            data = {
                'receita_bruta': 1000000.00,
                'deducoes': 100000.00,
                'receita_liquida': 900000.00,
                'custo_mercadorias': 400000.00,
                'lucro_bruto': 500000.00,
                'despesas_operacionais': 200000.00,
                'resultado_operacional': 300000.00,
                'resultado_financeiro': 10000.00,
                'resultado_antes_ir': 310000.00,
                'imposto_renda': 46500.00,
                'resultado_liquido': 263500.00
            }

            serializer = DREComposicaoSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar composição da DRE: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def evolucao(self, request):
        """
        Endpoint para evolução da DRE
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular evolução da DRE dos últimos 12 meses
            evolucao_data = []
            for i in range(12):
                month = timezone.now().date() - timedelta(days=30 * i)
                month_str = month.strftime('%Y-%m')
                
                # Simular dados de evolução
                receita_bruta = 80000.00 + (i * 2000)
                receita_liquida = receita_bruta * 0.9
                lucro_bruto = receita_liquida * 0.5
                resultado_liquido = lucro_bruto * 0.6
                
                evolucao_data.append({
                    'mes_ano': month_str,
                    'receita_bruta': receita_bruta,
                    'receita_liquida': receita_liquida,
                    'lucro_bruto': lucro_bruto,
                    'resultado_liquido': resultado_liquido
                })
            
            # Inverter para ordem cronológica crescente
            evolucao_data.reverse()

            return Response(evolucao_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar evolução da DRE: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
