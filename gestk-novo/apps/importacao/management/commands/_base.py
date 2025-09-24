import pyodbc
import re
import time
from datetime import date, datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.pessoas.models import Contrato, PessoaJuridica, PessoaFisica
from functools import lru_cache

class BaseETLCommand(BaseCommand):
    """
    Classe base para comandos de ETL que se conectam ao banco de dados Sybase.
    """
    help = 'Classe base para comandos de ETL.'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cache para mapa histórico
        self._historical_map_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 300  # 5 minutos
        
        # Cache para conexão Sybase
        self._sybase_connection = None
        
        # Estatísticas de performance
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'sybase_queries': 0,
            'contabilidade_found': 0,
            'contabilidade_not_found': 0,
            'errors': 0
        }

    def get_sybase_connection(self):
        """
        Cria e retorna uma conexão com o banco de dados Sybase usando as
        configurações definidas em SYBASE_CONFIG no settings.py.
        Reutiliza conexão existente se disponível.
        """
        if self._sybase_connection is not None:
            return self._sybase_connection
            
        sybase_config = settings.SYBASE_CONFIG
        try:
            conn_str = (
                f"DRIVER={{{sybase_config['DRIVER']}}};"
                f"SERVER={sybase_config['SERVER']};"
                f"DATABASE={sybase_config['DATABASE']};"
                f"UID={sybase_config['UID']};"
                f"PWD={sybase_config['PWD']}"
            )
            self._sybase_connection = pyodbc.connect(conn_str)
            self.stdout.write(self.style.SUCCESS('Conexão com o Sybase (ODBC) estabelecida com sucesso.'))
            return self._sybase_connection
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Falha ao conectar ao Sybase: {e}'))
            return None
    
    def close_sybase_connection(self):
        """Fechar conexão Sybase"""
        if self._sybase_connection:
            self._sybase_connection.close()
            self._sybase_connection = None
            self.stdout.write(self.style.SUCCESS('Conexão Sybase fechada.'))

    def execute_query(self, connection, query):
        """
        Executa uma query no banco de dados Sybase e retorna os resultados.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [column[0] for column in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return results
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao executar a query: {e}'))
            return []

    def handle(self, *args, **options):
        # Este método deve ser sobrescrito pelas classes filhas.
        raise NotImplementedError('Subclasses de BaseETLCommand devem implementar o método handle().')

    def build_historical_contabilidade_map(self):
        """
        Cria um mapa que associa o CNPJ/CPF de um cliente a uma
        lista de seus contratos ao longo do tempo.

        Retorna:
            dict: {
                'cnpj_ou_cpf_limpo': [
                    (data_inicio, data_termino, contabilidade_obj, contrato_obj),
                    ...
                ]
            }
        """
        self.stdout.write(self.style.SUCCESS('Construindo mapa histórico de contabilidades por CNPJ/CPF...'))
        
        historical_map = {}
        
        # Buscar todos os contratos com suas pessoas relacionadas
        contratos = Contrato.objects.select_related('contabilidade', 'content_type').all()

        for contrato in contratos:
            cliente = contrato.cliente
            if not cliente:
                continue

            # Determinar o documento único (CNPJ ou CPF)
            documento_limpo = None
            if hasattr(cliente, 'cnpj') and cliente.cnpj:
                documento_limpo = self.limpar_documento(cliente.cnpj)
            elif hasattr(cliente, 'cpf') and cliente.cpf:
                documento_limpo = self.limpar_documento(cliente.cpf)
            
            if not documento_limpo:
                continue
            
            if documento_limpo not in historical_map:
                historical_map[documento_limpo] = []

            # Define um "infinito" para data de término nula
            data_termino = contrato.data_termino if contrato.data_termino else date.max
            
            historical_map[documento_limpo].append(
                (contrato.data_inicio, data_termino, contrato.contabilidade, contrato)
            )
        
        self.stdout.write(self.style.SUCCESS(f'Mapa histórico construído com {len(historical_map)} empresas únicas.'))
        return historical_map
    
    def build_historical_contabilidade_map_cached(self):
        """
        Versão com cache do build_historical_contabilidade_map().
        Cache é invalidado a cada 5 minutos ou quando solicitado.
        """
        current_time = time.time()
        
        # Verificar se cache ainda é válido
        if (self._historical_map_cache is not None and 
            self._cache_timestamp is not None and 
            current_time - self._cache_timestamp < self._cache_ttl):
            self.stats['cache_hits'] += 1
            self.stdout.write(self.style.SUCCESS(f'Usando cache do mapa histórico (hits: {self.stats["cache_hits"]})'))
            return self._historical_map_cache
        
        # Construir novo mapa
        self.stats['cache_misses'] += 1
        self.stdout.write(self.style.WARNING(f'Construindo novo mapa histórico (misses: {self.stats["cache_misses"]})'))
        
        self._historical_map_cache = self.build_historical_contabilidade_map()
        self._cache_timestamp = current_time
        
        return self._historical_map_cache
    
    def invalidate_cache(self):
        """Invalidar cache manualmente"""
        self._historical_map_cache = None
        self._cache_timestamp = None
        self.stdout.write(self.style.SUCCESS('Cache invalidado com sucesso'))

    def get_contabilidade_for_date(self, historical_map, codi_emp, event_date):
        """
        Encontra a contabilidade correta para uma empresa em uma data específica.
        
        Primeiro busca o CNPJ/CPF da empresa no Sybase usando o CODI_EMP,
        depois usa esse documento para encontrar a contabilidade correta na data.

        Args:
            historical_map (dict): O mapa gerado por build_historical_contabilidade_map.
            codi_emp (int): O CODI_EMP da empresa no Sybase.
            event_date (date): A data do evento para o qual a contabilidade deve ser encontrada.

        Returns:
            Contabilidade or None: O objeto Contabilidade correspondente ou None se não encontrado.
        """
        if not event_date or not codi_emp:
            return None
        
        # Primeiro, buscar o CNPJ/CPF da empresa no Sybase
        connection = self.get_sybase_connection()
        if not connection:
            return None
            
        try:
            query = """
            SELECT cgce_emp 
            FROM bethadba.geempre 
            WHERE codi_emp = ?
            """
            with connection.cursor() as cursor:
                cursor.execute(query, (codi_emp,))
                result = cursor.fetchone()
                
            if not result:
                return None
                
            cgce_emp = result[0]
            documento_limpo = self.limpar_documento(cgce_emp)
            
            if not documento_limpo:
                return None
                
            # Agora buscar a contabilidade correta para essa empresa na data
            contratos_empresa = historical_map.get(documento_limpo)
            if not contratos_empresa:
                return None

            for data_inicio, data_termino, contabilidade in contratos_empresa:
                if data_inicio and data_inicio <= event_date <= data_termino:
                    return contabilidade
            
            return None
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao buscar CNPJ/CPF para CODI_EMP {codi_emp}: {e}'))
            return None
        finally:
            connection.close()
    
    def get_contabilidade_for_date_optimized(self, historical_map, codi_emp, event_date):
        """
        Versão otimizada do get_contabilidade_for_date com cache de conexão e logs.
        """
        self.stats['sybase_queries'] += 1
        
        if not event_date or not codi_emp:
            return None
        
        # Usar conexão em cache
        connection = self.get_sybase_connection()
        if not connection:
            return None
            
        try:
            query = """
            SELECT cgce_emp 
            FROM bethadba.geempre 
            WHERE codi_emp = ?
            """
            with connection.cursor() as cursor:
                cursor.execute(query, (codi_emp,))
                result = cursor.fetchone()
                
            if not result:
                self.stats['contabilidade_not_found'] += 1
                return None
                
            cgce_emp = result[0]
            documento_limpo = self.limpar_documento(cgce_emp)
            
            if not documento_limpo:
                self.stats['contabilidade_not_found'] += 1
                return None
                
            # Buscar contabilidade correta para essa empresa na data
            contratos_empresa = historical_map.get(documento_limpo)
            if not contratos_empresa:
                self.stats['contabilidade_not_found'] += 1
                return None

            # Ordenar contratos por data de início para busca mais eficiente
            contratos_ordenados = sorted(contratos_empresa, key=lambda x: x[0])
            
            for data_inicio, data_termino, contabilidade in contratos_ordenados:
                if data_inicio and data_inicio <= event_date <= data_termino:
                    self.stats['contabilidade_found'] += 1
                    return contabilidade
            
            self.stats['contabilidade_not_found'] += 1
            return None
            
        except Exception as e:
            self.stats['errors'] += 1
            self.stdout.write(self.style.ERROR(f'Erro ao buscar CNPJ/CPF para CODI_EMP {codi_emp}: {e}'))
            return None

    def limpar_documento(self, documento):
        """Remove caracteres não numéricos de uma string de documento."""
        if not documento:
            return ""
        return re.sub(r'\D', '', str(documento))
    
    def print_stats(self):
        """Imprimir estatísticas de performance"""
        print("\n=== ESTATÍSTICAS DE PERFORMANCE ===")
        print(f"Cache hits: {self.stats['cache_hits']}")
        print(f"Cache misses: {self.stats['cache_misses']}")
        print(f"Consultas Sybase: {self.stats['sybase_queries']}")
        print(f"Contabilidades encontradas: {self.stats['contabilidade_found']}")
        print(f"Contabilidades não encontradas: {self.stats['contabilidade_not_found']}")
        print(f"Erros: {self.stats['errors']}")
        
        if self.stats['cache_hits'] + self.stats['cache_misses'] > 0:
            hit_rate = self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['cache_misses']) * 100
            print(f"Taxa de acerto do cache: {hit_rate:.1f}%")
    
    def validate_mapeamento_integrity(self, historical_map):
        """Validar integridade do mapeamento"""
        problemas = []
        
        for documento, contratos in historical_map.items():
            # Verificar se há contratos
            if not contratos:
                problemas.append(f"Documento {documento} sem contratos")
                continue
            
            # Verificar sobreposições
            contratos_ordenados = sorted(contratos, key=lambda x: x[0])
            
            for i in range(len(contratos_ordenados) - 1):
                data_termino_atual = contratos_ordenados[i][1]
                data_inicio_proximo = contratos_ordenados[i + 1][0]
                
                if data_termino_atual != date.max and data_termino_atual >= data_inicio_proximo:
                    problemas.append(f"Sobreposição em {documento}: {contratos_ordenados[i]} e {contratos_ordenados[i + 1]}")
            
            # Verificar lacunas temporais significativas
            for i in range(len(contratos_ordenados) - 1):
                data_termino_atual = contratos_ordenados[i][1]
                data_inicio_proximo = contratos_ordenados[i + 1][0]
                
                if data_termino_atual != date.max and data_inicio_proximo != date.max:
                    # Verificar se a lacuna é significativa (mais de 30 dias)
                    if (data_inicio_proximo - data_termino_atual).days > 30:
                        problemas.append(f"Lacuna temporal em {documento}: {data_termino_atual} -> {data_inicio_proximo}")
        
        return problemas

