"""
ViewSets Base para API REST

Classes base que implementam multitenancy e Regra de Ouro
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.db.models import Q
from .filters import ContabilidadeFilterBackend, DataEventoFilterBackend, MultitenantPermissionMixin
import logging

logger = logging.getLogger(__name__)


class BaseViewSet(MultitenantPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet base que implementa multitenancy automático
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [ContabilidadeFilterBackend, DataEventoFilterBackend]
    
    def get_queryset(self):
        """
        Aplica filtros automáticos por contabilidade
        """
        queryset = super().get_queryset()
        
        if not self.request.user.is_authenticated:
            return queryset.none()
        
        # Verificar se o modelo tem campo contabilidade
        if not hasattr(queryset.model, 'contabilidade'):
            return queryset
        
        # Aplicar filtro por contabilidade
        contabilidade = getattr(self.request, 'contabilidade', self.request.user.contabilidade)
        
        if not contabilidade:
            return queryset.none()
        
        return queryset.filter(contabilidade=contabilidade)
    
    def perform_create(self, serializer):
        """
        Define automaticamente a contabilidade ao criar objetos
        """
        contabilidade = getattr(self.request, 'contabilidade', self.request.user.contabilidade)
        serializer.save(contabilidade=contabilidade)
    
    def perform_update(self, serializer):
        """
        Valida contabilidade ao atualizar objetos
        """
        contabilidade = getattr(self.request, 'contabilidade', self.request.user.contabilidade)
        
        # Verificar se o objeto pertence à contabilidade
        if hasattr(serializer.instance, 'contabilidade'):
            if serializer.instance.contabilidade != contabilidade:
                raise PermissionDenied("Acesso negado: objeto não pertence à sua contabilidade")
        
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Endpoint para estatísticas básicas do modelo
        """
        try:
            queryset = self.get_queryset()
            
            stats = {
                'total': queryset.count(),
                'ativo': queryset.filter(ativo=True).count() if hasattr(queryset.model, 'ativo') else None,
                'inativo': queryset.filter(ativo=False).count() if hasattr(queryset.model, 'ativo') else None,
            }
            
            return Response(stats)
        except Exception as e:
            logger.error(f"Erro ao gerar estatísticas: {e}")
            return Response(
                {'error': 'Erro ao gerar estatísticas'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReadOnlyViewSet(MultitenantPermissionMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet somente leitura com multitenancy
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [ContabilidadeFilterBackend, DataEventoFilterBackend]
    
    def get_queryset(self):
        """
        Aplica filtros automáticos por contabilidade
        """
        queryset = super().get_queryset()
        
        if not self.request.user.is_authenticated:
            return queryset.none()
        
        # Verificar se o modelo tem campo contabilidade
        if not hasattr(queryset.model, 'contabilidade'):
            return queryset
        
        # Aplicar filtro por contabilidade
        contabilidade = getattr(self.request, 'contabilidade', self.request.user.contabilidade)
        
        if not contabilidade:
            return queryset.none()
        
        return queryset.filter(contabilidade=contabilidade)


class DashboardViewSet(ReadOnlyViewSet):
    """
    ViewSet base para dashboards com agregações complexas
    """
    
    def get_queryset(self):
        """
        Aplica filtros específicos para dashboards
        """
        queryset = super().get_queryset()
        
        # Filtros específicos para dashboards
        data_inicio = self.request.query_params.get('data_inicio')
        data_fim = self.request.query_params.get('data_fim')
        
        if data_inicio and hasattr(queryset.model, 'data_criacao'):
            queryset = queryset.filter(data_criacao__gte=data_inicio)
        
        if data_fim and hasattr(queryset.model, 'data_criacao'):
            queryset = queryset.filter(data_criacao__lte=data_fim)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def resumo(self, request):
        """
        Endpoint para resumo executivo do dashboard
        """
        try:
            queryset = self.get_queryset()
            
            # Implementar agregações específicas do dashboard
            resumo = self.calcular_resumo(queryset)
            
            return Response(resumo)
        except Exception as e:
            logger.error(f"Erro ao gerar resumo: {e}")
            return Response(
                {'error': 'Erro ao gerar resumo'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def calcular_resumo(self, queryset):
        """
        Método para ser sobrescrito pelas classes filhas
        """
        return {
            'total': queryset.count(),
            'periodo': 'Últimos 30 dias'
        }
