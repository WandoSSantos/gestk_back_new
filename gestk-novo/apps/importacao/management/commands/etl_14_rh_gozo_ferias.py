import re
from django.db import transaction
from tqdm import tqdm
from ._base import BaseETLCommand
from apps.funcionarios.models import PeriodoAquisitivoFerias, GozoFerias, Rubrica
from decimal import Decimal

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
    help = 'ETL para importar os Gozos de Férias e seus valores do Sybase, com regras de negócio.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL de Gozo de Férias ---'))
        connection = self.get_sybase_connection()
        if not connection: return

        try:
            self.stdout.write(self.style.HTTP_INFO('\n[1/5] Construindo mapa histórico de Contabilidades...'))
            historical_map = self.build_historical_contabilidade_map()
            self.stdout.write(self.style.SUCCESS(f"✓ Mapa histórico construído."))

            self.stdout.write(self.style.HTTP_INFO('\n[2/5] Construindo mapa de Períodos Aquisitivos...'))
            periodos_map = self.build_periodos_map()
            self.stdout.write(self.style.SUCCESS(f"✓ Mapa de Períodos Aquisitivos construído com {len(periodos_map):,} registros."))

            self.stdout.write(self.style.HTTP_INFO('\n[3/5] Construindo mapa de valores financeiros de Férias...'))
            valores_map = self.build_valores_map(connection)
            self.stdout.write(self.style.SUCCESS(f"✓ Mapa de valores construído para {len(valores_map):,} gozos de férias."))

            self.stdout.write(self.style.HTTP_INFO('\n[4/5] Extraindo dados de Gozo de Férias (desde 2019)...'))
            data = self.extract_gozo_ferias(connection)
            if not data:
                self.stdout.write(self.style.WARNING('Nenhum registro de gozo de férias encontrado.'))
                return
            self.stdout.write(self.style.SUCCESS(f"✓ {len(data):,} registros de gozo de férias extraídos."))

            self.stdout.write(self.style.HTTP_INFO('\n[5/5] Processando e carregando dados no Gestk...'))
            stats = self.processar_dados(data, periodos_map, valores_map, historical_map)

        finally:
            connection.close()

        self.stdout.write(self.style.SUCCESS('\n--- Resumo do ETL de Gozo de Férias ---'))
        self.stdout.write(f"  - Registros de Gozo Criados: {stats['criados']}")
        self.stdout.write(f"  - Registros de Gozo Atualizados: {stats['atualizados']}")
        self.stdout.write(f"  - Registros sem contabilidade/contrato na data: {stats['sem_contabilidade']}")
        self.stdout.write(f"  - Registros sem período aquisitivo correspondente: {stats['sem_periodo']}")
        self.stdout.write(self.style.ERROR(f"  - Erros: {stats['erros']}"))
        self.stdout.write(self.style.SUCCESS('--- ETL de Gozo de Férias Finalizado ---'))

    def build_periodos_map(self):
        """
        Cria um mapa de Períodos Aquisitivos usando uma chave composta
        (id_legado_contabilidade, matricula_vinculo, id_legado_periodo)
        para garantir unicidade.
        """
        periodos_map = {}
        periodos = PeriodoAquisitivoFerias.objects.select_related('vinculo__contabilidade').all()
        for p in periodos:
            if p.vinculo and p.vinculo.contabilidade:
                chave = (p.vinculo.contabilidade.id_legado, p.vinculo.matricula, p.id_legado)
                periodos_map[chave] = p
        return periodos_map

    def build_valores_map(self, connection):
        # A lógica original desta função está correta e não precisa de alterações.
        rubricas_map = {r.id_legado: r.tipo for r in Rubrica.objects.all()}
        query_movimentos = """
        SELECT fs.i_ferias_gozo, m.i_eventos, SUM(m.valor_cal) as valor_total
        FROM bethadba.FOMOVTOSERV m
        JOIN bethadba.FOBASESSERV fs ON 
            fs.codi_emp = m.codi_emp AND fs.i_empregados = m.i_empregados AND
            fs.competencia = m.data AND fs.tipo_process = m.TIPO_PROCES
        WHERE m.TIPO_PROCES = 60 AND fs.i_ferias_gozo IS NOT NULL
        GROUP BY fs.i_ferias_gozo, m.i_eventos
        """
        movimentos_data = self.execute_query(connection, query_movimentos)
        
        valores_map = {}
        for mov in movimentos_data:
            id_gozo = mov['i_ferias_gozo']
            if id_gozo not in valores_map:
                valores_map[id_gozo] = {'valor_ferias': Decimal(0), 'valor_abono': Decimal(0)}
            
            id_evento = str(mov['i_eventos'])
            valor = mov['valor_total'] or 0
            
            # Eventos de Férias e Abono
            if id_evento in ['3', '808']: # Salário Férias + Dif. Salário Férias
                valores_map[id_gozo]['valor_ferias'] += valor
            elif id_evento in ['807', '930']: # Abono Pecuniário + Adic. 1/3 Abono
                valores_map[id_gozo]['valor_abono'] += valor
        
        return valores_map

    def extract_gozo_ferias(self, connection):
        query = """
        SELECT 
            fg.codi_emp, fg.i_empregados, fg.i_ferias_aquisitivos, fg.i_ferias_gozo,
            fg.gozo_inicio, fg.gozo_fim,
            (SELECT SUM(fgt.numero_dias) FROM bethadba.FOFERIAS_GOZO_TIPO fgt WHERE fgt.i_ferias_gozo = fg.i_ferias_gozo AND fgt.i_ferias_gozo_tipo = 1) as dias_gozo,
            (SELECT SUM(fgt.numero_dias) FROM bethadba.FOFERIAS_GOZO_TIPO fgt WHERE fgt.i_ferias_gozo = fg.i_ferias_gozo AND fgt.i_ferias_gozo_tipo = 2) as dias_abono
        FROM bethadba.FOFERIAS_GOZO fg
        WHERE fg.gozo_inicio >= '2019-01-01'
        """
        return self.execute_query(connection, query)

    def processar_dados(self, data, periodos_map, valores_map, historical_map):
        stats = {'criados': 0, 'atualizados': 0, 'erros': 0, 'sem_periodo': 0, 'sem_contabilidade': 0}
        batch_size = 1000

        for lote in tqdm(batch_iterator(data, batch_size), total=(len(data) + batch_size - 1) // batch_size, desc="Processando Lotes"):
            with transaction.atomic():
                for row in lote:
                    try:
                        codi_emp = row['codi_emp']
                        data_inicio_gozo = row['gozo_inicio']

                        contabilidade = self.get_contabilidade_for_date(historical_map, codi_emp, data_inicio_gozo)
                        if not contabilidade:
                            stats['sem_contabilidade'] += 1
                            continue

                        periodo_key = (contabilidade.id_legado, str(row['i_empregados']), str(row['i_ferias_aquisitivos']))
                        periodo_aquisitivo_obj = periodos_map.get(periodo_key)
                        if not periodo_aquisitivo_obj:
                            stats['sem_periodo'] += 1
                            continue
                        
                        id_legado_gozo = row['i_ferias_gozo']
                        valores = valores_map.get(id_legado_gozo, {'valor_ferias': 0, 'valor_abono': 0})

                        defaults = {
                            'data_inicio_gozo': data_inicio_gozo,
                            'data_fim_gozo': row['gozo_fim'],
                            'dias_gozo': row['dias_gozo'] or 0,
                            'dias_abono': row['dias_abono'] or 0,
                            'valor_ferias': Decimal(valores.get('valor_ferias') or 0),
                            'valor_abono': Decimal(valores.get('valor_abono') or 0),
                        }
                        
                        gozo, created = GozoFerias.objects.update_or_create(
                            contabilidade=contabilidade,
                            periodo_aquisitivo=periodo_aquisitivo_obj,
                            id_legado=str(id_legado_gozo),
                            defaults=defaults
                        )

                        if created:
                            stats['criados'] += 1
                        else:
                            stats['atualizados'] += 1
                    
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Erro ao processar i_ferias_gozo={row.get('i_ferias_gozo')}: {e}"))
                        stats['erros'] += 1
        return stats
