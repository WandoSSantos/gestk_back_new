"""
URLs do módulo de Autenticação
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    CustomTokenObtainPairView, 
    AuthViewSet, 
    UsuarioViewSet,
    login_view,
    me_view,
    logout_view
)

# Router para autenticação
router = DefaultRouter()
router.trailing_slash = False

# Registrar ViewSets
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'usuarios', UsuarioViewSet, basename='usuarios')

urlpatterns = [
    path('', include(router.urls)),
    
    # Endpoints JWT customizados
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Endpoints customizados
    path('login/', login_view, name='login'),
    path('me/', me_view, name='me'),
    path('logout/', logout_view, name='logout'),
]
