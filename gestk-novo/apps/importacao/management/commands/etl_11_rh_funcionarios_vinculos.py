from django.db import transaction
from tqdm import tqdm
from django.contrib.contenttypes.models import ContentType

from ._base import BaseETLCommand
from apps.pessoas.models import PessoaJuridica, PessoaFisica
from apps.funcionarios.models import Cargo, Departamento, CentroCusto, Funcionario, VinculoEmpregaticio

def batch_iterator(iterator, batch_size):
    # (Código do batch_iterator)
    batch = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

class Command(BaseETLCommand):
    help = 'ETL para importar Funcionários e Vínculos Empregatícios do Sybase, com regras de negócio.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL de Funcionários e Vínculos ---'))

        # PASSO 1: Construir mapas
        self.stdout.write(self.style.HTTP_INFO('\n[1/4] Construindo mapas de referência...'))
        historical_map = self.build_historical_contabilidade_map()
        cargos_map = self.build_auxiliar_map(Cargo)
        deptos_map = self.build_auxiliar_map(Departamento)
        ccustos_map = self.build_auxiliar_map(CentroCusto)
        self.stdout.write(self.style.SUCCESS("✓ Mapas construídos."))

        # PASSO 2: Extração de Dados
        connection = self.get_sybase_connection()
        if not connection: return

        self.stdout.write(self.style.HTTP_INFO('\n[2/4] Extraindo dados de Funcionários do Sybase (desde 2019)...'))
        query = """
        SELECT
            fe.codi_emp, fe.i_empregados, fe.nome, fe.cpf, fe.data_nascimento, fe.admissao, fe.matricula, fe.salario,
            fe.i_cargos, fe.i_depto, fe.i_ccustos,
            ge.cgce_emp, ge.nome_emp, ge.tins_emp
        FROM
            bethadba.foempregados fe
        JOIN
            bethadba.geempre ge ON fe.codi_emp = ge.codi_emp
        WHERE fe.admissao >= '2019-01-01'
        """
        try:
            data = self.execute_query(connection, query)
        finally:
            connection.close()
        
        if not data:
            self.stdout.write(self.style.WARNING('Nenhum funcionário encontrado no Sybase.'))
            return
        self.stdout.write(self.style.SUCCESS(f"✓ {len(data):,} registros de funcionários extraídos."))

        # PASSO 3: Processamento e Carga
        self.stdout.write(self.style.HTTP_INFO('\n[3/4] Processando e carregando dados no Gestk...'))
        stats = self.processar_dados(data, historical_map, cargos_map, deptos_map, ccustos_map)
        
        # PASSO 4: Resumo
        self.stdout.write(self.style.SUCCESS('\n--- Resumo do ETL ---'))
        self.stdout.write(f"  - Pessoas Físicas (Funcionários) Criadas: {stats['pf_criadas']}")
        self.stdout.write(f"  - Pessoas (Empregadores) Criadas: {stats['emp_criados']}")
        self.stdout.write(f"  - Funcionários Criados: {stats['func_criados']}")
        self.stdout.write(f"  - Vínculos Criados: {stats['vinc_criados']}")
        self.stdout.write(f"  - Vínculos Atualizados: {stats['vinc_atualizados']}")
        self.stdout.write(f"  - Registros sem contabilidade/contrato na data: {stats['sem_contabilidade']}")
        self.stdout.write(self.style.ERROR(f"  - Erros: {stats['erros']}"))
        self.stdout.write(self.style.SUCCESS('--- ETL de Funcionários e Vínculos Finalizado ---'))

    def processar_dados(self, data, historical_map, cargos_map, deptos_map, ccustos_map):
        stats = {'pf_criadas': 0, 'emp_criados': 0, 'func_criados': 0, 'vinc_criados': 0, 'vinc_atualizados': 0, 'erros': 0, 'sem_contabilidade': 0}
        batch_size = 500

        for lote in tqdm(batch_iterator(data, batch_size), total=(len(data) + batch_size - 1) // batch_size, desc="Processando Lotes"):
            with transaction.atomic():
                for row in lote:
                    try:
                        # 1. Resolver Tenant usando a nova lógica
                        codi_emp = row['codi_emp']
                        data_admissao = row['admissao']
                        
                        contabilidade = self.get_contabilidade_for_date(historical_map, codi_emp, data_admissao)
                        if not contabilidade:
                            stats['sem_contabilidade'] += 1
                            continue
                        
                        # 2. Garantir Empregador (PF ou PJ)
                        doc_empregador = self.limpar_documento(row['cgce_emp'])
                        empregador_obj, created = self.get_or_create_pessoa(doc_empregador, row['nome_emp'])
                        if created: stats['emp_criados'] += 1
                        if not empregador_obj: continue
                        
                        # 3. Garantir Pessoa Física (Funcionário)
                        doc_funcionario = self.limpar_documento(row['cpf'])
                        if not doc_funcionario: continue
                        pf_funcionario, created = self.get_or_create_pessoa(doc_funcionario, row['nome'], {'data_nascimento': row['data_nascimento']})
                        if created: stats['pf_criadas'] += 1
                        
                        # 4. Criar/Atualizar Funcionário
                        funcionario_obj, created = Funcionario.objects.update_or_create(
                            contabilidade=contabilidade,
                            pessoa_fisica=pf_funcionario,
                            id_legado=f"{row['codi_emp']}-{row['i_empregados']}",
                            defaults={'ativo': True}
                        )
                        if created: stats['func_criados'] += 1
                        
                        # 5. Buscar objetos de FKS
                        cargo_obj = cargos_map.get((contabilidade.id, str(row['i_cargos'])))
                        depto_obj = deptos_map.get((contabilidade.id, str(row['i_depto'])))

                        if not cargo_obj: continue # Cargo é obrigatório

                        # 6. Criar/Atualizar Vínculo
                        defaults = {
                            'matricula': str(row['matricula']),
                            'salario_base': row['salario'] or 0,
                            'cargo': cargo_obj,
                            'departamento': depto_obj,
                            'content_type': ContentType.objects.get_for_model(empregador_obj),
                            'object_id': empregador_obj.id,
                            'ativo': True # Assumindo que a query só traz ativos
                        }
                        
                        vinculo_obj, created = VinculoEmpregaticio.objects.update_or_create(
                            contabilidade=contabilidade,
                            funcionario=funcionario_obj,
                            data_admissao=row['admissao'],
                            defaults=defaults
                        )
                        if created: stats['vinc_criados'] += 1
                        else: stats['vinc_atualizados'] += 1

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Erro ao processar i_empregados={row.get('i_empregados')}: {e}"))
                        stats['erros'] += 1
        return stats
    
    def build_auxiliar_map(self, model):
        """ Cria um mapa de entidades auxiliares usando (contabilidade_id, id_legado) como chave. """
        map_dict = {}
        for item in model.objects.all().select_related('contabilidade'):
            if item.id_legado:
                map_dict[(item.contabilidade_id, item.id_legado)] = item
        return map_dict
    def get_or_create_pessoa(self, documento, nome, defaults=None):
        if not documento or len(documento) not in [11, 14]: return None, False
        model = PessoaFisica if len(documento) == 11 else PessoaJuridica
        field = 'cpf' if len(documento) == 11 else 'cnpj'
        
        extra_defaults = defaults or {}
        if model == PessoaJuridica:
            extra_defaults['razao_social'] = nome
            extra_defaults['nome_fantasia'] = nome
        else:
            extra_defaults['nome_completo'] = nome

        obj, created = model.objects.get_or_create(**{field: documento}, defaults=extra_defaults)
        return obj, created
