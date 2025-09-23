from django.core.management.base import BaseCommand
from django.db import transaction

class Command(BaseCommand):
    help = 'Limpa todos os dados relacionados a Notas Fiscais e Parceiros de Negócio para a refatoração.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('--- INICIANDO LIMPEZA DE DADOS FISCAIS PARA REATORAÇÃO ---'))
        
        # Importar modelos aqui para evitar problemas de importação circular
        from fiscal.models import NotaFiscalItem, NotaFiscal
        from pessoas.models import ParceiroNegocio

        try:
            with transaction.atomic():
                self.stdout.write('Deletando Itens de Notas Fiscais...')
                count_items, _ = NotaFiscalItem.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'✓ {count_items} itens de notas fiscais deletados.'))

                self.stdout.write('Deletando Notas Fiscais...')
                count_nf, _ = NotaFiscal.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'✓ {count_nf} notas fiscais deletadas.'))

                self.stdout.write('Deletando Parceiros de Negócio...')
                count_parceiros, _ = ParceiroNegocio.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'✓ {count_parceiros} parceiros de negócio deletados.'))

            self.stdout.write(self.style.SUCCESS('\nLimpeza de dados concluída com sucesso!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocorreu um erro durante a limpeza: {e}'))
            self.stdout.write(self.style.WARNING('A transação foi revertida. Nenhum dado foi alterado.'))
        
        self.stdout.write(self.style.SUCCESS('--- FINALIZADO ---'))

