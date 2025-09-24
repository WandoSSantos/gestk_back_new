"""
URLs do módulo de Exportação
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar ViewSets (serão criados nos próximos passos)
# from .views import RelatoriosViewSet, ExportViewSet

# Router para exportação
router = DefaultRouter()
router.trailing_slash = False

# Registrar ViewSets (serão descomentados conforme implementação)
# router.register(r'relatorios', RelatoriosViewSet, basename='relatorios')
# router.register(r'export', ExportViewSet, basename='export')

urlpatterns = [
    path('', include(router.urls)),
]
