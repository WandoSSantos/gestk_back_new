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
from django.contrib.contenttypes.models import ContentType
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
        contratos_ativos = Contrato.objects.filter(ativo=True).select_related('contabilidade')
        
        print(f"📋 Clientes com contratos ativos: {contratos_ativos.count()}")
        
        # Contar por tipo de cliente
        pessoa_juridica_ct = ContentType.objects.get_for_model(PessoaJuridica)
        pessoa_fisica_ct = ContentType.objects.get_for_model(PessoaFisica)
        
        contratos_pj = contratos_ativos.filter(content_type=pessoa_juridica_ct).count()
        contratos_pf = contratos_ativos.filter(content_type=pessoa_fisica_ct).count()
        
        print(f"  • Pessoas Jurídicas: {contratos_pj}")
        print(f"  • Pessoas Físicas: {contratos_pf}")
        
        # Mostrar alguns exemplos de contratos com PJ
        contratos_pj_exemplos = contratos_ativos.filter(content_type=pessoa_juridica_ct)[:10]
        
        print(f"\n📋 Exemplos de clientes PJ:")
        for contrato in contratos_pj_exemplos:
            if contrato.cliente:
                lancamentos_count = LancamentoContabil.objects.filter(contrato=contrato).count()
                notas_count = NotaFiscal.objects.filter(contrato=contrato).count()
                
                print(f"🏢 {contrato.cliente.razao_social[:25]:25} | Lançamentos: {lancamentos_count:3} | Notas: {notas_count:3}")
    
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
    print("📊 MAPEAMENTO PARA ENDPOINTS")
    print("=" * 60)
    
    print("\n🎯 ENDPOINTS DE CARTEIRA:")
    print("  • /api/gestao/carteira/clientes/ - Lista clientes por status")
    print("  • /api/gestao/carteira/categorias/ - Agregações por regime fiscal")
    print("  • /api/gestao/carteira/evolucao/ - Evolução mensal")
    
    print("\n🎯 ENDPOINTS DE CLIENTES:")
    print("  • /api/gestao/clientes/lista/ - Tabela por competência")
    print("  • /api/gestao/clientes/detalhes/ - Visualização detalhada")
    print("  • /api/gestao/clientes/socios/ - Sócio majoritário")
    
    print("\n🎯 ENDPOINTS DE USUÁRIOS:")
    print("  • /api/gestao/usuarios/lista/ - Lista de usuários")
    print("  • /api/gestao/usuarios/atividades/ - Atividades por usuário")
    print("  • /api/gestao/usuarios/produtividade/ - Relatórios de produtividade")
    
    print("\n" + "=" * 60)
    print("🔗 ESTRUTURA DE DADOS IDENTIFICADA")
    print("=" * 60)
    
    print("\n📋 TABELAS PRINCIPAIS:")
    print("  • core_contabilidades - Contabilidades")
    print("  • core_usuarios - Usuários do sistema")
    print("  • pessoas_juridicas - Pessoas jurídicas (clientes)")
    print("  • pessoas_fisicas - Pessoas físicas (clientes)")
    print("  • pessoas_contratos - Contratos (Generic FK)")
    print("  • contabil_lancamentos - Lançamentos contábeis")
    print("  • fiscal_notas_fiscais - Notas fiscais")
    print("  • funcionarios_funcionario - Funcionários")
    
    print("\n🔗 RELACIONAMENTOS:")
    print("  • Contabilidade → Contratos → Cliente (PJ/PF)")
    print("  • Contrato → Lançamentos Contábeis")
    print("  • Contrato → Notas Fiscais")
    print("  • Contrato → Funcionários")
    print("  • Contabilidade → Usuários")

if __name__ == "__main__":
    analisar_tabelas()
