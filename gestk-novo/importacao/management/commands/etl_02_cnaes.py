from django.db import transaction
from ._base import BaseETLCommand
from cadastros_gerais.models import CNAE

class Command(BaseETLCommand):
    help = 'ETL para extrair e carregar dados de CNAEs do Sybase.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL de CNAEs ---'))

        connection = self.get_sybase_connection()
        if not connection:
            return

        query = """
        SELECT
            codigo_cnae,
            descricao
        FROM 
            BETHADBA.GECNAE
        """

        self.stdout.write("Extraindo dados de CNAE do Sybase...")
        data = self.execute_query(connection, query)
        connection.close()
        
        if not data:
            self.stdout.write(self.style.WARNING('Nenhum dado extraído. ETL concluído.'))
            return

        self.stdout.write(f"{len(data)} registros encontrados. Iniciando o carregamento...")

        try:
            with transaction.atomic():
                total_criados = 0
                total_atualizados = 0
                
                for item in data:
                    codigo = (item.get('codigo_cnae') or '').strip()
                    if not codigo:
                        continue

                    obj, created = CNAE.objects.update_or_create(
                        codigo=codigo,
                        defaults={
                            'descricao': (item.get('descricao') or '').strip(),
                        }
                    )

                    if created:
                        total_criados += 1
                    else:
                        total_atualizados += 1

            self.stdout.write(self.style.SUCCESS('Carregamento de CNAEs concluído!'))
            self.stdout.write(f'  - Registros novos: {total_criados}')
            self.stdout.write(f'  - Registros atualizados: {total_atualizados}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocorreu um erro durante o carregamento: {e}'))

        self.stdout.write(self.style.SUCCESS('--- ETL de CNAEs finalizado ---'))
