from django.db import transaction
from ._base import BaseETLCommand
from core.models import Contabilidade
from pessoas.models import PessoaJuridica, PessoaFisica, Contrato
from django.contrib.contenttypes.models import ContentType
import re

class Command(BaseETLCommand):
    help = 'ETL para carregar Contratos e criar Pessoas (Físicas/Jurídicas) sob demanda.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL Unificado de Contratos e Pessoas ---'))

        connection = self.get_sybase_connection()
        if not connection:
            return

        # Query para buscar todos os contratos com dados dos clientes
        query = """
        SELECT
            hc.codi_emp as id_legado_contabilidade,
            hc.i_contrato as id_legado_contrato,
            hc.data_inicio_faturamento,
            hc.data_termino,
            hc.dia_vencimento,
            hc.valor_contrato,
            ge.codi_emp as id_legado_cliente,
            ge.cgce_emp as documento,
            ge.nome_emp as nome_razao_social,
            ge.fantasia_emp
        FROM 
            BETHADBA.HRCONTRATO AS hc
        INNER JOIN
            BETHADBA.HRVCLIENTE AS hvc ON hc.i_cliente = hvc.i_cliente AND hc.codi_emp = hvc.codigo_escritorio
        INNER JOIN
            BETHADBA.GEEMPRE AS ge ON hvc.i_cliente_fixo = ge.codi_emp
        """

        self.stdout.write("Extraindo dados de Contratos do Sybase...")
        data = self.execute_query(connection, query)
        connection.close()

        if not data:
            self.stdout.write(self.style.WARNING('Nenhum contrato encontrado.'))
            return

        self.stdout.write(f"{len(data)} contratos extraídos. Iniciando o carregamento...")
        
        total_contratos_criados = 0
        total_contratos_atualizados = 0
        total_pj_criadas = 0
        total_pf_criadas = 0

        try:
            with transaction.atomic():
                for item in data:
                    documento_bruto = str(item.get('documento') or '').strip()
                    documento_limpo = re.sub(r'\D', '', documento_bruto)
                    
                    contabilidade = Contabilidade.objects.filter(id_legado=item.get('id_legado_contabilidade')).first()
                    if not contabilidade:
                        self.stdout.write(self.style.WARNING(f"Contabilidade com ID Legado {item.get('id_legado_contabilidade')} não encontrada. Pulando contrato."))
                        continue
                    
                    # A contabilidade agora é associada ao contrato, não à pessoa.
                    # A pessoa é única pelo seu documento (CNPJ/CPF) em todo o sistema.
                    if len(documento_limpo) == 14:
                        pj, created = PessoaJuridica.objects.update_or_create(
                            cnpj=documento_limpo,
                            defaults={
                                'id_legado': item.get('id_legado_cliente'),
                                'razao_social': str(item.get('nome_razao_social') or '').strip(),
                                'nome_fantasia': str(item.get('fantasia_emp') or '').strip(),
                            }
                        )
                        cliente_obj = pj
                        if created: total_pj_criadas += 1
                    
                    elif len(documento_limpo) == 11:
                        pf, created = PessoaFisica.objects.update_or_create(
                            cpf=documento_limpo,
                            defaults={
                                'id_legado': item.get('id_legado_cliente'),
                                'nome_completo': str(item.get('nome_razao_social') or '').strip(),
                            }
                        )
                        cliente_obj = pf
                        if created: total_pf_criadas += 1
                    
                    else:
                        self.stdout.write(self.style.WARNING(f"Documento inválido '{documento_bruto}' para o cliente {item.get('id_legado_cliente')}. Pulando contrato."))
                        continue
                    
                    # Cria o Contrato, que agora liga a Pessoa à Contabilidade
                    contrato_id_legado = f"{item.get('id_legado_contabilidade')}-{item.get('id_legado_contrato')}"
                    
                    # Usamos o ContentType para o relacionamento genérico
                    content_type = ContentType.objects.get_for_model(cliente_obj)

                    contrato, created = Contrato.objects.update_or_create(
                        id_legado=contrato_id_legado,
                        defaults={
                            'contabilidade': contabilidade,
                            'content_type': content_type,
                            'object_id': cliente_obj.id,
                            'data_inicio': item.get('data_inicio_faturamento'),
                            'data_termino': item.get('data_termino'),
                            'dia_vencimento': item.get('dia_vencimento'),
                            'valor_honorario': item.get('valor_contrato') or 0,
                        }
                    )
                    if created:
                        total_contratos_criados += 1
                    else:
                        total_contratos_atualizados += 1

            self.stdout.write(self.style.SUCCESS('Carregamento concluído!'))
            self.stdout.write(f'  - Pessoas Jurídicas criadas: {total_pj_criadas}')
            self.stdout.write(f'  - Pessoas Físicas criadas: {total_pf_criadas}')
            self.stdout.write(f'  - Contratos criados: {total_contratos_criados}')
            self.stdout.write(f'  - Contratos atualizados: {total_contratos_atualizados}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocorreu um erro durante o carregamento: {e}'))

        self.stdout.write(self.style.SUCCESS('--- ETL Unificado finalizado ---'))

