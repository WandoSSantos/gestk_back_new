"""
URLs do módulo de Gestão
"""

from django.urls import path, include

urlpatterns = [
    # Módulos específicos seguindo a estrutura da documentação
    path('carteira/', include('apps.api.gestao.carteira.urls')),
    path('clientes/', include('apps.api.gestao.clientes.urls')),
    path('usuarios/', include('apps.api.gestao.usuarios.urls')),
    path('escritorio/', include('apps.api.gestao.escritorio.urls')),
]
