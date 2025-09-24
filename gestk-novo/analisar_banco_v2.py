#!/usr/bin/env python3
"""
Script para analisar a estrutura do banco de dados db_gestk
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestk.settings')
django.setup()

from django.db import connection
from apps.core.models import Contabilidade, Usuario
from apps.pessoas.models import PessoaJuridica, PessoaFisica, Contrato
from apps.contabil.models import LancamentoContabil
from apps.fiscal.models import NotaFiscal
from apps.funcionarios.models import Funcionario

def analisar_tabelas():
    """Analisar todas as tabelas do banco"""
    
    print("🔍 ANÁLISE DO BANCO DE DADOS DB_GESTK")
    print("=" * 60)
    
    # Usar Django ORM para contar registros
    print(f"\n📊 CONTAGEM DE REGISTROS:")
    print("-" * 40)
    
    try:
        contabilidades = Contabilidade.objects.count()
        print(f"✅ Contabilidades: {contabilidades:,}")
    except Exception as e:
        print(f"❌ Contabilidades: ERRO - {e}")
    
    try:
        usuarios = Usuario.objects.count()
        print(f"✅ Usuários: {usuarios:,}")
    except Exception as e:
        print(f"❌ Usuários: ERRO - {e}")
    
    try:
        pessoas_juridicas = PessoaJuridica.objects.count()
        print(f"✅ Pessoas Jurídicas: {pessoas_juridicas:,}")
    except Exception as e:
        print(f"❌ Pessoas Jurídicas: ERRO - {e}")
    
    try:
        pessoas_fisicas = PessoaFisica.objects.count()
        print(f"✅ Pessoas Físicas: {pessoas_fisicas:,}")
    except Exception as e:
        print(f"❌ Pessoas Físicas: ERRO - {e}")
    
    try:
        contratos = Contrato.objects.count()
        print(f"✅ Contratos: {contratos:,}")
    except Exception as e:
        print(f"❌ Contratos: ERRO - {e}")
    
    try:
        lancamentos = LancamentoContabil.objects.count()
        print(f"✅ Lançamentos Contábeis: {lancamentos:,}")
    except Exception as e:
        print(f"❌ Lançamentos Contábeis: ERRO - {e}")
    
    try:
        notas_fiscais = NotaFiscal.objects.count()
        print(f"✅ Notas Fiscais: {notas_fiscais:,}")
    except Exception as e:
        print(f"❌ Notas Fiscais: ERRO - {e}")
    
    try:
        funcionarios = Funcionario.objects.count()
        print(f"✅ Funcionários: {funcionarios:,}")
    except Exception as e:
        print(f"❌ Funcionários: ERRO - {e}")
    
    print("\n" + "=" * 60)
    print("🏢 ANÁLISE DE CARTEIRA (Clientes por Contabilidade)")
    print("=" * 60)
    
    # Analisar carteira
    try:
        contabilidades = Contabilidade.objects.all()
        
        for contabilidade in contabilidades:
            contratos_ativos = Contrato.objects.filter(
                contabilidade=contabilidade, 
                ativo=True
            ).count()
            
            contratos_inativos = Contrato.objects.filter(
                contabilidade=contabilidade, 
                ativo=False
            ).count()
            
            total_clientes = contratos_ativos + contratos_inativos
            
            print(f"📊 {contabilidade.razao_social[:30]:30} | Total: {total_clientes:3} | Ativos: {contratos_ativos:3} | Inativos: {contratos_inativos:3}")
    
    except Exception as e:
        print(f"❌ Erro na análise de carteira: {e}")
    
    print("\n" + "=" * 60)
    print("👥 ANÁLISE DE CLIENTES (Dados Contábeis)")
    print("=" * 60)
    
    # Analisar clientes com dados contábeis
    try:
        contratos_ativos = Contrato.objects.filter(ativo=True).select_related('pessoa_juridica', 'contabilidade')
        
        print(f"📋 Clientes com contratos ativos: {contratos_ativos.count()}")
        
        # Mostrar alguns exemplos
        for contrato in contratos_ativos[:10]:
            pessoa_juridica = contrato.pessoa_juridica
            lancamentos_count = LancamentoContabil.objects.filter(contrato=contrato).count()
            notas_count = NotaFiscal.objects.filter(contrato=contrato).count()
            
            print(f"🏢 {pessoa_juridica.razao_social[:25]:25} | Lançamentos: {lancamentos_count:3} | Notas: {notas_count:3}")
    
    except Exception as e:
        print(f"❌ Erro na análise de clientes: {e}")
    
    print("\n" + "=" * 60)
    print("👤 ANÁLISE DE USUÁRIOS (Atividades)")
    print("=" * 60)
    
    # Analisar usuários
    try:
        usuarios = Usuario.objects.select_related('contabilidade').all()
        
        for usuario in usuarios:
            contabilidade_nome = usuario.contabilidade.razao_social if usuario.contabilidade else "Sem contabilidade"
            etl = "✅" if usuario.pode_executar_etl else "❌"
            admin = "✅" if usuario.pode_administrar_usuarios else "❌"
            
            print(f"👤 {usuario.username:15} | {usuario.tipo_usuario:12} | {contabilidade_nome[:20]:20} | ETL: {etl} | Admin: {admin}")
    
    except Exception as e:
        print(f"❌ Erro na análise de usuários: {e}")
    
    print("\n" + "=" * 60)
    print("🔗 ANÁLISE DE RELACIONAMENTOS")
    print("=" * 60)
    
    # Analisar relacionamentos usando Django ORM
    try:
        print("📊 Relacionamentos principais:")
        print("  • Contabilidade → Usuários")
        print("  • Contabilidade → Contratos")
        print("  • Pessoa Jurídica → Contratos")
        print("  • Contrato → Lançamentos Contábeis")
        print("  • Contrato → Notas Fiscais")
        print("  • Contrato → Funcionários")
        
        # Verificar integridade dos relacionamentos
        contratos_sem_contabilidade = Contrato.objects.filter(contabilidade__isnull=True).count()
        contratos_sem_pessoa = Contrato.objects.filter(pessoa_juridica__isnull=True).count()
        
        print(f"\n⚠️  Verificações de integridade:")
        print(f"  • Contratos sem contabilidade: {contratos_sem_contabilidade}")
        print(f"  • Contratos sem pessoa jurídica: {contratos_sem_pessoa}")
    
    except Exception as e:
        print(f"❌ Erro na análise de relacionamentos: {e}")

if __name__ == "__main__":
    analisar_tabelas()
