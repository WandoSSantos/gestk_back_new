"""
URLs da API REST - Projeto GESTK

Estrutura de endpoints com Regra de Ouro e multitenancy
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar ViewSets (serão criados nos próximos passos)
# from .auth.views import AuthViewSet
# from .gestao.views import CarteiraViewSet, ClientesViewSet, UsuariosViewSet
# from .dashboards.views import FiscalViewSet, ContabilViewSet, RHViewSet
# from .export.views import RelatoriosViewSet

# Router principal
router = DefaultRouter()
router.trailing_slash = False

# Registrar ViewSets (serão descomentados conforme implementação)
# router.register(r'auth', AuthViewSet, basename='auth')
# router.register(r'gestao/carteira', CarteiraViewSet, basename='carteira')
# router.register(r'gestao/clientes', ClientesViewSet, basename='clientes')
# router.register(r'gestao/usuarios', UsuariosViewSet, basename='usuarios')
# router.register(r'dashboards/fiscal', FiscalViewSet, basename='fiscal')
# router.register(r'dashboards/contabil', ContabilViewSet, basename='contabil')
# router.register(r'dashboards/rh', RHViewSet, basename='rh')
# router.register(r'export/relatorios', RelatoriosViewSet, basename='relatorios')

urlpatterns = [
    # API principal
    path('', include(router.urls)),
    
    # Módulos específicos
    path('auth/', include('apps.api.auth.urls')),
    path('gestao/', include('apps.api.gestao.urls')),
    path('dashboards/', include('apps.api.dashboards.urls')),
    path('export/', include('apps.api.export.urls')),
]
