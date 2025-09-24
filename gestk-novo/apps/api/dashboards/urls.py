"""
URLs do módulo de Dashboards
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar ViewSets (serão criados nos próximos passos)
# from .views import FiscalViewSet, ContabilViewSet, RHViewSet, DemograficoViewSet

# Router para dashboards
router = DefaultRouter()
router.trailing_slash = False

# Registrar ViewSets (serão descomentados conforme implementação)
# router.register(r'fiscal', FiscalViewSet, basename='fiscal')
# router.register(r'contabil', ContabilViewSet, basename='contabil')
# router.register(r'rh', RHViewSet, basename='rh')
# router.register(r'demografico', DemograficoViewSet, basename='demografico')

urlpatterns = [
    path('', include(router.urls)),
]
