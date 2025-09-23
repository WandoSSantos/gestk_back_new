#!/usr/bin/env python
"""
Script de limpeza de dados duplicados para preparar a migração.
"""

import os
import sys
import django
from django.db import transaction, connection

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestk.settings')
django.setup()

from django.apps import apps
from django.db.models import Count
from pessoas.models import PessoaJuridica, PessoaFisica

def limpar_duplicatas():
    """Remove duplicatas de pessoas e relacionamentos para permitir migração."""
    print("--- Iniciando a limpeza de dados duplicados ---")
    
    with transaction.atomic():
        # 1. Consolidar Pessoas Jurídicas (CNPJ duplicados)
        print("1. Consolidando Pessoas Jurídicas (CNPJ)...")
        
        # Usar SQL direto para melhor performance
        with connection.cursor() as cursor:
            # Buscar CNPJs duplicados
            cursor.execute("""
                SELECT cnpj, array_agg(id) as ids, COUNT(*)
                FROM pessoas_juridicas 
                WHERE cnpj IS NOT NULL AND cnpj != ''
                GROUP BY cnpj
                HAVING COUNT(*) > 1
                ORDER BY COUNT(*) DESC
            """)
            
            cnpjs_duplicados = cursor.fetchall()
            print(f"  Encontrados {len(cnpjs_duplicados)} cnpjs duplicados. Processando...")
            
            # Mapeamento para FK updates
            FK_MAP = {
                'contabil_planoconta': {'parceiro_pj': 'id'},
                'fiscal_notafiscal': {'empresa': 'id'},
                'funcionarios_funcionario': {'pessoa_juridica': 'id'},
                'cadastros_gerais_fornecedor': {'pessoa_juridica': 'id'},
                'cadastros_gerais_cliente': {'pessoa_juridica': 'id'},
                'pessoas_contratos': {'object_id': 'id'}
            }
            
            for cnpj, ids_array, count in cnpjs_duplicados:
                # Converter string array do PostgreSQL para lista Python
                import re
                ids_str = ids_array.strip('{}')
                ids_list = [x.strip() for x in ids_str.split(',') if x.strip()]
                
                if len(ids_list) <= 1:
                    continue
                    
                # Primeiro ID será o mestre
                mestre_id = ids_list[0]
                duplicados_ids = ids_list[1:]
                
                print(f"  - Consolidando cnpj {cnpj}: Mestre={mestre_id}, Duplicados={duplicados_ids}")
                
                # Atualizar todas as FKs para apontar para o mestre
                for tabela, campos in FK_MAP.items():
                    for campo, _ in campos.items():
                        cursor.execute(f"""
                            UPDATE {tabela}
                            SET {campo} = %s
                            WHERE {campo} = ANY(%s)
                        """, (mestre_id, duplicados_ids))
                
                # Deletar duplicados
                cursor.execute("""
                    DELETE FROM pessoas_juridicas 
                    WHERE id = ANY(%s)
                """, (duplicados_ids,))
        
        # 2. Consolidar Pessoas Físicas (CPF duplicados)
        print("2. Consolidando Pessoas Físicas (CPF)...")
        
        with connection.cursor() as cursor:
            # Buscar CPFs duplicados
            cursor.execute("""
                SELECT cpf, array_agg(id) as ids, COUNT(*)
                FROM pessoas_fisicas 
                WHERE cpf IS NOT NULL AND cpf != ''
                GROUP BY cpf
                HAVING COUNT(*) > 1
                ORDER BY COUNT(*) DESC
            """)
            
            cpfs_duplicados = cursor.fetchall()
            print(f"  Encontrados {len(cpfs_duplicados)} cpfs duplicados. Processando...")
            
            # Mapeamento para FK updates
            FK_MAP_PF = {
                'funcionarios_funcionario': {'pessoa_fisica': 'id'},
                'cadastros_gerais_socio': {'pessoa_fisica': 'id'},
                'pessoas_contratos': {'object_id': 'id'}
            }
            
            for cpf, ids_array, count in cpfs_duplicados:
                # Converter string array do PostgreSQL para lista Python
                ids_str = ids_array.strip('{}')
                ids_list = [x.strip() for x in ids_str.split(',') if x.strip()]
                
                if len(ids_list) <= 1:
                    continue
                    
                # Primeiro ID será o mestre
                mestre_id = ids_list[0]
                duplicados_ids = ids_list[1:]
                
                print(f"  - Consolidando cpf {cpf}: Mestre={mestre_id}, Duplicados={duplicados_ids}")
                
                # Atualizar todas as FKs para apontar para o mestre
                for tabela, campos in FK_MAP_PF.items():
                    for campo, _ in campos.items():
                        cursor.execute(f"""
                            UPDATE {tabela}
                            SET {campo} = %s
                            WHERE {campo} = ANY(%s)
                        """, (mestre_id, duplicados_ids))
                
                # Deletar duplicados
                cursor.execute("""
                    DELETE FROM pessoas_fisicas 
                    WHERE id = ANY(%s)
                """, (duplicados_ids,))
        
        # 3. Consolidar Contratos duplicados
        print("3. Consolidando Contratos duplicados...")
        
        # Buscar contratos duplicados com base em content_type e object_id
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT content_type_id, object_id, array_agg(id::text) as ids, COUNT(*)
                FROM pessoas_contratos 
                GROUP BY content_type_id, object_id
                HAVING COUNT(*) > 1
                ORDER BY COUNT(*) DESC
            """)
            
            contratos_duplicados = cursor.fetchall()
            print(f"  Encontrados {len(contratos_duplicados)} grupos de contratos duplicados. Processando...")
            
            for content_type_id, object_id, ids_array, count in contratos_duplicados:
                # Tratar o array de IDs (já vem como lista do PostgreSQL)
                if isinstance(ids_array, list):
                    ids_list = [str(x) for x in ids_array if x is not None]
                else:
                    # Fallback para string array
                    ids_str = str(ids_array).strip('{}')
                    ids_list = [x.strip() for x in ids_str.split(',') if x.strip()]
                
                if len(ids_list) <= 1:
                    continue
                    
                # Manter o primeiro contrato e deletar os outros
                mestre_id = ids_list[0]
                duplicados_ids = ids_list[1:]
                
                print(f"  - Consolidando contratos content_type={content_type_id}, object_id={object_id}: Mestre={mestre_id}, Duplicados={duplicados_ids[:3]}...")
                
                # Deletar contratos duplicados usando UUID cast
                cursor.execute("""
                    DELETE FROM pessoas_contratos 
                    WHERE id = ANY(%s::uuid[])
                """, (duplicados_ids,))
        
        print("--- Limpeza de dados concluída com sucesso! ---")
        print('Você agora pode executar o comando "python manage.py migrate" novamente.')

if __name__ == '__main__':
    limpar_duplicatas()