"""
Filtros Automáticos por Contabilidade

Aplica automaticamente filtros de contabilidade em todos os ViewSets
para garantir isolamento multitenant rigoroso.
"""

from rest_framework import filters
from django.db import models
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)


class ContabilidadeFilterBackend(filters.BaseFilterBackend):
    """
    Filtro automático que aplica contabilidade=request.user.contabilidade
    em todos os ViewSets que herdam de BaseViewSet
    """
    
    def filter_queryset(self, request, queryset, view):
        """
        Aplica filtro automático por contabilidade
        """
        if not request.user.is_authenticated:
            return queryset.none()
        
        # Verificar se o modelo tem campo contabilidade
        if not hasattr(queryset.model, 'contabilidade'):
            return queryset
        
        # Aplicar filtro por contabilidade
        contabilidade = getattr(request, 'contabilidade', request.user.contabilidade)
        
        if not contabilidade:
            logger.warning(f"Usuário {request.user} sem contabilidade definida")
            return queryset.none()
        
        try:
            return queryset.filter(contabilidade=contabilidade)
        except Exception as e:
            logger.error(f"Erro ao aplicar filtro de contabilidade: {e}")
            return queryset.none()


class DataEventoFilterBackend(filters.BaseFilterBackend):
    """
    Filtro que aplica a Regra de Ouro baseada na data do evento
    """
    
    def filter_queryset(self, request, queryset, view):
        """
        Aplica filtro baseado na data do evento usando Regra de Ouro
        """
        if not request.user.is_authenticated:
            return queryset.none()
        
        # Verificar se há data de evento na requisição
        data_evento = request.query_params.get('data_evento')
        if not data_evento:
            return queryset
        
        # Aplicar Regra de Ouro se necessário
        contabilidade = getattr(request, 'contabilidade', request.user.contabilidade)
        
        if not contabilidade:
            return queryset.none()
        
        try:
            # Se a contabilidade mudou devido à Regra de Ouro, refiltrar
            if contabilidade != request.user.contabilidade:
                return queryset.filter(contabilidade=contabilidade)
            
            return queryset
        except Exception as e:
            logger.error(f"Erro ao aplicar filtro de data de evento: {e}")
            return queryset


class MultitenantPermissionMixin:
    """
    Mixin que adiciona validação de permissão multitenant
    """
    
    def check_object_permissions(self, request, obj):
        """
        Verifica se o usuário tem permissão para acessar o objeto
        baseado na contabilidade
        """
        super().check_object_permissions(request, obj)
        
        # Verificar se o objeto pertence à contabilidade do usuário
        if hasattr(obj, 'contabilidade'):
            if obj.contabilidade != request.user.contabilidade:
                raise PermissionDenied("Acesso negado: objeto não pertence à sua contabilidade")
    
    def get_queryset(self):
        """
        Aplica filtro automático por contabilidade
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
