#!/usr/bin/env python
"""
Script para limpar duplicatas do Plano de Contas.
"""

import os
import sys
import django
from django.db import transaction

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestk.settings')
django.setup()

from contabil.models import PlanoContas
from django.db.models import Count

def limpar_duplicatas():
    """Remove duplicatas do Plano de Contas."""
    print("=" * 70)
    print("LIMPEZA DE DUPLICATAS DO PLANO DE CONTAS")
    print("=" * 70)
    
    # Encontrar duplicatas
    print("\n1. Identificando duplicatas...")
    duplicatas = PlanoContas.objects.values('contabilidade', 'id_legado').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    total_duplicatas = duplicatas.count()
    print(f"   Total de grupos duplicados: {total_duplicatas:,}")
    
    if total_duplicatas == 0:
        print("   ✓ Nenhuma duplicata encontrada!")
        return
    
    # Mostrar algumas duplicatas
    print("\n2. Exemplos de duplicatas:")
    for i, dup in enumerate(duplicatas[:5]):
        contas = PlanoContas.objects.filter(
            contabilidade_id=dup['contabilidade'], 
            id_legado=dup['id_legado']
        )
        print(f"   Grupo {i+1}: Contabilidade {dup['contabilidade']}, ID {dup['id_legado']}: {contas.count()} registros")
        for conta in contas:
            print(f"     - ID {conta.id}: {conta.nome}")
    
    # Remover duplicatas
    print(f"\n3. Removendo duplicatas...")
    total_removidas = 0
    
    with transaction.atomic():
        for dup in duplicatas:
            contas = PlanoContas.objects.filter(
                contabilidade_id=dup['contabilidade'], 
                id_legado=dup['id_legado']
            ).order_by('id')
            
            # Manter apenas o primeiro, remover os demais
            if contas.count() > 1:
                contas_lista = list(contas)
                for conta in contas_lista[1:]:  # Pular o primeiro
                    conta.delete()
                    total_removidas += 1
    
    print(f"   ✓ {total_removidas:,} registros duplicados removidos")
    
    # Verificar resultado
    print("\n4. Verificando resultado...")
    duplicatas_restantes = PlanoContas.objects.values('contabilidade', 'id_legado').annotate(
        count=Count('id')
    ).filter(count__gt=1).count()
    
    if duplicatas_restantes == 0:
        print("   ✓ Todas as duplicatas foram removidas!")
    else:
        print(f"   ⚠ Ainda restam {duplicatas_restantes} grupos duplicados")
    
    # Estatísticas finais
    total_contas = PlanoContas.objects.count()
    print(f"\n5. Estatísticas finais:")
    print(f"   Total de contas no banco: {total_contas:,}")
    
    print("\n" + "=" * 70)
    print("LIMPEZA DE DUPLICATAS CONCLUÍDA")
    print("=" * 70)

if __name__ == '__main__':
    limpar_duplicatas()
