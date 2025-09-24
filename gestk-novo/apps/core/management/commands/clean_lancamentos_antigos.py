import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.contabil.models import LancamentoContabil, Partida

class Command(BaseCommand):
    help = 'Remove todos os lançamentos contábeis com data anterior a 2019-01-01.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('--- INICIANDO LIMPEZA DE LANÇAMENTOS ANTIGOS ---'))
        
        data_corte = datetime.date(2019, 1, 1)
        batch_size = 5000
        
        self.stdout.write(f"Data de corte definida para: {data_corte.strftime('%Y-%m-%d')}")
        self.stdout.write(f"Processando em lotes de {batch_size:,} registros.")

        total_lancamentos_removidos = 0
        total_partidas_removidas = 0

        while True:
            try:
                with transaction.atomic():
                    # Encontra o próximo lote de lançamentos para remover
                    lancamentos_para_remover_ids = LancamentoContabil.objects.filter(
                        data_lancamento__lt=data_corte
                    ).values_list('id', flat=True)[:batch_size]

                    if not lancamentos_para_remover_ids:
                        self.stdout.write(self.style.SUCCESS("Nenhum lançamento antigo encontrado. Limpeza concluída."))
                        break

                    self.stdout.write(f"\nEncontrado lote de {len(lancamentos_para_remover_ids):,} lançamentos para remover...")

                    # Exclui as partidas associadas
                    partidas_deletadas = Partida.objects.filter(lancamento_id__in=lancamentos_para_remover_ids)._raw_delete(Partida.objects.db)
                    self.stdout.write(f"  -> {partidas_deletadas:,} partidas removidas.")
                    total_partidas_removidas += partidas_deletadas

                    # Exclui os lançamentos
                    lancamentos_deletados = LancamentoContabil.objects.filter(id__in=lancamentos_para_remover_ids)._raw_delete(LancamentoContabil.objects.db)
                    self.stdout.write(f"  -> {lancamentos_deletados:,} lançamentos removidos.")
                    total_lancamentos_removidos += lancamentos_deletados

                    self.stdout.write(self.style.SUCCESS(f"Total acumulado: {total_lancamentos_removidos:,} lançamentos e {total_partidas_removidas:,} partidas removidas."))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Ocorreu um erro durante a limpeza: {e}"))
                self.stdout.write(self.style.WARNING("A operação foi revertida devido ao erro. Tentando novamente..."))
                # Opcional: Adicionar um sleep se o erro persistir
                # import time
                # time.sleep(5)

        self.stdout.write(self.style.SUCCESS('\n--- LIMPEZA FINALIZADA COM SUCESSO! ---'))
        self.stdout.write(f"Total final: {total_lancamentos_removidos:,} lançamentos e {total_partidas_removidas:,} partidas removidas.")
