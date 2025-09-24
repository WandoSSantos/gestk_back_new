from django.core.management.base import BaseCommand
from django.db import connection
from funcionarios.models import GozoFerias, PeriodoAquisitivoFerias

class Command(BaseCommand):
    help = 'Limpa as tabelas de GozoFerias e PeriodoAquisitivoFerias para permitir a recriação de migrações.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Iniciando a limpeza das tabelas de Férias...'))

        try:
            with connection.cursor() as cursor:
                self.stdout.write(self.style.WARNING(f'Deletando registros de {GozoFerias._meta.db_table}...'))
                # Usamos TRUNCATE para resetar a tabela de forma eficiente
                cursor.execute(f'TRUNCATE TABLE "{GozoFerias._meta.db_table}" RESTART IDENTITY CASCADE;')
                
                self.stdout.write(self.style.WARNING(f'Deletando registros de {PeriodoAquisitivoFerias._meta.db_table}...'))
                cursor.execute(f'TRUNCATE TABLE "{PeriodoAquisitivoFerias._meta.db_table}" RESTART IDENTITY CASCADE;')

            self.stdout.write(self.style.SUCCESS('Tabelas de Férias limpas com sucesso.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocorreu um erro ao limpar as tabelas: {e}'))
