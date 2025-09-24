import re
from django.db import transaction
from tqdm import tqdm
from django.contrib.contenttypes.models import ContentType

from ._base import BaseETLCommand
from core.models import Contabilidade
from pessoas.models import PessoaJuridica, PessoaFisica, Contrato
from funcionarios.models import Rubrica

def batch_iterator(iterator, batch_size):
    """Gera lotes de um iterador."""
    batch = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

class Command(BaseETLCommand):
    help = 'ETL para importar as Rubricas (Eventos) de RH do Sybase.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL de Rubricas de RH ---'))

        self.stdout.write(self.style.HTTP_INFO('\n[1/3] Construindo mapas de CNPJ/CPF para Contabilidade...'))
        cnpj_map, cpf_map = self.build_contabilidade_maps()
        self.stdout.write(self.style.SUCCESS(f"✓ Mapas construídos com {len(cnpj_map):,} CNPJs e {len(cpf_map):,} CPFs."))

        connection = self.get_sybase_connection()
        if not connection: return

        self.stdout.write(self.style.HTTP_INFO('\n[2/3] Extraindo dados de Rubricas (foeventos) do Sybase...'))
        
        query = """
        SELECT ev.codi_emp, ev.i_eventos, ev.nome, ev.prov_desc, ev.base_inss, ev.base_irrf, ev.base_fgts, ev.situacao, e.cgce_emp
        FROM bethadba.foeventos ev
        JOIN bethadba.geempre e ON ev.codi_emp = e.codi_emp
        """
        
        try:
            data = self.execute_query(connection, query)
        finally:
            connection.close()
        
        if not data:
            self.stdout.write(self.style.WARNING('Nenhuma rubrica encontrada no Sybase.'))
            return
            
        self.stdout.write(self.style.SUCCESS(f"✓ {len(data):,} registros de rubricas extraídos."))

        self.stdout.write(self.style.HTTP_INFO('\n[3/3] Processando e carregando dados no Gestk...'))
        
        stats = {'criados': 0, 'atualizados': 0, 'erros': 0, 'sem_contabilidade': 0}
        batch_size = 1000

        for lote in tqdm(batch_iterator(data, batch_size), total=(len(data) + batch_size - 1) // batch_size, desc="Processando Lotes de Rubricas"):
            with transaction.atomic():
                for row in lote:
                    try:
                        documento_empregador = self.limpar_documento(row['cgce_emp'])
                        contabilidade = cpf_map.get(documento_empregador) if len(documento_empregador) == 11 else cnpj_map.get(documento_empregador)
                        
                        if not contabilidade:
                            stats['sem_contabilidade'] += 1
                            continue
                        
                        # Mapeando o tipo de provento/desconto
                        tipo_rubrica = 'B' # Default para 'Base'
                        if row['prov_desc'] == 1:
                            tipo_rubrica = 'P' # Provento
                        elif row['prov_desc'] == 2:
                            tipo_rubrica = 'D' # Desconto

                        defaults = {
                            'nome': row['nome'],
                            'tipo': tipo_rubrica,
                            'incide_inss': True if row['base_inss'] == 'S' else False,
                            'incide_irrf': True if row['base_irrf'] == 'S' else False,
                            'incide_fgts': True if row['base_fgts'] == 'S' else False,
                            'ativo': True if row['situacao'] == 'A' else False
                        }
                        
                        rubrica, created = Rubrica.objects.update_or_create(
                            contabilidade=contabilidade,
                            id_legado=str(row['i_eventos']),
                            defaults=defaults
                        )

                        if created:
                            stats['criados'] += 1
                        else:
                            stats['atualizados'] += 1
                    
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Erro ao processar rubrica com i_eventos={row.get('i_eventos')}: {e}"))
                        stats['erros'] += 1

        self.stdout.write(self.style.SUCCESS('\n--- Resumo do ETL de Rubricas ---'))
        self.stdout.write(f"  - Rubricas Criadas: {stats['criados']}")
        self.stdout.write(f"  - Rubricas Atualizadas: {stats['atualizados']}")
        self.stdout.write(f"  - Registros sem contabilidade mapeada: {stats['sem_contabilidade']}")
        self.stdout.write(self.style.ERROR(f"  - Erros: {stats['erros']}"))
        self.stdout.write(self.style.SUCCESS('--- ETL de Rubricas de RH Finalizado ---'))

    def build_contabilidade_maps(self):
        cnpj_map = {}
        cpf_map = {}
        pj_content_type = ContentType.objects.get_for_model(PessoaJuridica)
        contratos_pj = Contrato.objects.filter(content_type=pj_content_type, ativo=True).order_by('object_id', '-data_inicio').distinct('object_id').select_related('contabilidade')
        
        pj_ids = [c.object_id for c in contratos_pj]
        pessoas_juridicas = PessoaJuridica.objects.filter(id__in=pj_ids).in_bulk()

        for contrato in contratos_pj:
            pessoa = pessoas_juridicas.get(contrato.object_id)
            if pessoa:
                cnpj_limpo = self.limpar_documento(pessoa.cnpj)
                if cnpj_limpo:
                    cnpj_map[cnpj_limpo] = contrato.contabilidade

        pf_content_type = ContentType.objects.get_for_model(PessoaFisica)
        contratos_pf = Contrato.objects.filter(content_type=pf_content_type, ativo=True).order_by('object_id', '-data_inicio').distinct('object_id').select_related('contabilidade')
        
        pf_ids = [c.object_id for c in contratos_pf]
        pessoas_fisicas = PessoaFisica.objects.filter(id__in=pf_ids).in_bulk()

        for contrato in contratos_pf:
            pessoa = pessoas_fisicas.get(contrato.object_id)
            if pessoa:
                cpf_limpo = self.limpar_documento(pessoa.cpf)
                if cpf_limpo:
                    cpf_map[cpf_limpo] = contrato.contabilidade
        
        return cnpj_map, cpf_map
    
    def limpar_documento(self, documento):
        return re.sub(r'\D', '', str(documento or ''))
