"""
Permissões Customizadas para API REST

Implementa permissões baseadas em contabilidade e Regra de Ouro
"""

from rest_framework import permissions
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)


class IsContabilidadeOwner(permissions.BasePermission):
    """
    Permissão que verifica se o usuário pertence à contabilidade do objeto
    """
    
    def has_permission(self, request, view):
        """
        Verifica se o usuário tem permissão para acessar a view
        """
        if not request.user.is_authenticated:
            return False
        
        # Verificar se o usuário tem contabilidade
        if not hasattr(request.user, 'contabilidade') or not request.user.contabilidade:
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica se o usuário tem permissão para acessar o objeto
        """
        if not request.user.is_authenticated:
            return False
        
        # Verificar se o objeto tem campo contabilidade
        if not hasattr(obj, 'contabilidade'):
            return True
        
        # Verificar se a contabilidade do objeto é a mesma do usuário
        return obj.contabilidade == request.user.contabilidade


class IsContabilidadeOwnerOrReadOnly(permissions.BasePermission):
    """
    Permissão que permite leitura para todos e escrita apenas para donos da contabilidade
    """
    
    def has_permission(self, request, view):
        """
        Verifica se o usuário tem permissão para acessar a view
        """
        if not request.user.is_authenticated:
            return False
        
        # Verificar se o usuário tem contabilidade
        if not hasattr(request.user, 'contabilidade') or not request.user.contabilidade:
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica se o usuário tem permissão para acessar o objeto
        """
        if not request.user.is_authenticated:
            return False
        
        # Verificar se o objeto tem campo contabilidade
        if not hasattr(obj, 'contabilidade'):
            return True
        
        # Leitura sempre permitida
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Escrita apenas para donos da contabilidade
        return obj.contabilidade == request.user.contabilidade


class IsSuperUserOrContabilidadeOwner(permissions.BasePermission):
    """
    Permissão que permite acesso para superusuários ou donos da contabilidade
    """
    
    def has_permission(self, request, view):
        """
        Verifica se o usuário tem permissão para acessar a view
        """
        if not request.user.is_authenticated:
            return False
        
        # Superusuários têm acesso total
        if request.user.is_superuser:
            return True
        
        # Verificar se o usuário tem contabilidade
        if not hasattr(request.user, 'contabilidade') or not request.user.contabilidade:
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica se o usuário tem permissão para acessar o objeto
        """
        if not request.user.is_authenticated:
            return False
        
        # Superusuários têm acesso total
        if request.user.is_superuser:
            return True
        
        # Verificar se o objeto tem campo contabilidade
        if not hasattr(obj, 'contabilidade'):
            return True
        
        # Verificar se a contabilidade do objeto é a mesma do usuário
        return obj.contabilidade == request.user.contabilidade


class IsContabilidadeActive(permissions.BasePermission):
    """
    Permissão que verifica se a contabilidade está ativa
    """
    
    def has_permission(self, request, view):
        """
        Verifica se a contabilidade do usuário está ativa
        """
        if not request.user.is_authenticated:
            return False
        
        # Verificar se o usuário tem contabilidade
        if not hasattr(request.user, 'contabilidade') or not request.user.contabilidade:
            return False
        
        # Verificar se a contabilidade está ativa
        return request.user.contabilidade.ativo


class RegraOuroPermission(permissions.BasePermission):
    """
    Permissão que aplica a Regra de Ouro para validação de acesso
    """
    
    def has_permission(self, request, view):
        """
        Verifica se o usuário tem permissão baseada na Regra de Ouro
        """
        if not request.user.is_authenticated:
            return False
        
        # Verificar se o usuário tem contabilidade
        if not hasattr(request.user, 'contabilidade') or not request.user.contabilidade:
            return False
        
        # Aplicar Regra de Ouro se necessário
        if hasattr(request, 'contabilidade') and request.contabilidade:
            # Verificar se a contabilidade foi alterada pela Regra de Ouro
            if request.contabilidade != request.user.contabilidade:
                # Verificar se o usuário tem acesso à nova contabilidade
                return self.verificar_acesso_contabilidade(request.user, request.contabilidade)
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """
        Verifica se o usuário tem permissão para acessar o objeto baseado na Regra de Ouro
        """
        if not request.user.is_authenticated:
            return False
        
        # Verificar se o objeto tem campo contabilidade
        if not hasattr(obj, 'contabilidade'):
            return True
        
        # Aplicar Regra de Ouro
        contabilidade = getattr(request, 'contabilidade', request.user.contabilidade)
        
        if contabilidade != request.user.contabilidade:
            # Verificar se o usuário tem acesso à contabilidade da Regra de Ouro
            return self.verificar_acesso_contabilidade(request.user, contabilidade)
        
        return obj.contabilidade == contabilidade
    
    def verificar_acesso_contabilidade(self, user, contabilidade):
        """
        Verifica se o usuário tem acesso à contabilidade
        """
        try:
            # Verificar se o usuário tem vínculo com a contabilidade
            from apps.administracao.models import UsuarioContabilidade
            
            return UsuarioContabilidade.objects.filter(
                usuario=user,
                contabilidade=contabilidade,
                ativo=True
            ).exists()
            
        except Exception as e:
            logger.error(f"Erro ao verificar acesso à contabilidade: {e}")
            return False
