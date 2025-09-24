import re
from django.db import transaction
from tqdm import tqdm
from ._base import BaseETLCommand
from apps.funcionarios.models import Cargo, VinculoEmpregaticio, HistoricoSalario, HistoricoCargo

class Command(BaseETLCommand):
    help = 'ETL para importar Históricos de Salário e Cargo do Sybase, com regras de negócio.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL de Históricos de RH ---'))
        connection = self.get_sybase_connection()
        if not connection: return

        try:
            self.stdout.write(self.style.HTTP_INFO('\n[1/3] Construindo mapas de referência...'))
            historical_map = self.build_historical_contabilidade_map()
            vinculos_map = self.build_vinculos_map()
            cargos_map = self.build_cargos_map()
            self.stdout.write(self.style.SUCCESS("✓ Mapas construídos."))

            self.processar_historico_salarios(connection, historical_map, vinculos_map)
            self.processar_historico_cargos(connection, historical_map, vinculos_map, cargos_map)
        
        finally:
            connection.close()
        self.stdout.write(self.style.SUCCESS('\n--- ETL de Históricos de RH Finalizado ---'))

    def processar_historico_salarios(self, connection, historical_map, vinculos_map):
        self.stdout.write(self.style.HTTP_INFO('\n[2/3] Processando Histórico de Salários (desde 2019)...'))
        query = """
        SELECT a.codi_emp, a.i_empregados, a.competencia, a.novo_salario, a.motivo
        FROM bethadba.foaltesal a
        WHERE a.competencia >= '2019-01-01'
        """
        data = self.execute_query(connection, query)
        stats = {'criados': 0, 'atualizados': 0, 'erros': 0, 'sem_vinculo': 0, 'sem_contabilidade': 0}

        for row in tqdm(data, desc="Processando Hist. Salários"):
            try:
                codi_emp = row['codi_emp']
                data_mudanca = row['competencia']

                contabilidade = self.get_contabilidade_for_date(historical_map, codi_emp, data_mudanca)
                if not contabilidade:
                    stats['sem_contabilidade'] += 1
                    continue

                vinculo_key = (contabilidade.id_legado, str(row['i_empregados']))
                vinculo_obj = vinculos_map.get(vinculo_key)
                if not vinculo_obj:
                    stats['sem_vinculo'] += 1
                    continue

                obj, created = HistoricoSalario.objects.update_or_create(
                    vinculo=vinculo_obj,
                    data_mudanca=data_mudanca,
                    defaults={
                        'salario_novo': row['novo_salario'] or 0,
                        'motivo': row['motivo']
                    }
                )
                if created: stats['criados'] += 1
                else: stats['atualizados'] += 1
            except Exception:
                stats['erros'] += 1
        
        self.stdout.write(self.style.SUCCESS(f"✓ Histórico de Salários: {stats['criados']} criados, {stats['atualizados']} atualizados, {stats['sem_vinculo']} sem vínculo, {stats['erros']} erros."))

    def processar_historico_cargos(self, connection, historical_map, vinculos_map, cargos_map):
        self.stdout.write(self.style.HTTP_INFO('\n[3/3] Processando Histórico de Cargos (desde 2019)...'))
        query = """
        SELECT t.codi_emp, t.i_empregados, t.data_troca, t.novo_codigo
        FROM bethadba.fotrocas t
        WHERE t.tabela_troca = 2 AND t.data_troca >= '2019-01-01'
        """
        data = self.execute_query(connection, query)
        stats = {'criados': 0, 'atualizados': 0, 'erros': 0, 'sem_vinculo': 0, 'sem_cargo': 0, 'sem_contabilidade': 0}

        for row in tqdm(data, desc="Processando Hist. Cargos"):
            try:
                codi_emp = row['codi_emp']
                data_mudanca = row['data_troca']

                contabilidade = self.get_contabilidade_for_date(historical_map, codi_emp, data_mudanca)
                if not contabilidade:
                    stats['sem_contabilidade'] += 1
                    continue

                vinculo_key = (contabilidade.id_legado, str(row['i_empregados']))
                vinculo_obj = vinculos_map.get(vinculo_key)
                if not vinculo_obj:
                    stats['sem_vinculo'] += 1
                    continue
                
                cargo_novo_key = (contabilidade.id, str(row['novo_codigo']))
                cargo_novo_obj = cargos_map.get(cargo_novo_key)
                if not cargo_novo_obj:
                    stats['sem_cargo'] += 1
                    continue

                obj, created = HistoricoCargo.objects.update_or_create(
                    vinculo=vinculo_obj,
                    data_mudanca=data_mudanca,
                    defaults={'cargo_novo': cargo_novo_obj}
                )
                if created: stats['criados'] += 1
                else: stats['atualizados'] += 1
            except Exception:
                stats['erros'] += 1
        
        self.stdout.write(self.style.SUCCESS(f"✓ Histórico de Cargos: {stats['criados']} criados, {stats['atualizados']} atualizados, {stats['sem_vinculo']} sem vínculo, {stats['sem_cargo']} sem cargo, {stats['erros']} erros."))

    def build_vinculos_map(self):
        """ Cria um mapa de Vínculos usando (id_legado_contabilidade, matricula) como chave. """
        map_dict = {}
        for vinculo in VinculoEmpregaticio.objects.select_related('contabilidade').all():
            if vinculo.contabilidade:
                map_dict[(vinculo.contabilidade.id_legado, vinculo.matricula)] = vinculo
        return map_dict
    
    def build_cargos_map(self):
        """ Cria um mapa de Cargos usando (contabilidade_id, id_legado_cargo) como chave. """
        map_dict = {}
        for item in Cargo.objects.all():
            if item.id_legado:
                map_dict[(item.contabilidade_id, item.id_legado)] = item
        return map_dict
