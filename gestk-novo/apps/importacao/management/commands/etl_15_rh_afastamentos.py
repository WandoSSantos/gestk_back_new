import re
import pyodbc
from decimal import Decimal
from itertools import islice
from django.db import transaction
from apps.funcionarios.models import VinculoEmpregaticio, Afastamento
from ._base import BaseETLCommand

def batch_iterator(iterable, batch_size):
    """Itera sobre um iterável em lotes de tamanho batch_size."""
    it = iter(iterable)
    while True:
        chunk = tuple(islice(it, batch_size))
        if not chunk:
            return
        yield chunk

class Command(BaseETLCommand):
    help = 'Executa o ETL de Afastamentos do Sybase para o PostgreSQL, aplicando regras de negócio.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Iniciando ETL de Afastamentos..."))

        # Construir mapas em memória
        historical_map = self.build_historical_contabilidade_map()
        vinculos_map = self.build_vinculos_map()
        
        # Conectar ao Sybase e buscar dados
        conn = self.get_sybase_connection()
        if not conn:
            return

        query = """
        SELECT
            a.CODI_EMP,
            a.I_EMPREGADOS,
            a.I_AFASTAMENTOS,
            a.DATA_REAL as data_inicio,
            a.DATA_FIM as data_fim,
            a.DATA_FIM_TMP as previsao_fim,
            a.NUMERO_DIAS as dias_afastado,
            a.CODIGO_DOENCA,
            a.NOME_MEDICO,
            a.CRM_MEDICO,
            a.OBSERVACAO_LICENCA_SEM_VENCIMENTO as observacoes
        FROM bethadba.FOAFASTAMENTOS a
        WHERE a.DATA_REAL >= '2019-01-01'
        """
        
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            afastamentos_data = cursor.fetchall()
            self.stdout.write(self.style.SUCCESS(f"Total de {len(afastamentos_data)} registros de afastamento encontrados (desde 2019)."))
            
            total_criados = 0
            total_atualizados = 0
            
            with transaction.atomic():
                for afastamento in afastamentos_data:
                    contabilidade = self.get_contabilidade_for_date(
                        historical_map, afastamento.CODI_EMP, afastamento.data_inicio
                    )
                    
                    if not contabilidade:
                        # Este warning agora é mais preciso, pois a falta de contrato na data é um motivo válido
                        continue
                    
                    vinculo_key = (contabilidade.id, str(afastamento.I_EMPREGADOS))
                    vinculo = vinculos_map.get(vinculo_key)
                    
                    if not vinculo:
                        continue

                    defaults = {
                        'data_inicio': afastamento.data_inicio,
                        'data_fim': afastamento.data_fim,
                        'previsao_fim': afastamento.previsao_fim,
                        'dias_afastado': int(afastamento.dias_afastado) if afastamento.dias_afastado else 0,
                        'codigo_doenca': afastamento.CODIGO_DOENCA,
                        'nome_medico': afastamento.NOME_MEDICO,
                        'crm_medico': afastamento.CRM_MEDICO,
                        'observacoes': afastamento.observacoes,
                    }

                    obj, created = Afastamento.objects.update_or_create(
                        contabilidade=contabilidade,
                        vinculo=vinculo,
                        id_legado=str(afastamento.I_AFASTAMENTOS),
                        defaults=defaults
                    )
                    
                    if created:
                        total_criados += 1
                    else:
                        total_atualizados += 1
            
            self.stdout.write(self.style.SUCCESS(f"ETL concluído. {total_criados} afastamentos criados, {total_atualizados} atualizados."))

        except pyodbc.Error as e:
            self.stdout.write(self.style.ERROR(f"Erro ao buscar dados de afastamentos: {e}"))
        finally:
            cursor.close()
            conn.close()

    def build_vinculos_map(self):
        self.stdout.write("Construindo mapa de vínculos empregatícios...")
        vinculos_map = {
            (v.contabilidade.id, v.matricula): v
            for v in VinculoEmpregaticio.objects.select_related('contabilidade').all()
        }
        self.stdout.write(f"Mapa de vínculos construído com {len(vinculos_map)} registros.")
        return vinculos_map
