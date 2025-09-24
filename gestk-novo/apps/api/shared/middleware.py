"""
Middleware Multitenant com Regra de Ouro

Aplica automaticamente a Regra de Ouro para isolamento multitenant
em todas as requisições da API.
"""

from django.core.cache import cache
from django.conf import settings
from apps.core.models import Contabilidade
from apps.pessoas.models import Contrato
import logging

logger = logging.getLogger(__name__)


class MultitenantMiddleware:
    """
    Middleware que aplica automaticamente a Regra de Ouro
    para isolamento multitenant em todas as requisições
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache_key = 'historical_contabilidade_map'
        self.cache_timeout = 300  # 5 minutos
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Aplicar filtros automáticos por contabilidade
            request.contabilidade = request.user.contabilidade
            
            # Aplicar Regra de Ouro se necessário
            if hasattr(request, 'data_evento') and request.data_evento:
                request.contabilidade = self.aplicar_regra_ouro(
                    request.user.contabilidade,
                    request.data_evento
                )
        
        response = self.get_response(request)
        return response
    
    def aplicar_regra_ouro(self, contabilidade_padrao, data_evento):
        """
        Aplica a Regra de Ouro para identificar a contabilidade correta:
        1. Busca no cache o mapa histórico de contabilidades
        2. Se não estiver em cache, constrói o mapa
        3. Aplica a regra de ouro para a data do evento
        """
        try:
            # Buscar mapa histórico no cache
            historical_map = cache.get(self.cache_key)
            
            if not historical_map:
                historical_map = self.build_historical_contabilidade_map()
                cache.set(self.cache_key, historical_map, self.cache_timeout)
            
            # Aplicar regra de ouro
            return self.get_contabilidade_for_date_optimized(
                historical_map, 
                contabilidade_padrao, 
                data_evento
            )
            
        except Exception as e:
            logger.error(f"Erro ao aplicar Regra de Ouro: {e}")
            return contabilidade_padrao
    
    def build_historical_contabilidade_map(self):
        """
        Constrói o mapa histórico de contabilidades por CNPJ/CPF
        Reutiliza a lógica dos ETLs
        """
        historical_map = {}
        
        try:
            contratos = Contrato.objects.select_related('contabilidade', 'content_type').all()
            
            for contrato in contratos:
                if contrato.content_type.model == 'pessoajuridica':
                    cnpj_limpo = self.limpar_documento(contrato.empresa.cnpj)
                    data_termino = contrato.data_fim or settings.DEFAULT_END_DATE
                    
                    if cnpj_limpo not in historical_map:
                        historical_map[cnpj_limpo] = []
                    
                    historical_map[cnpj_limpo].append(
                        (contrato.data_inicio, data_termino, contrato.contabilidade)
                    )
            
            # Ordenar por data de início
            for cnpj in historical_map:
                historical_map[cnpj].sort(key=lambda x: x[0])
            
            logger.info(f"Mapa histórico construído com {len(historical_map)} empresas")
            return historical_map
            
        except Exception as e:
            logger.error(f"Erro ao construir mapa histórico: {e}")
            return {}
    
    def get_contabilidade_for_date_optimized(self, historical_map, contabilidade_padrao, data_evento):
        """
        Versão otimizada da Regra de Ouro para uso no middleware
        """
        try:
            # Se não há data de evento, retorna contabilidade padrão
            if not data_evento:
                return contabilidade_padrao
            
            # Buscar contabilidade no mapa histórico
            for cnpj, contratos in historical_map.items():
                for data_inicio, data_termino, contabilidade in contratos:
                    if data_inicio <= data_evento <= data_termino:
                        return contabilidade
            
            # Se não encontrou, retorna contabilidade padrão
            return contabilidade_padrao
            
        except Exception as e:
            logger.error(f"Erro na Regra de Ouro otimizada: {e}")
            return contabilidade_padrao
    
    def limpar_documento(self, documento):
        """
        Limpa e formata CNPJ/CPF para busca no mapa histórico
        """
        if not documento:
            return None
        
        # Remove caracteres não numéricos
        documento_limpo = ''.join(filter(str.isdigit, str(documento)))
        
        # Validação básica
        if len(documento_limpo) not in [11, 14]:  # CPF ou CNPJ
            return None
        
        return documento_limpo
