from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar ViewSets
from .views import ClientesViewSet

# Router para clientes
router = DefaultRouter()
router.register(r'', ClientesViewSet, basename='clientes')

urlpatterns = [
    path('', include(router.urls)),
]
