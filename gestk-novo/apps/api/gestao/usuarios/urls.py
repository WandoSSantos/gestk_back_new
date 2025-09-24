from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar ViewSets
from .views import UsuariosViewSet

# Router para usuários
router = DefaultRouter()
router.register(r'', UsuariosViewSet, basename='usuarios')

urlpatterns = [
    path('', include(router.urls)),
]
