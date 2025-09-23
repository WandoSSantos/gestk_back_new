import pyodbc
import re
from datetime import date, datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from pessoas.models import Contrato, PessoaJuridica, PessoaFisica

class BaseETLCommand(BaseCommand):
    """
    Classe base para comandos de ETL que se conectam ao banco de dados Sybase.
    """
    help = 'Classe base para comandos de ETL.'

    def get_sybase_connection(self):
        """
        Cria e retorna uma conexão com o banco de dados Sybase usando as
        configurações definidas em SYBASE_CONFIG no settings.py.
        """
        sybase_config = settings.SYBASE_CONFIG
        try:
            conn_str = (
                f"DRIVER={{{sybase_config['DRIVER']}}};"
                f"SERVER={sybase_config['SERVER']};"
                f"DATABASE={sybase_config['DATABASE']};"
                f"UID={sybase_config['UID']};"
                f"PWD={sybase_config['PWD']}"
            )
            connection = pyodbc.connect(conn_str)
            self.stdout.write(self.style.SUCCESS('Conexão com o Sybase (ODBC) estabelecida com sucesso.'))
            return connection
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Falha ao conectar ao Sybase: {e}'))
            return None

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
                    (data_inicio, data_termino, contabilidade_obj),
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
                (contrato.data_inicio, data_termino, contrato.contabilidade)
            )
        
        self.stdout.write(self.style.SUCCESS(f'Mapa histórico construído com {len(historical_map)} empresas únicas.'))
        return historical_map

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

    def limpar_documento(self, documento):
        """Remove caracteres não numéricos de uma string de documento."""
        if not documento:
            return ""
        return re.sub(r'\D', '', str(documento))

