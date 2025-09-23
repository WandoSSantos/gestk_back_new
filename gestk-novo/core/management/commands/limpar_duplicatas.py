import logging
from django.db import connection, transaction
from django.core.management.base import BaseCommand

# Configura um logger para registrar informações detalhadas
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Consolida registros duplicados de Pessoas Físicas e Jurídicas antes da migração que adiciona a constraint UNIQUE.'

    # Mapeamento de tabelas e colunas que podem ter Foreign Keys para os modelos de Pessoa
    FK_MAP = {
        'pessoas_juridicas': [
            ('pessoas_juridicas', 'matriz_id'),
            ('funcionarios_cargo', 'empresa_id'),
            ('funcionarios_departamento', 'empresa_id'),
            ('funcionarios_vinculoempregaticio', 'empresa_id'),
        ],
        'pessoas_fisicas': [
            ('funcionarios_funcionario', 'pessoa_fisica_id'),
        ],
    }

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando a limpeza de dados duplicados ---'))
        
        try:
            with transaction.atomic():
                self.stdout.write(self.style.NOTICE('1. Consolidando Pessoas Jurídicas (CNPJ)...'))
                self.consolidate_duplicates(
                    table='pessoas_juridicas',
                    field='cnpj',
                    pk_field='id'
                )
                
                self.stdout.write(self.style.NOTICE('2. Consolidando Pessoas Físicas (CPF)...'))
                self.consolidate_duplicates(
                    table='pessoas_fisicas',
                    field='cpf',
                    pk_field='id'
                )
                
                self.stdout.write(self.style.NOTICE('3. Consolidando Contratos (GenericForeignKey)...'))
                self.consolidate_generic_fk('pessoas_juridicas', 'cnpj')
                self.consolidate_generic_fk('pessoas_fisicas', 'cpf')

            self.stdout.write(self.style.SUCCESS('--- Limpeza de dados concluída com sucesso! ---'))
            self.stdout.write(self.style.WARNING('Você agora pode executar o comando "python manage.py migrate" novamente.'))

        except Exception as e:
            logger.exception("Ocorreu um erro durante a limpeza de duplicatas.")
            self.stdout.write(self.style.ERROR(f'A operação falhou e foi revertida. Erro: {e}'))

    def consolidate_duplicates(self, table, field, pk_field):
        with connection.cursor() as cursor:
            # Verifica se a tabela existe
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                if cursor.fetchone()[0] == 0:
                    self.stdout.write(f'  Tabela {table} está vazia ou não existe. Pulando.')
                    return
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Tabela {table} não encontrada: {e}. Pulando.'))
                return

            # Encontra todos os valores de campo que existem mais de uma vez
            cursor.execute(f"""
                SELECT {field}, COUNT(*)
                FROM {table}
                GROUP BY {field}
                HAVING COUNT(*) > 1
            """)
            duplicates = cursor.fetchall()
            
            if not duplicates:
                self.stdout.write(f'  Nenhum {field} duplicado encontrado em {table}.')
                return

            self.stdout.write(f'  Encontrados {len(duplicates)} {field}s duplicados. Processando...')

            for value, count in duplicates:
                # Para cada valor duplicado, busca todos os registros associados
                cursor.execute(f"SELECT {pk_field} FROM {table} WHERE {field} = %s ORDER BY created_at", [value])
                pks = [row[0] for row in cursor.fetchall()]
                
                if len(pks) < 2:
                    continue
                    
                master_pk = pks[0]  # O primeiro (mais antigo) será o mestre
                duplicate_pks = pks[1:] # Os restantes são duplicados a serem removidos

                self.stdout.write(f'  - Consolidando {field} {value}: Mestre={master_pk}, Duplicados={duplicate_pks}')

                # Redireciona as Foreign Keys dos duplicados para o mestre
                self.remap_foreign_keys(table, master_pk, duplicate_pks)
                
                # Deleta os registros duplicados
                if duplicate_pks:
                    placeholder = ','.join(['%s'] * len(duplicate_pks))
                    cursor.execute(f"DELETE FROM {table} WHERE {pk_field} IN ({placeholder})", duplicate_pks)

    def remap_foreign_keys(self, source_table, master_pk, duplicate_pks):
        if source_table not in self.FK_MAP or not duplicate_pks:
            return
            
        with connection.cursor() as cursor:
            for target_table, target_column in self.FK_MAP[source_table]:
                try:
                    # Atualiza a coluna de FK na tabela de destino
                    placeholder = ','.join(['%s'] * len(duplicate_pks))
                    cursor.execute(
                        f"UPDATE {target_table} SET {target_column} = %s WHERE {target_column} IN ({placeholder})",
                        [master_pk] + duplicate_pks
                    )
                    if cursor.rowcount > 0:
                        self.stdout.write(f'    - {cursor.rowcount} registros atualizados em {target_table}.{target_column}')
                except Exception as e:
                    # Ignora se a tabela ou coluna não existir
                    self.stdout.write(self.style.WARNING(f'    - Aviso ao atualizar {target_table}.{target_column}: {e}'))

    def consolidate_generic_fk(self, source_table, source_field):
        """Trata o caso especial da GenericForeignKey na tabela de contratos."""
        with connection.cursor() as cursor:
            try:
                # Obtém o content_type_id para o modelo de origem
                model_name = source_table.replace('pessoas_', '').rstrip('s')  # pessoas_juridicas -> juridica
                cursor.execute("SELECT id FROM django_content_type WHERE app_label = 'pessoas' AND model = %s", [model_name])
                content_type_result = cursor.fetchone()
                if not content_type_result:
                    self.stdout.write(self.style.WARNING(f'    - ContentType para {source_table} não encontrado. Pulando consolidação de GenericFK.'))
                    return
                content_type_id = content_type_result[0]

                # Verifica se a tabela de contratos existe
                cursor.execute("SELECT COUNT(*) FROM pessoas_contratos")
                if cursor.fetchone()[0] == 0:
                    self.stdout.write(f'    - Tabela pessoas_contratos está vazia. Pulando consolidação de GenericFK.')
                    return

                # Encontra duplicatas na tabela de contratos para este tipo de conteúdo
                cursor.execute(f"""
                    SELECT t.{source_field}, COUNT(c.id)
                    FROM pessoas_contratos c
                    JOIN {source_table} t ON CAST(c.object_id AS VARCHAR(36)) = CAST(t.id AS VARCHAR(36))
                    WHERE c.content_type_id = %s
                    GROUP BY t.{source_field}
                    HAVING COUNT(c.id) > 1
                """, [content_type_id])
                
                duplicates = cursor.fetchall()

                for value, count in duplicates:
                    # Obtém os IDs dos contratos e os IDs dos objetos (Pessoa)
                    cursor.execute(f"""
                        SELECT c.id, c.object_id
                        FROM pessoas_contratos c
                        JOIN {source_table} t ON CAST(c.object_id AS VARCHAR(36)) = CAST(t.id AS VARCHAR(36))
                        WHERE c.content_type_id = %s AND t.{source_field} = %s
                        ORDER BY t.created_at
                    """, [content_type_id, value])
                    
                    results = cursor.fetchall()
                    if not results:
                        continue
                        
                    master_contract_id, master_object_id = results[0]
                    duplicate_contracts = results[1:]

                    # Deleta os contratos duplicados, mantendo o mais antigo
                    for contract_id, object_id in duplicate_contracts:
                        cursor.execute("DELETE FROM pessoas_contratos WHERE id = %s", [contract_id])
                        self.stdout.write(f'    - Contrato duplicado {contract_id} para {source_field} {value} removido.')
                        
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'    - Erro ao consolidar GenericFK para {source_table}: {e}'))