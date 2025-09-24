import re
from django.db import transaction
from tqdm import tqdm
from ._base import BaseETLCommand
from funcionarios.models import VinculoEmpregaticio, PeriodoAquisitivoFerias

def batch_iterator(iterator, batch_size):
    """Gera lotes de um iterador."""
    batch = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

class Command(BaseETLCommand):
    help = 'ETL para importar os Períodos Aquisitivos de Férias do Sybase, com regras de negócio.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL de Períodos Aquisitivos de Férias ---'))
        connection = self.get_sybase_connection()
        if not connection: return

        try:
            self.stdout.write(self.style.HTTP_INFO('\n[1/4] Construindo mapa histórico de Contabilidades...'))
            historical_map = self.build_historical_contabilidade_map()
            self.stdout.write(self.style.SUCCESS(f"✓ Mapa histórico construído."))

            self.stdout.write(self.style.HTTP_INFO('\n[2/4] Construindo mapa de Vínculos Empregatícios...'))
            vinculos_map = self.build_vinculos_map()
            self.stdout.write(self.style.SUCCESS(f"✓ Mapa de Vínculos construído com {len(vinculos_map):,} registros."))
            
            self.stdout.write(self.style.HTTP_INFO('\n[3/4] Extraindo dados de Períodos Aquisitivos (desde 2019)...'))
            query = """
            SELECT 
                fa.codi_emp, fa.i_empregados, fa.i_ferias_aquisitivos,
                fa.ini_per_aquis as data_inicio, fa.fim_per_aquis as data_fim,
                fa.dias_direito, fa.situacao -- 1=Aberto, 2=Fechado, 3=Programado
            FROM bethadba.FOFERIAS_AQUISITIVOS fa
            WHERE fa.ini_per_aquis >= '2019-01-01'
            """
            data = self.execute_query(connection, query)
            if not data:
                self.stdout.write(self.style.WARNING('Nenhum período aquisitivo encontrado.'))
                return
            self.stdout.write(self.style.SUCCESS(f"✓ {len(data):,} registros de períodos aquisitivos extraídos."))

            self.stdout.write(self.style.HTTP_INFO('\n[4/4] Processando e carregando dados no Gestk...'))
            stats = self.processar_dados(data, vinculos_map, historical_map)

        finally:
            connection.close()

        self.stdout.write(self.style.SUCCESS('\n--- Resumo do ETL de Períodos Aquisitivos ---'))
        self.stdout.write(f"  - Períodos Criados: {stats['criados']}")
        self.stdout.write(f"  - Períodos Atualizados: {stats['atualizados']}")
        self.stdout.write(f"  - Registros sem contabilidade/contrato na data: {stats['sem_contabilidade']}")
        self.stdout.write(f"  - Registros sem vínculo correspondente: {stats['sem_vinculo']}")
        self.stdout.write(self.style.ERROR(f"  - Erros: {stats['erros']}"))
        self.stdout.write(self.style.SUCCESS('--- ETL de Períodos Aquisitivos Finalizado ---'))

    def build_vinculos_map(self):
        """ Cria um mapa de Vínculos usando (id_legado_contabilidade, matricula) como chave. """
        vinculos_map = {}
        vinculos = VinculoEmpregaticio.objects.select_related('contabilidade').all()
        for v in vinculos:
            if v.contabilidade:
                chave = (v.contabilidade.id_legado, v.matricula)
                vinculos_map[chave] = v
        return vinculos_map

    def processar_dados(self, data, vinculos_map, historical_map):
        stats = {'criados': 0, 'atualizados': 0, 'erros': 0, 'sem_vinculo': 0, 'sem_contabilidade': 0}
        batch_size = 1000
        situacao_map = {1: 'A', 2: 'F', 3: 'P'} # Aberto, Fechado, Programado

        for lote in tqdm(batch_iterator(data, batch_size), total=(len(data) + batch_size - 1) // batch_size, desc="Processando Lotes"):
            with transaction.atomic():
                for row in lote:
                    try:
                        codi_emp = row['codi_emp']
                        data_inicio_periodo = row['data_inicio']

                        contabilidade = self.get_contabilidade_for_date(historical_map, codi_emp, data_inicio_periodo)
                        if not contabilidade:
                            stats['sem_contabilidade'] += 1
                            continue

                        vinculo_key = (contabilidade.id_legado, str(row['i_empregados']))
                        vinculo_obj = vinculos_map.get(vinculo_key)
                        if not vinculo_obj:
                            stats['sem_vinculo'] += 1
                            continue
                        
                        defaults = {
                            'data_inicio': data_inicio_periodo,
                            'data_fim': row['data_fim'],
                            'dias_direito': row['dias_direito'],
                            'situacao': situacao_map.get(row['situacao'], 'A')
                        }
                        
                        periodo, created = PeriodoAquisitivoFerias.objects.update_or_create(
                            contabilidade=contabilidade,
                            vinculo=vinculo_obj,
                            id_legado=str(row['i_ferias_aquisitivos']),
                            defaults=defaults
                        )

                        if created:
                            stats['criados'] += 1
                        else:
                            stats['atualizados'] += 1
                    
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Erro ao processar i_ferias_aquisitivos={row.get('i_ferias_aquisitivos')}: {e}"))
                        stats['erros'] += 1
        return stats

