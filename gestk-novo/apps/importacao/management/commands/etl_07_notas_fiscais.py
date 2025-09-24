from django.db import transaction
from ._base import BaseETLCommand
from apps.core.models import Contabilidade
from apps.pessoas.models import PessoaJuridica, PessoaFisica, Contrato
from apps.fiscal.models import NotaFiscal, NotaFiscalItem
from itertools import islice
import re
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from tqdm import tqdm

def batch_iterator(iterator, batch_size):
    """Itera sobre os dados em lotes de tamanho 'batch_size'."""
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            break
        yield batch

class Command(BaseETLCommand):
    help = 'ETL para importar Notas Fiscais, Serviços e Cupons Fiscais.'

    def __init__(self):
        super().__init__()
        self.cache_pessoas = {}
        self.cache_contabilidades_parceiro = {}  # Cache para contabilidade via parceiro

    def obter_contabilidade_por_parceiro(self, documento):
        """
        Lógica CORRETA: Identifica a contabilidade baseada no CNPJ/CPF do parceiro,
        buscando o contrato mais recente onde o parceiro é cliente.
        """
        documento_limpo = re.sub(r'\D', '', str(documento or ''))
        
        if not documento_limpo or len(documento_limpo) not in [11, 14]:
            return None

        if documento_limpo in self.cache_contabilidades_parceiro:
            return self.cache_contabilidades_parceiro[documento_limpo]

        pessoa_model = PessoaJuridica if len(documento_limpo) == 14 else PessoaFisica
        filtro_documento = {'cnpj': documento_limpo} if len(documento_limpo) == 14 else {'cpf': documento_limpo}
        
        pessoas = pessoa_model.objects.filter(**filtro_documento)
        if not pessoas.exists():
            self.cache_contabilidades_parceiro[documento_limpo] = None
            return None

        content_type = ContentType.objects.get_for_model(pessoa_model)
        
        contrato = Contrato.objects.filter(
            content_type=content_type,
            object_id__in=pessoas.values_list('id', flat=True)
        ).select_related('contabilidade').order_by('-data_inicio').first()

        if contrato:
            self.cache_contabilidades_parceiro[documento_limpo] = contrato.contabilidade
            return contrato.contabilidade
            
        self.cache_contabilidades_parceiro[documento_limpo] = None
        return None

    def criar_ou_obter_pessoa(self, contabilidade, documento, nome):
        """
        Cria ou obtém uma pessoa (PJ/PF) na contabilidade correta.
        """
        documento_limpo = re.sub(r'\D', '', str(documento or ''))
        
        if not documento_limpo or len(documento_limpo) not in [11, 14]:
            return None

        chave_cache = f"{contabilidade.id}_{documento_limpo}"
        
        if chave_cache in self.cache_pessoas:
            return self.cache_pessoas[chave_cache]

        pessoa = None
        if len(documento_limpo) == 14:
            pessoa, _ = PessoaJuridica.objects.update_or_create(
                cnpj=documento_limpo,
                defaults={
                    'razao_social': str(nome or '').strip() or 'NOME NÃO INFORMADO',
                    'nome_fantasia': str(nome or '').strip() or 'NOME NÃO INFORMADO',
                }
            )
        else:
            pessoa, _ = PessoaFisica.objects.update_or_create(
                cpf=documento_limpo,
                defaults={
                    'nome_completo': str(nome or '').strip() or 'NOME NÃO INFORMADO',
                }
            )
        
        self.cache_pessoas[chave_cache] = pessoa
        return pessoa

    def determinar_cfop_item(self, cfop_nota, item_cfop):
        """
        Determina o CFOP do item baseado no tipo de operação.
        """
        if cfop_nota in ['1933', '2933']:  # Serviços
            return cfop_nota  # Para serviços, usar o CFOP da nota (1933/2933)
        return item_cfop or cfop_nota

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('--- INICIANDO ETL UNIFICADO DE DOCUMENTOS FISCAIS ---'))
        self.stdout.write(self.style.SUCCESS('='*70))

        connection = self.get_sybase_connection()
        if not connection:
            return

        query = """
        -- NOTAS DE ENTRADA (PRODUTOS)
        SELECT TOP 10
            1 as TIPO_DOC,
            EFMVEPRO.CODI_EMP as CODIGO_EMPRESA,
            EFENTRADAS.NUME_ENT as NUM_DOCUMENTO,
            EFENTRADAS.SITUACAO_ENT as SITUACAO,
            EFENTRADAS.SERI_ENT as SERIE,
            EFENTRADAS.CHAVE_NFE_ENT as CHAVE_NF,
            EFENTRADAS.DENT_ENT as DATA_EMISSAO,
            EFENTRADAS.DATA_ENTRADA as DATA_MOVIMENTO,
            EFENTRADAS.CODI_FOR as CODIGO_PARCEIRO,
            EFFORNECE.NOME_FOR as NOME_PARCEIRO,
            EFFORNECE.CGCE_FOR as CPF_CNPJ_PARCEIRO,
            EFMVEPRO.CFOP_MEP as CFOP_ITEM,
            TRIM(EFMVEPRO.CODI_PDI) as CODIGO_ITEM,
            UPPER(EFPRODUTOS.DESC_PDI) as DESCRICAO_ITEM,
            EFPRODUTOS.CNCM_PDI as NCM_ITEM,
            EFMVEPRO.QTDE_MEP as QTDE_ITEM,
            EFMVEPRO.VALOR_UNIT_MEP as VALOR_UNITARIO_ITEM,
            EFMVEPRO.VPRO_MEP as VALOR_TOTAL_ITEM,
            EFMVEPRO.VDES_MEP as VALOR_DESCONTO_ITEM,
            EFMVEPRO.VFRE_MEP as VALOR_FRETE_ITEM,
            EFMVEPRO.VDESACE_MEP as VALOR_DESP_ACES_ITEM,
            EFMVEPRO.BICMS_MEP as BASE_ICMS_ITEM,
            EFMVEPRO.ALIICMS_MEP as ALIQ_ICMS_ITEM,
            EFMVEPRO.VALOR_ICMS_MEP as VALOR_ICMS_ITEM,
            EFMVEPRO.BC_PIS_MEP as BASE_PIS_ITEM,
            EFMVEPRO.VALOR_PIS_MEP as VALOR_PIS_ITEM,
            EFMVEPRO.CST_PIS_MEP as CST_PIS_ITEM,
            EFMVEPRO.BC_COFINS_MEP as BASE_COFINS_ITEM,
            EFMVEPRO.VALOR_COFINS_MEP as VALOR_COFINS_ITEM,
            EFMVEPRO.CST_COFINS_MEP as CST_COFINS_ITEM,
            EFMVEPRO.BICMSST_MEP as BASE_ICMSST_ITEM,
            EFMVEPRO.ALIQ_ST_MEP as ALIQ_ICMSST_ITEM,
            EFMVEPRO.VALOR_SUBTRI_MEP as VALOR_ICMSST_ITEM,
            EFENTRADAS.VCON_ENT as VALOR_TOTAL_NOTA,
            NULL as CFOP_NOTA
        FROM BETHADBA.EFMVEPRO EFMVEPRO 
        INNER JOIN BETHADBA.EFENTRADAS EFENTRADAS ON EFENTRADAS.CODI_EMP = EFMVEPRO.CODI_EMP AND EFENTRADAS.CODI_ENT = EFMVEPRO.CODI_ENT
        INNER JOIN BETHADBA.EFFORNECE EFFORNECE ON EFFORNECE.CODI_EMP = EFMVEPRO.CODI_EMP AND EFFORNECE.CODI_FOR = EFENTRADAS.CODI_FOR
        INNER JOIN BETHADBA.EFPRODUTOS EFPRODUTOS ON EFPRODUTOS.CODI_EMP = EFMVEPRO.CODI_EMP AND EFPRODUTOS.CODI_PDI = EFMVEPRO.CODI_PDI
        WHERE EFENTRADAS.CHAVE_NFE_ENT IS NOT NULL AND EFENTRADAS.CHAVE_NFE_ENT != '' AND EFENTRADAS.DENT_ENT >= '2019-01-01'
        
        UNION ALL
        
        -- NOTAS DE SAÍDA (PRODUTOS)
        SELECT TOP 10
            2 as TIPO_DOC,
            EFMVSPRO.CODI_EMP as CODIGO_EMPRESA,
            EFSAIDAS.NUME_SAI as NUM_DOCUMENTO,
            EFSAIDAS.SITUACAO_SAI as SITUACAO,
            EFSAIDAS.SERI_SAI as SERIE,
            EFSAIDAS.CHAVE_NFE_SAI as CHAVE_NF,
            EFSAIDAS.DSAI_SAI as DATA_EMISSAO,
            EFSAIDAS.DATA_SAIDA as DATA_MOVIMENTO,
            EFSAIDAS.CODI_CLI as CODIGO_PARCEIRO,
            EFCLIENTES.NOME_CLI as NOME_PARCEIRO,
            EFCLIENTES.CGCE_CLI as CPF_CNPJ_PARCEIRO,
            EFMVSPRO.CFOP_MSP as CFOP_ITEM,
            TRIM(EFMVSPRO.CODI_PDI) as CODIGO_ITEM,
            UPPER(EFPRODUTOS.DESC_PDI) as DESCRICAO_ITEM,
            EFPRODUTOS.CNCM_PDI as NCM_ITEM,
            EFMVSPRO.QTDE_MSP as QTDE_ITEM,
            EFMVSPRO.VALOR_UNIT_MSP as VALOR_UNITARIO_ITEM,
            EFMVSPRO.VPRO_MSP as VALOR_TOTAL_ITEM,
            EFMVSPRO.VDES_MSP as VALOR_DESCONTO_ITEM,
            EFMVSPRO.VFRE_MSP as VALOR_FRETE_ITEM,
            EFMVSPRO.VDESACE_MSP as VALOR_DESP_ACES_ITEM,
            EFMVSPRO.BICMS_MSP as BASE_ICMS_ITEM,
            EFMVSPRO.ALIICMS_MSP as ALIQ_ICMS_ITEM,
            EFMVSPRO.VALOR_ICMS_MSP as VALOR_ICMS_ITEM,
            EFMVSPRO.BC_PIS_MSP as BASE_PIS_ITEM,
            EFMVSPRO.VALOR_PIS_MSP as VALOR_PIS_ITEM,
            EFMVSPRO.CST_PIS_MSP as CST_PIS_ITEM,
            EFMVSPRO.BC_COFINS_MSP as BASE_COFINS_ITEM,
            EFMVSPRO.VALOR_COFINS_MSP as VALOR_COFINS_ITEM,
            EFMVSPRO.CST_COFINS_MSP as CST_COFINS_ITEM,
            EFMVSPRO.BICMSST_MSP as BASE_ICMSST_ITEM,
            EFMVSPRO.ALIQ_ST_MSP as ALIQ_ICMSST_ITEM,
            EFMVSPRO.VALOR_SUBTRI_MSP as VALOR_ICMSST_ITEM,
            EFSAIDAS.VCON_SAI as VALOR_TOTAL_NOTA,
            NULL as CFOP_NOTA
        FROM BETHADBA.EFMVSPRO EFMVSPRO 
        INNER JOIN BETHADBA.EFSAIDAS EFSAIDAS ON EFSAIDAS.CODI_EMP = EFMVSPRO.CODI_EMP AND EFSAIDAS.CODI_SAI = EFMVSPRO.CODI_SAI
        INNER JOIN BETHADBA.EFCLIENTES EFCLIENTES ON EFCLIENTES.CODI_EMP = EFMVSPRO.CODI_EMP AND EFCLIENTES.CODI_CLI = EFSAIDAS.CODI_CLI
        INNER JOIN BETHADBA.EFPRODUTOS EFPRODUTOS ON EFPRODUTOS.CODI_EMP = EFMVSPRO.CODI_EMP AND EFPRODUTOS.CODI_PDI = EFMVSPRO.CODI_PDI
        WHERE EFSAIDAS.CHAVE_NFE_SAI IS NOT NULL AND EFSAIDAS.CHAVE_NFE_SAI != '' AND EFSAIDAS.DSAI_SAI >= '2019-01-01'
        
        UNION ALL
        
        -- NOTAS DE SERVIÇO (CFOPs 1933/2933)
        SELECT TOP 10
            3 as TIPO_DOC,
            EFSERVICOS.CODI_EMP as CODIGO_EMPRESA,
            EFSERVICOS.NUME_NS as NUM_DOCUMENTO,
            EFSERVICOS.SITUACAO_NS as SITUACAO,
            EFSERVICOS.SERI_NS as SERIE,
            EFSERVICOS.CHAVE_NFE_NS as CHAVE_NF,
            EFSERVICOS.DTEM_NS as DATA_EMISSAO,
            EFSERVICOS.DTPR_NS as DATA_MOVIMENTO,
            EFSERVICOS.CODI_TOM as CODIGO_PARCEIRO,
            EFTOMADORES.NOME_TOM as NOME_PARCEIRO,
            EFTOMADORES.CGCE_TOM as CPF_CNPJ_PARCEIRO,
            EFSERVICOS.CFOP_NS as CFOP_ITEM,
            TRIM(EFSERVICOS.CODI_SRV) as CODIGO_ITEM,
            UPPER(EFSERVICOS.DESC_SRV) as DESCRICAO_ITEM,
            NULL as NCM_ITEM,  -- Serviços não têm NCM
            1 as QTDE_ITEM,    -- Serviços sempre quantidade 1
            EFSERVICOS.VALOR_UNIT_NS as VALOR_UNITARIO_ITEM,
            EFSERVICOS.VTOT_NS as VALOR_TOTAL_ITEM,
            0 as VALOR_DESCONTO_ITEM,
            0 as VALOR_FRETE_ITEM,
            0 as VALOR_DESP_ACES_ITEM,
            EFSERVICOS.BICMS_NS as BASE_ICMS_ITEM,
            EFSERVICOS.ALIQ_ICMS_NS as ALIQ_ICMS_ITEM,
            EFSERVICOS.VALOR_ICMS_NS as VALOR_ICMS_ITEM,
            EFSERVICOS.BC_PIS_NS as BASE_PIS_ITEM,
            EFSERVICOS.VALOR_PIS_NS as VALOR_PIS_ITEM,
            EFSERVICOS.CST_PIS_NS as CST_PIS_ITEM,
            EFSERVICOS.BC_COFINS_NS as BASE_COFINS_ITEM,
            EFSERVICOS.VALOR_COFINS_NS as VALOR_COFINS_ITEM,
            EFSERVICOS.CST_COFINS_NS as CST_COFINS_ITEM,
            0 as BASE_ICMSST_ITEM,
            0 as ALIQ_ICMSST_ITEM,
            0 as VALOR_ICMSST_ITEM,
            EFSERVICOS.VTOT_NS as VALOR_TOTAL_NOTA,
            EFSERVICOS.CFOP_NS as CFOP_NOTA
        FROM BETHADBA.EFSERVICOS EFSERVICOS
        INNER JOIN BETHADBA.EFTOMADORES EFTOMADORES ON EFTOMADORES.CODI_EMP = EFSERVICOS.CODI_EMP AND EFTOMADORES.CODI_TOM = EFSERVICOS.CODI_TOM
        WHERE EFSERVICOS.CHAVE_NFE_NS IS NOT NULL AND EFSERVICOS.CHAVE_NFE_NS != '' 
            AND EFSERVICOS.DTEM_NS >= '2019-01-01'
            AND EFSERVICOS.CFOP_NS IN ('1933', '2933')
        """

        self.stdout.write("Executando query unificada de documentos fiscais...")
        cursor = connection.cursor()
        
        self.stdout.write("Contando registros na query...")
        # Executar a query e contar os registros no Python para evitar problemas com subquery
        cursor.execute(query)
        all_rows = cursor.fetchall()
        total_rows = len(all_rows)
        self.stdout.write(f"Total de registros a serem processados (após filtro de data): {total_rows:,}")
        
        # Resetar o cursor para o início dos dados
        data_iterator = iter(all_rows)

        total_notas_criadas = 0
        total_notas_atualizadas = 0
        total_itens_criados = 0
        BATCH_SIZE = 500
        
        notas_agrupadas = {}
        self.stdout.write("Agrupando dados por chave do documento...")
        
        for row in tqdm(data_iterator, total=total_rows, desc="Processando Registros"):
            item = dict(zip([desc[0] for desc in cursor.description], row))
            chave_nota = item['CHAVE_NF']
            if chave_nota not in notas_agrupadas:
                notas_agrupadas[chave_nota] = {'dados_nota': item, 'itens': []}
            notas_agrupadas[chave_nota]['itens'].append(item)

        self.stdout.write(f"Total de documentos únicos encontrados: {len(notas_agrupadas):,}")
        
        total_lotes = 0
        for batch in tqdm(batch_iterator(iter(notas_agrupadas.items()), BATCH_SIZE), total=len(notas_agrupadas)//BATCH_SIZE, desc="Importando Lotes"):
            total_lotes += 1
            try:
                with transaction.atomic():
                    for chave_nota, dados_agrupados in batch:
                        item_nota = dados_agrupados['dados_nota']
                        
                        contabilidade = self.obter_contabilidade_por_parceiro(documento=item_nota['CPF_CNPJ_PARCEIRO'])
                        
                        if not contabilidade:
                            self.stdout.write(self.style.WARNING(f"Contabilidade não encontrada para o parceiro {item_nota['CPF_CNPJ_PARCEIRO']}. Pulando doc {chave_nota}"))
                            continue

                        parceiro = self.criar_ou_obter_pessoa(
                            contabilidade=contabilidade,
                            documento=item_nota['CPF_CNPJ_PARCEIRO'],
                            nome=item_nota['NOME_PARCEIRO']
                        )
                        
                        if not parceiro:
                            continue

                        tipo_nota_map = {1: 'ENTRADA', 2: 'SAIDA', 3: 'SERVICO', 4: 'CUPOM'}
                        tipo_nota = tipo_nota_map.get(item_nota['TIPO_DOC'], 'SAIDA')

                        defaults = {
                            'numero_documento': str(item_nota['NUM_DOCUMENTO'] or ''),
                            'serie': str(item_nota['SERIE'] or ''),
                            'tipo_nota': tipo_nota,
                            'situacao': str(item_nota['SITUACAO'] or ''),
                            'data_emissao': item_nota['DATA_EMISSAO'],
                            'data_entrada_saida': item_nota['DATA_MOVIMENTO'],
                            'valor_total': Decimal(str(item_nota['VALOR_TOTAL_NOTA'] or 0)),
                            'id_legado_empresa': item_nota['CODIGO_EMPRESA'],
                            'id_legado_cli_for': item_nota['CODIGO_PARCEIRO'],
                        }
                        
                        if isinstance(parceiro, PessoaJuridica):
                            defaults['parceiro_pj'] = parceiro
                        else:
                            defaults['parceiro_pf'] = parceiro

                        nota_fiscal, created = NotaFiscal.objects.update_or_create(
                            contabilidade=contabilidade,
                            chave_acesso=chave_nota,
                            defaults=defaults
                        )

                        if created: total_notas_criadas += 1
                        else: total_notas_atualizadas += 1

                        nota_fiscal.itens.all().delete()
                        
                        for item_produto in dados_agrupados['itens']:
                            # Determinar tipo do item baseado no tipo da nota
                            if tipo_nota == 'SERVICO':
                                tipo_item = 'SERVICO'
                                ncm_item = None  # Serviços não têm NCM
                            else:
                                tipo_item = 'PRODUTO'
                                ncm_item = str(item_produto['NCM_ITEM'] or '')
                            
                            NotaFiscalItem.objects.create(
                                nota_fiscal=nota_fiscal,
                                tipo_item=tipo_item,
                                descricao=str(item_produto['DESCRICAO_ITEM'] or ''),
                                cfop=self.determinar_cfop_item(str(item_produto.get('CFOP_NOTA')), str(item_produto.get('CFOP_ITEM'))),
                                ncm=ncm_item,
                                quantidade=Decimal(str(item_produto['QTDE_ITEM'] or 0)),
                                valor_unitario=Decimal(str(item_produto['VALOR_UNITARIO_ITEM'] or 0)),
                                valor_total=Decimal(str(item_produto['VALOR_TOTAL_ITEM'] or 0)),
                                base_icms=Decimal(str(item_produto['BASE_ICMS_ITEM'] or 0)),
                                aliquota_icms=Decimal(str(item_produto['ALIQ_ICMS_ITEM'] or 0)),
                                valor_icms=Decimal(str(item_produto['VALOR_ICMS_ITEM'] or 0)),
                                base_icms_st=Decimal(str(item_produto['BASE_ICMSST_ITEM'] or 0)),
                                aliquota_icms_st=Decimal(str(item_produto['ALIQ_ICMSST_ITEM'] or 0)),
                                valor_icms_st=Decimal(str(item_produto['VALOR_ICMSST_ITEM'] or 0)),
                                base_ipi=0, valor_ipi=0, aliquota_ipi=0,
                                base_pis=Decimal(str(item_produto['BASE_PIS_ITEM'] or 0)),
                                aliquota_pis=0,
                                valor_pis=Decimal(str(item_produto['VALOR_PIS_ITEM'] or 0)),
                                cst_pis=str(item_produto['CST_PIS_ITEM'] or ''),
                                base_cofins=Decimal(str(item_produto['BASE_COFINS_ITEM'] or 0)),
                                aliquota_cofins=0,
                                valor_cofins=Decimal(str(item_produto['VALOR_COFINS_ITEM'] or 0)),
                                cst_cofins=str(item_produto['CST_COFINS_ITEM'] or ''),
                                valor_desconto=Decimal(str(item_produto['VALOR_DESCONTO_ITEM'] or 0)),
                                valor_frete=Decimal(str(item_produto['VALOR_FRETE_ITEM'] or 0)),
                                valor_seguro=0,
                                valor_outras_despesas=Decimal(str(item_produto['VALOR_DESP_ACES_ITEM'] or 0)),
                            )
                            total_itens_criados += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erro no lote {total_lotes}: {e}'))
                continue

        connection.close()
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('--- ESTATÍSTICAS FINAIS ---'))
        self.stdout.write(self.style.SUCCESS(f'✓ Documentos criados: {total_notas_criadas:,}'))
        self.stdout.write(self.style.SUCCESS(f'✓ Documentos atualizados: {total_notas_atualizadas:,}'))
        self.stdout.write(self.style.SUCCESS(f'✓ Itens criados: {total_itens_criados:,}'))
        self.stdout.write(self.style.SUCCESS(f'✓ Pessoas (parceiros) processadas: {len(self.cache_pessoas):,}'))
        self.stdout.write(self.style.SUCCESS(f'✓ Total de lotes processados: {total_lotes:,}'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('--- ETL UNIFICADO FINALIZADO! ---'))
        self.stdout.write(self.style.SUCCESS('='*70))
