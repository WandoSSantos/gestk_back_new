import logging
from django.db import transaction
from django.core.management.base import BaseCommand
from ._base import BaseETLCommand
from core.models import Contabilidade
from pessoas.models import PessoaJuridica, PessoaFisica
from pessoas.services import get_or_create_parceiro, associar_cliente_a_contabilidade
from fiscal.models import NotaFiscal, NotaFiscalItem
from tqdm import tqdm

# Configuração do logger
logger = logging.getLogger(__name__)

class Command(BaseETLCommand):
    help = 'ETL robusto para extrair e carregar Notas Fiscais e seus itens do sistema legado.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL Robusto de Notas Fiscais ---'))
        
        connection = self.get_sybase_connection()
        if not connection:
            return

        # 1. Extração de dados
        query = self.get_unified_query()
        self.stdout.write("Extraindo dados unificados de notas fiscais do Sybase...")
        notas_data = self.execute_query(connection, query)
        
        if not notas_data:
            self.stdout.write(self.style.WARNING('Nenhuma nota fiscal encontrada para importação.'))
            return

        self.stdout.write(f"{len(notas_data)} registros de notas fiscais encontrados. Iniciando o carregamento...")

        # 2. Processamento e Carregamento
        erros = []
        sucessos = 0
        
        for nota_raw in tqdm(notas_data, desc="Processando Notas Fiscais"):
            try:
                with transaction.atomic():
                    # Identifica a contabilidade e a empresa principal da nota
                    contabilidade = Contabilidade.objects.get(id_legado=nota_raw['id_legado_contabilidade'])
                    
                    # Garante que a empresa principal (cliente da contabilidade) exista
                    empresa_principal, _ = get_or_create_parceiro(
                        documento=nota_raw['cnpj_empresa_principal'],
                        nome=nota_raw['razao_social_empresa_principal']
                    )
                    associar_cliente_a_contabilidade(empresa_principal, contabilidade)

                    # Lógica do Parceiro de Negócio (emitente/destinatário)
                    parceiro, _ = get_or_create_parceiro(
                        documento=nota_raw['parceiro_documento'],
                        nome=nota_raw['parceiro_nome']
                    )

                    # Cria ou atualiza a Nota Fiscal
                    nota_fiscal, created = NotaFiscal.objects.update_or_create(
                        chave_acesso=nota_raw.get('chave_acesso'),
                        defaults={
                            'contabilidade': contabilidade,
                            'empresa': empresa_principal,
                            'parceiro': parceiro,
                            'tipo_nota': nota_raw['tipo_nota'],
                            'numero_documento': nota_raw['numero_documento'],
                            'serie': nota_raw['serie'],
                            'data_emissao': nota_raw['data_emissao'],
                            'data_entrada_saida': nota_raw.get('data_entrada_saida'),
                            'valor_total': nota_raw['valor_total'],
                            'situacao': nota_raw.get('situacao'),
                            'id_legado_nota': nota_raw.get('id_legado_nota'),
                        }
                    )

                    # Processa os itens da nota (apenas se a nota for nova para evitar duplicatas)
                    if created and nota_raw.get('id_legado_nota'):
                        query_itens = self.get_items_query(nota_raw['id_legado_nota'], nota_raw['tipo_nota'])
                        itens_data = self.execute_query(connection, query_itens)
                        
                        itens_para_criar = [
                            NotaFiscalItem(
                                nota_fiscal=nota_fiscal,
                                descricao=item.get('descricao'),
                                cfop=item.get('cfop'),
                                cst=item.get('cst'),
                                ncm=item.get('ncm'),
                                quantidade=item.get('quantidade', 0),
                                valor_unitario=item.get('valor_unitario', 0),
                                valor_total=item.get('valor_total_item', 0),
                                # Adicionar outros campos fiscais aqui
                            ) for item in itens_data
                        ]
                        if itens_para_criar:
                            NotaFiscalItem.objects.bulk_create(itens_para_criar)
                    
                    sucessos += 1

            except Exception as e:
                error_info = {
                    'id_legado_nota': nota_raw.get('id_legado_nota'),
                    'chave_acesso': nota_raw.get('chave_acesso'),
                    'erro': str(e)
                }
                erros.append(error_info)
                logger.error(f"Falha ao processar nota {nota_raw.get('id_legado_nota')}: {e}")

        connection.close()
        self._log_summary(sucessos, erros)
        self.stdout.write(self.style.SUCCESS('--- ETL Robusto de Notas Fiscais finalizado ---'))

    def get_unified_query(self):
        """
        Monta a query SQL para unificar notas de entrada, saída e serviços.
        Esta query é um exemplo e deve ser adaptada à estrutura real do banco Sybase.
        """
        return """
        -- Exemplo para Notas de Saída (Produtos)
        SELECT
            'SAIDA' AS tipo_nota,
            nf.chave_nfe AS chave_acesso,
            nf.nume_nf AS numero_documento,
            nf.serie_nf AS serie,
            nf.dtem_nf AS data_emissao,
            nf.dtsa_nf AS data_entrada_saida,
            cli.cgce_pessoa AS parceiro_documento,
            cli.nome_pessoa AS parceiro_nome,
            emp.cgce_emp AS cnpj_empresa_principal,
            emp.nome_emp AS razao_social_empresa_principal,
            nf.vltot_nf AS valor_total,
            nf.codi_sit AS situacao,
            emp.codi_emp AS id_legado_contabilidade,
            nf.codi_nf AS id_legado_nota
        FROM BETHADBA.FSNOTAS_SAIDA nf
        JOIN BETHADBA.GEEMPRE emp ON nf.codi_emp = emp.codi_emp
        JOIN BETHADBA.GEPESSOA cli ON nf.codi_pessoa = cli.codi_pessoa

        UNION ALL

        -- Exemplo para Notas de Entrada (Produtos)
        SELECT
            'ENTRADA' AS tipo_nota,
            ne.chave_nfe AS chave_acesso,
            ne.nume_ne AS numero_documento,
            ne.serie_ne AS serie,
            ne.dtem_ne AS data_emissao,
            ne.dten_ne AS data_entrada_saida,
            forn.cgce_pessoa AS parceiro_documento,
            forn.nome_pessoa AS parceiro_nome,
            emp.cgce_emp AS cnpj_empresa_principal,
            emp.nome_emp AS razao_social_empresa_principal,
            ne.vltot_ne AS valor_total,
            ne.codi_sit AS situacao,
            emp.codi_emp AS id_legado_contabilidade,
            ne.codi_ne AS id_legado_nota
        FROM BETHADBA.FSNOTAS_ENTRADA ne
        JOIN BETHADBA.GEEMPRE emp ON ne.codi_emp = emp.codi_emp
        JOIN BETHADBA.GEPESSOA forn ON ne.codi_pessoa = forn.codi_pessoa

        UNION ALL

        -- Exemplo para Notas de Serviço
        SELECT
            'SERVICO' AS tipo_nota,
            ns.chave_nfe AS chave_acesso,
            ns.nume_ns AS numero_documento,
            ns.serie_ns AS serie,
            ns.dtem_ns AS data_emissao,
            ns.dtpr_ns AS data_entrada_saida,
            tom.cgce_pessoa AS parceiro_documento,
            tom.nome_pessoa AS parceiro_nome,
            emp.cgce_emp AS cnpj_empresa_principal,
            emp.nome_emp AS razao_social_empresa_principal,
            ns.vltot_ns AS valor_total,
            ns.codi_sit AS situacao,
            emp.codi_emp AS id_legado_contabilidade,
            ns.codi_ns AS id_legado_nota
        FROM BETHADBA.FSSERVICOS ns
        JOIN BETHADBA.GEEMPRE emp ON ns.codi_emp = emp.codi_emp
        JOIN BETHADBA.GEPESSOA tom ON ns.codi_tomador = tom.codi_pessoa;
        """

    def get_items_query(self, id_legado_nota, tipo_nota):
        """
        Retorna a query para buscar os itens de uma nota específica.
        """
        if tipo_nota == 'SAIDA':
            return f"SELECT desc_item, cfop, cst, ncm, qtde, vrunit, vltot FROM BETHADBA.FSITENS_SAIDA WHERE codi_nf = {id_legado_nota}"
        elif tipo_nota == 'ENTRADA':
            return f"SELECT desc_item, cfop, cst, ncm, qtde, vrunit, vltot FROM BETHADBA.FSITENS_ENTRADA WHERE codi_ne = {id_legado_nota}"
        elif tipo_nota == 'SERVICO':
            return f"SELECT desc_servico as desc_item, cfop, cst, 1 as qtde, vltot as vrunit, vltot FROM BETHADBA.FSITENS_SERVICO WHERE codi_ns = {id_legado_nota}"
        return ""

    def _log_summary(self, sucessos, erros):
        self.stdout.write(self.style.SUCCESS(f'Carregamento concluído!'))
        self.stdout.write(f'  - Registros processados com sucesso: {sucessos}')
        self.stdout.write(self.style.WARNING(f'  - Registros com erro: {len(erros)}'))
        
        if erros:
            self.stdout.write(self.style.ERROR('--- Detalhes dos Erros ---'))
            for erro in erros:
                self.stdout.write(f"  - ID Legado: {erro['id_legado_nota']}, Chave: {erro['chave_acesso']}, Erro: {erro['erro']}")
