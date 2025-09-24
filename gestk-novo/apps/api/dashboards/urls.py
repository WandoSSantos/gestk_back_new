from django.urls import path, include

urlpatterns = [
    # Módulos específicos seguindo a estrutura da documentação
    path('demografico/', include('apps.api.dashboards.demografico.urls')),
    # path('fiscal/', include('apps.api.dashboards.fiscal.urls')),
    # path('contabil/', include('apps.api.dashboards.contabil.urls')),
    # path('indicadores/', include('apps.api.dashboards.indicadores.urls')),
    # path('dre/', include('apps.api.dashboards.dre.urls')),
]