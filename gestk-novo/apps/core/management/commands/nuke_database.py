from django.core.management.base import BaseCommand
from django.db import connection, transaction
from contabil.models import Partida, LancamentoContabil
import warnings

class Command(BaseCommand):
    help = 'Apaga TODOS os dados das tabelas de Partidas e Lançamentos Contábeis usando TRUNCATE.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('--- ATENÇÃO: OPERAÇÃO DE ALTO RISCO ---'))
        self.stdout.write(self.style.WARNING('Este comando irá apagar PERMANENTEMENTE todos os dados das tabelas:'))
        self.stdout.write(self.style.WARNING(f'  - {Partida._meta.db_table}'))
        self.stdout.write(self.style.WARNING(f'  - {LancamentoContabil._meta.db_table}'))
        self.stdout.write(self.style.WARNING('=' * 70))

        confirmation = input("Você tem certeza que deseja continuar? [s/N]: ")
        if confirmation.lower() != 's':
            self.stdout.write(self.style.ERROR("Operação cancelada pelo usuário."))
            return

        self.stdout.write(self.style.SUCCESS("\nIniciando a limpeza..."))

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    self.stdout.write(f"Limpando a tabela '{Partida._meta.db_table}'...")
                    
                    # Ignorar avisos sobre TRUNCATE em transação
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        cursor.execute(f'TRUNCATE TABLE "{Partida._meta.db_table}" RESTART IDENTITY CASCADE;')
                    
                    self.stdout.write(f"Limpando a tabela '{LancamentoContabil._meta.db_table}'...")
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        cursor.execute(f'TRUNCATE TABLE "{LancamentoContabil._meta.db_table}" RESTART IDENTITY CASCADE;')

            self.stdout.write(self.style.SUCCESS('\n--- LIMPEZA COMPLETA REALIZADA COM SUCESSO! ---'))
            self.stdout.write("As tabelas de lançamentos e partidas estão vazias.")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nOcorreu um erro durante a operação de TRUNCATE: {e}"))
            self.stdout.write(self.style.WARNING("A operação foi revertida devido ao erro."))

