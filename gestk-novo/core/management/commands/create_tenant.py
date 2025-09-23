from django.core.management.base import BaseCommand
from core.models import Contabilidade
import os

class Command(BaseCommand):
    help = 'Cria a primeira Contabilidade (tenant principal) no sistema.'

    def handle(self, *args, **options):
        if Contabilidade.objects.exists():
            self.stdout.write(self.style.WARNING('Uma contabilidade já existe. Nenhuma ação foi tomada.'))
            return

        self.stdout.write("Nenhuma contabilidade encontrada. Criando a contabilidade principal...")
        
        try:
            razao_social = os.environ.get('GESTAO_RAZAO_SOCIAL', 'Contabilidade Matriz LTDA')
            cnpj = os.environ.get('GESTAO_CNPJ', '00000000000000')

            contabilidade = Contabilidade.objects.create(
                razao_social=razao_social,
                nome_fantasia='Matriz',
                cnpj=cnpj,
                ativo=True
            )
            self.stdout.write(self.style.SUCCESS(f'Contabilidade "{contabilidade.razao_social}" criada com sucesso!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocorreu um erro ao criar a contabilidade: {e}'))

