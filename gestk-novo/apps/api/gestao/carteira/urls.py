from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar ViewSets
from .views import CarteiraViewSet

# Router para carteira
router = DefaultRouter()
router.register(r'', CarteiraViewSet, basename='carteira')

urlpatterns = [
    path('', include(router.urls)),
]
