from django.db import transaction
from ._base import BaseETLCommand
from core.models import Contabilidade
import re

class Command(BaseETLCommand):
    help = 'ETL para extrair e carregar dados de Contabilidades do Sybase (Lógica Corrigida).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL de Contabilidades (Lógica Corrigida) ---'))

        connection = self.get_sybase_connection()
        if not connection:
            return

        # Query corrigida para buscar os dados das contabilidades a partir da GEEMPRE,
        # usando a HRCONTRATO para identificar quais empresas são escritórios.
        query = """
        SELECT
            codi_emp,
            nome_emp,
            fantasia_emp,
            cgce_emp
        FROM
            BETHADBA.GEEMPRE
        WHERE 
            codi_emp IN (SELECT DISTINCT codi_emp FROM BETHADBA.HRCONTRATO)
        """

        self.stdout.write("Extraindo dados das Contabilidades (GEEMPRE)...")
        data = self.execute_query(connection, query)
        connection.close()
        
        if not data:
            self.stdout.write(self.style.WARNING('Nenhum dado extraído. ETL concluído.'))
            return

        self.stdout.write(f"{len(data)} registros de contabilidades encontrados. Iniciando o carregamento...")

        try:
            with transaction.atomic():
                total_criados = 0
                total_atualizados = 0
                
                for item in data:
                    id_legado = item.get('codi_emp')
                    cnpj_bruto = item.get('cgce_emp')
                    cnpj_limpo = re.sub(r'\D', '', (cnpj_bruto or ''))

                    if not id_legado:
                        self.stdout.write(self.style.WARNING(f"Registro ignorado: ID Legado ausente."))
                        continue
                    
                    if len(cnpj_limpo) != 14:
                         self.stdout.write(self.style.WARNING(f"Registro ignorado: ID Legado {id_legado}, CNPJ inválido '{cnpj_bruto}'"))
                         continue

                    obj, created = Contabilidade.objects.update_or_create(
                        id_legado=id_legado,
                        defaults={
                            'razao_social': (item.get('nome_emp') or '').strip(),
                            'nome_fantasia': (item.get('fantasia_emp') or '').strip(),
                            'cnpj': cnpj_limpo
                        }
                    )

                    if created:
                        total_criados += 1
                    else:
                        total_atualizados += 1

            self.stdout.write(self.style.SUCCESS('Carregamento concluído!'))
            self.stdout.write(f'  - Registros novos: {total_criados}')
            self.stdout.write(f'  - Registros atualizados: {total_atualizados}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocorreu um erro durante o carregamento: {e}'))

        self.stdout.write(self.style.SUCCESS('--- ETL de Contabilidades finalizado ---'))
