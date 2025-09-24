from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta, date

from apps.core.models import Contabilidade, Usuario
from apps.funcionarios.models import Funcionario, VinculoEmpregaticio
from ..serializers import (
    IndicadoresDemograficosSerializer, EvolucaoColaboradoresSerializer,
    DistribuicaoEtariaSerializer, DistribuicaoEscolaridadeSerializer,
    DistribuicaoCargoSerializer, DistribuicaoGeneroSerializer
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

            # Buscar vínculos empregatícios da contabilidade
            vinculos = VinculoEmpregaticio.objects.filter(funcionario__contabilidade=contabilidade)
            
            # Calcular indicadores básicos
            total_colaboradores = vinculos.count()
            colaboradores_ativos = vinculos.filter(ativo=True).count()
            colaboradores_inativos = total_colaboradores - colaboradores_ativos
            
            # Calcular turnover mensal
            data_limite = timezone.now().date() - timedelta(days=30)
            admissões_mes = vinculos.filter(
                data_admissao__gte=data_limite
            ).count()
            demissões_mes = vinculos.filter(
                data_demissao__gte=data_limite
            ).count()
            
            turnover_mensal = (demissões_mes / max(total_colaboradores, 1)) * 100
            
            # Calcular turnover anual
            data_limite_ano = timezone.now().date() - timedelta(days=365)
            admissões_ano = vinculos.filter(
                data_admissao__gte=data_limite_ano
            ).count()
            demissões_ano = vinculos.filter(
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
