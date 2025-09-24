"""
URLs do módulo de Gestão
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar ViewSets (serão criados nos próximos passos)
# from .views import CarteiraViewSet, ClientesViewSet, UsuariosViewSet, EscritorioViewSet

# Router para gestão
router = DefaultRouter()
router.trailing_slash = False

# Registrar ViewSets (serão descomentados conforme implementação)
# router.register(r'carteira', CarteiraViewSet, basename='carteira')
# router.register(r'clientes', ClientesViewSet, basename='clientes')
# router.register(r'usuarios', UsuariosViewSet, basename='usuarios')
# router.register(r'escritorio', EscritorioViewSet, basename='escritorio')

urlpatterns = [
    path('', include(router.urls)),
]
