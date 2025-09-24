from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar ViewSets
from .views import EscritorioViewSet

# Router para escritório
router = DefaultRouter()
router.register(r'', EscritorioViewSet, basename='escritorio')

urlpatterns = [
    path('', include(router.urls)),
]
