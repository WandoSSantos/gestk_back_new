from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from apps.core.models import Contabilidade, Usuario
from apps.pessoas.models import Contrato
from apps.contabil.models import LancamentoContabil
from apps.fiscal.models import NotaFiscal

class EscritorioViewSet(viewsets.ViewSet):
    """ViewSet para análise do escritório"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def resultados(self, request):
        """
        Endpoint para resultados do escritório.
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calcular métricas do escritório
            total_clientes = Contrato.objects.filter(contabilidade=contabilidade, ativo=True).count()
            total_usuarios = Usuario.objects.filter(contabilidade=contabilidade, is_active=True).count()
            
            # Calcular receita total (simulada)
            receita_total = 100000.00  # Simulado
            
            # Calcular despesas totais (simulada)
            despesas_total = 60000.00  # Simulado
            
            # Calcular lucro líquido
            lucro_liquido = receita_total - despesas_total
            
            # Calcular margem de lucro
            margem_lucro = (lucro_liquido / receita_total * 100) if receita_total > 0 else 0

            data = {
                'contabilidade': {
                    'id': str(contabilidade.id),
                    'cnpj': contabilidade.cnpj,
                    'razao_social': contabilidade.razao_social
                },
                'metricas': {
                    'total_clientes': total_clientes,
                    'total_usuarios': total_usuarios,
                    'receita_total': receita_total,
                    'despesas_total': despesas_total,
                    'lucro_liquido': lucro_liquido,
                    'margem_lucro': round(margem_lucro, 2)
                }
            }

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar resultados do escritório: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def comparativo(self, request):
        """
        Endpoint para comparativo entre períodos.
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular dados de comparativo
            comparativo_data = {
                'periodo_atual': {
                    'mes': 'Setembro 2025',
                    'receita': 100000.00,
                    'despesas': 60000.00,
                    'lucro': 40000.00,
                    'clientes': 50
                },
                'periodo_anterior': {
                    'mes': 'Agosto 2025',
                    'receita': 95000.00,
                    'despesas': 58000.00,
                    'lucro': 37000.00,
                    'clientes': 48
                },
                'variacoes': {
                    'receita_percentual': 5.26,
                    'despesas_percentual': 3.45,
                    'lucro_percentual': 8.11,
                    'clientes_percentual': 4.17
                }
            }

            return Response(comparativo_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar comparativo do escritório: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
