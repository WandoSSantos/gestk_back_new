from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar ViewSets
from .views import DemograficoViewSet

# Router para demográfico
router = DefaultRouter()
router.register(r'', DemograficoViewSet, basename='demografico')

urlpatterns = [
    path('', include(router.urls)),
]
