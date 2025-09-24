from django.db import transaction
from ._base import BaseETLCommand
from apps.core.models import Contabilidade
from apps.contabil.models import PlanoContas, LancamentoContabil, Partida
from apps.pessoas.models import PessoaJuridica, Contrato
from django.contrib.contenttypes.models import ContentType
from itertools import islice
import datetime
import re

def batch_iterator(iterator, batch_size):
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch: break
        yield batch

class Command(BaseETLCommand):
    help = 'ETL para carregar os Lançamentos Contábeis (bethadba.ctlancto) em lotes com criação automática de contas.'

    def __init__(self):
        super().__init__()
        self.cache_nomes_contas = {}  # Cache para nomes de contas do Sybase

    def obter_nome_conta_sybase(self, connection, codigo_conta):
        """
        Busca o nome da conta no Sybase.
        """
        if codigo_conta in self.cache_nomes_contas:
            return self.cache_nomes_contas[codigo_conta]
        
        query = """
        SELECT TOP 1 nome_cta 
        FROM BETHADBA.CTCONTAS 
        WHERE codi_cta = ?
        """
        
        cursor = connection.cursor()
        cursor.execute(query, (codigo_conta,))
        result = cursor.fetchone()
        
        if result and result[0]:
            nome = str(result[0]).strip()
            self.cache_nomes_contas[codigo_conta] = nome
            return nome
        
        return None

    def criar_conta_automatica(self, connection, contabilidade, codigo_conta, tipo='D'):
        """
        Cria uma conta automaticamente quando não existe no plano de contas.
        Busca o nome da conta no Sybase quando possível.
        """
        # Buscar nome da conta no Sybase
        nome_sybase = self.obter_nome_conta_sybase(connection, codigo_conta)
        
        if nome_sybase:
            nome_conta = nome_sybase
            # Determinar natureza baseada no nome
            nome_upper = nome_conta.upper()
            if any(palavra in nome_upper for palavra in ['RECEITA', 'VENDA', 'FATURAMENTO', 'PASSIVO', 'CAPITAL']):
                natureza = "CREDORA"
            elif str(codigo_conta).startswith(('2', '3', '4')):
                natureza = "CREDORA"
            else:
                natureza = "DEVEDORA"
        else:
            # Nome padrão se não encontrar no Sybase
            if tipo == 'D':
                nome_conta = f"Conta Débito {codigo_conta}"
                natureza = "DEVEDORA"
            else:
                nome_conta = f"Conta Crédito {codigo_conta}"
                natureza = "CREDORA"
        
        # Criar a conta
        conta = PlanoContas.objects.create(
            contabilidade=contabilidade,
            id_legado=str(codigo_conta),
            codigo=str(codigo_conta),
            nome=nome_conta,
            nivel=1,  # Conta de nível 1 (sem hierarquia)
            aceita_lancamento=True,
            tipo_conta="ANALITICA",
            natureza=natureza,
            ativo=True
        )
        
        return conta

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL para Lançamentos Contábeis (Regra de Ouro) ---'))
        self.stdout.write(self.style.WARNING("ATENÇÃO: Esta é uma importação incremental. Dados existentes serão mantidos."))

        # PASSO 1: Construir o mapa histórico de contabilidades
        self.stdout.write("\n[1/4] Construindo mapa histórico de contabilidades...")
        historical_map = self.build_historical_contabilidade_map()

        connection = self.get_sybase_connection()
        if not connection: return
        
        count_query = """
        SELECT COUNT(*)
        FROM
            BETHADBA.CTLANCTO l
        INNER JOIN
            BETHADBA.GEEMPRE e ON l.codi_emp = e.codi_emp
        WHERE
            l.data_lan IS NOT NULL 
            AND l.data_lan >= '2019-01-01'
            AND l.vlor_lan > 0
            AND e.cgce_emp IS NOT NULL AND e.cgce_emp <> ''
        """

        query = """
        SELECT TOP 100
            l.nume_lan,
            e.cgce_emp,
            l.data_lan,
            l.chis_lan,
            l.vlor_lan,
            l.cdeb_lan,
            l.ccre_lan,
            l.codi_his,
            cd.nome_cta AS nome_deb,
            cc.nome_cta AS nome_cred
        FROM
            BETHADBA.CTLANCTO l
        INNER JOIN
            BETHADBA.GEEMPRE e ON l.codi_emp = e.codi_emp
        LEFT JOIN
            BETHADBA.CTCONTAS AS cd ON l.cdeb_lan = cd.codi_cta
        LEFT JOIN
            BETHADBA.CTCONTAS AS cc ON l.ccre_lan = cc.codi_cta
        WHERE
            l.data_lan IS NOT NULL 
            AND l.data_lan >= '2019-01-01'
            AND l.vlor_lan > 0
            AND e.cgce_emp IS NOT NULL AND e.cgce_emp <> ''
        ORDER BY
            l.data_lan, l.nume_lan
        """
        
        try:
            self.stdout.write("\n[2/4] Contando o número total de lançamentos a serem importados...")
            cursor = connection.cursor()
            cursor.execute(count_query)
            total_lancamentos = cursor.fetchone()[0]
            self.stdout.write(self.style.SUCCESS(f"✓ Total de lançamentos a serem processados do Sybase: {total_lancamentos:,}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao contar lançamentos no Sybase: {e}"))
            return
            
        self.stdout.write("\n[3/4] Iniciando importação dos lançamentos...")
        cursor.execute(query)
        data_iterator = iter(lambda: cursor.fetchone(), None)

        total_lancamentos_criados = 0
        total_lancamentos_atualizados = 0
        total_contas_criadas = 0
        total_lotes = 0
        total_sem_mapeamento = 0
        BATCH_SIZE = 2500

        cache_contas = {}

        for batch in batch_iterator(data_iterator, BATCH_SIZE):
            total_lotes += 1
            
            try:
                with transaction.atomic():
                    for row in batch:
                        cnpj_bruto = str(row[1] or '')
                        documento_limpo = self.limpar_documento(cnpj_bruto)

                        # Aplicar a Regra de Ouro: buscar contabilidade no mapa histórico
                        contratos_empresa = historical_map.get(documento_limpo)
                        if not contratos_empresa:
                            total_sem_mapeamento += 1
                            continue

                        # Encontrar a contabilidade correta para a data do lançamento
                        data_lancamento = row[2]
                        if not data_lancamento:
                            total_sem_mapeamento += 1
                            continue

                        # Verificar se a empresa tem contrato nos últimos 5 anos (2019-2025)
                        # e se o lançamento está no período de importação (01/01/2019 até presente)
                        from datetime import date
                        data_limite_5_anos = date(2019, 1, 1)  # Últimos 5 anos (obrigação legal)
                        data_limite_importacao = date(2019, 1, 1)  # Período de importação
                        data_atual = date.today()
                        
                        # Verificar se o lançamento está no período de importação
                        if data_lancamento < data_limite_importacao or data_lancamento > data_atual:
                            total_sem_mapeamento += 1
                            continue

                        contabilidade = None
                        contrato_correto = None
                        contrato_valido = False
                        
                        for data_inicio, data_termino, contab, contrato in contratos_empresa:
                            # Verificar se o contrato está nos últimos 5 anos (2019-2025)
                            # Contrato é válido se começou em 2019 ou depois, ou se terminou em 2019 ou depois
                            contrato_nos_ultimos_5_anos = (
                                (data_inicio and data_inicio >= data_limite_5_anos) or
                                (data_termino and data_termino >= data_limite_5_anos) or
                                (data_inicio and data_termino and data_inicio <= data_limite_5_anos <= data_termino)
                            )
                            
                            if contrato_nos_ultimos_5_anos:
                                contrato_valido = True
                                # Verificar se o lançamento está dentro do período do contrato
                                if data_inicio and data_termino and data_inicio <= data_lancamento <= data_termino:
                                    contabilidade = contab
                                    contrato_correto = contrato
                                    break
                        
                        # Se não encontrou contrato específico para a data, mas tem contrato válido nos últimos 5 anos,
                        # usar o contrato mais recente
                        if not contabilidade and contrato_valido:
                            # Buscar o contrato mais recente dos últimos 5 anos
                            contratos_validos = [
                                (data_inicio, data_termino, contab, contrato) 
                                for data_inicio, data_termino, contab, contrato in contratos_empresa
                                if (data_inicio and data_inicio >= data_limite_5_anos) or
                                   (data_termino and data_termino >= data_limite_5_anos) or
                                   (data_inicio and data_termino and data_inicio <= data_limite_5_anos <= data_termino)
                            ]
                            
                            if contratos_validos:
                                # Ordenar por data de início (mais recente primeiro)
                                contratos_validos.sort(key=lambda x: x[0] or date.min, reverse=True)
                                data_inicio, data_termino, contabilidade, contrato_correto = contratos_validos[0]
                        
                        if not contabilidade:
                            total_sem_mapeamento += 1
                            continue
                        
                        item = {
                            'nume_lan': row[0],
                            'cnpj': cnpj_limpo,
                            'data_lan': row[2],
                            'chis_lan': row[3],
                            'vlor_lan': row[4],
                            'cdeb_lan': row[5],
                            'ccre_lan': row[6],
                            'codi_his': row[7],
                            'nome_deb': row[8],
                            'nome_cred': row[9]
                        }
                        
                        # Buscar ou criar conta débito
                        chave_conta_debito = (contabilidade.id, str(item.get('cdeb_lan')))
                        if chave_conta_debito not in cache_contas:
                            conta_debito = PlanoContas.objects.filter(
                                contabilidade=contabilidade,
                                id_legado=str(item.get('cdeb_lan'))
                            ).first()
                            
                            if not conta_debito:
                                conta_debito = self.criar_conta_automatica(connection, contabilidade, item.get('cdeb_lan'), tipo='D')
                                total_contas_criadas += 1
                            
                            cache_contas[chave_conta_debito] = conta_debito
                        else:
                            conta_debito = cache_contas[chave_conta_debito]
                        
                        # Buscar ou criar conta crédito
                        chave_conta_credito = (contabilidade.id, str(item.get('ccre_lan')))
                        if chave_conta_credito not in cache_contas:
                            conta_credito = PlanoContas.objects.filter(
                                contabilidade=contabilidade,
                                id_legado=str(item.get('ccre_lan'))
                            ).first()
                            
                            if not conta_credito:
                                conta_credito = self.criar_conta_automatica(connection, contabilidade, item.get('ccre_lan'), tipo='C')
                                total_contas_criadas += 1
                            
                            cache_contas[chave_conta_credito] = conta_credito
                        else:
                            conta_credito = cache_contas[chave_conta_credito]
                        
                        if not item.get('vlor_lan'):
                            continue
                        
                        historico_completo = ''
                        if item.get('codi_his'):
                            historico_completo = f"Código: {item.get('codi_his')} - "
                        if item.get('chis_lan'):
                            historico_completo += str(item.get('chis_lan') or '').strip()
                        
                        lancamento, created = LancamentoContabil.objects.update_or_create(
                            contabilidade=contabilidade,
                            contrato=contrato_correto,
                            numero_lancamento=str(item.get('nume_lan')),
                            defaults={
                                'data_lancamento': item.get('data_lan'),
                                'historico': historico_completo[:1000],
                                'valor_total': item.get('vlor_lan')
                            }
                        )
                        
                        if created:
                            total_lancamentos_criados += 1
                        else:
                            total_lancamentos_atualizados += 1
                        
                        Partida.objects.filter(lancamento=lancamento).delete()
                        
                        Partida.objects.create(lancamento=lancamento, conta=conta_debito, tipo='D', valor=lancamento.valor_total)
                        Partida.objects.create(lancamento=lancamento, conta=conta_credito, tipo='C', valor=lancamento.valor_total)
                
                if total_lotes % 10 == 0:
                    self.stdout.write(f"Lote {total_lotes} | Criados: {total_lancamentos_criados} | Atualizados: {total_lancamentos_atualizados} | Contas Novas: {total_contas_criadas} | Sem Mapeamento: {total_sem_mapeamento}")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro no lote {total_lotes}: {e}"))

        connection.close()
        
        self.stdout.write(self.style.SUCCESS('\n--- Resumo Final ---'))
        self.stdout.write(f'Total de lançamentos criados: {total_lancamentos_criados}')
        self.stdout.write(f'Total de lançamentos atualizados: {total_lancamentos_atualizados}')
        self.stdout.write(f'Total de lançamentos ignorados (sem mapeamento): {total_sem_mapeamento}')
        self.stdout.write(f'Total de contas criadas automaticamente: {total_contas_criadas}')
        self.stdout.write(f'Total de lotes processados: {total_lotes}')
        self.stdout.write(self.style.SUCCESS('--- ETL de Lançamentos Contábeis finalizado (Regra de Ouro) ---'))