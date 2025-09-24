from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from apps.core.models import Contabilidade, Usuario
from ..serializers import UsuarioSerializer, UsuarioAtividadesSerializer, UsuarioProdutividadeSerializer

class UsuariosViewSet(viewsets.ViewSet):
    """ViewSet para análise de usuários"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def lista(self, request):
        """
        Endpoint para listar usuários com nome e função.
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            usuarios = Usuario.objects.filter(contabilidade=contabilidade, is_active=True)
            serializer = UsuarioSerializer(usuarios, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar lista de usuários: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def atividades(self, request):
        """
        Endpoint para atividades por usuário (cálculo por hora).
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Simular dados de atividades
            atividades_data = [
                {'usuario': 'wando', 'data': '2025-09-20', 'horas_trabalhadas': 8, 'modulo': 'Gestão'},
                {'usuario': 'operacional', 'data': '2025-09-20', 'horas_trabalhadas': 6, 'modulo': 'Fiscal'},
            ]
            return Response(atividades_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar atividades de usuários: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def produtividade(self, request):
        """
        Endpoint para relatórios de produtividade.
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Simular dados de produtividade
            produtividade_data = [
                {'usuario': 'wando', 'tarefas_concluidas': 15, 'media_tempo_tarefa_min': 30},
                {'usuario': 'operacional', 'tarefas_concluidas': 10, 'media_tempo_tarefa_min': 45},
            ]
            return Response(produtividade_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar produtividade de usuários: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
