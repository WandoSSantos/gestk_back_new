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
    
    with connection.cursor() as cursor:
        # Listar todas as tabelas
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tabelas = cursor.fetchall()
        
        print(f"\n📊 TOTAL DE TABELAS: {len(tabelas)}")
        print("\n📋 LISTA DE TABELAS:")
        for i, (tabela,) in enumerate(tabelas, 1):
            print(f"{i:2d}. {tabela}")
    
    print("\n" + "=" * 60)
    print("🏗️ ANÁLISE DAS TABELAS PRINCIPAIS")
    print("=" * 60)
    
    # Analisar tabelas principais
    tabelas_principais = [
        ('core_contabilidades', 'Contabilidades'),
        ('core_usuarios', 'Usuários'),
        ('pessoas_pessoajuridica', 'Pessoas Jurídicas'),
        ('pessoas_pessoafisica', 'Pessoas Físicas'),
        ('pessoas_contrato', 'Contratos'),
        ('contabil_lancamento_contabil', 'Lançamentos Contábeis'),
        ('fiscal_notafiscal', 'Notas Fiscais'),
        ('funcionarios_funcionario', 'Funcionários'),
    ]
    
    for tabela, nome in tabelas_principais:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {tabela};")
            count = cursor.fetchone()[0]
            print(f"✅ {nome:25} | {tabela:30} | {count:6,} registros")
        except Exception as e:
            print(f"❌ {nome:25} | {tabela:30} | ERRO: {str(e)[:50]}")
    
    print("\n" + "=" * 60)
    print("🔗 ANÁLISE DE RELACIONAMENTOS")
    print("=" * 60)
    
    # Analisar relacionamentos
    try:
        cursor.execute("""
            SELECT 
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name 
            FROM 
                information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_schema='public'
            ORDER BY tc.table_name, kcu.column_name;
        """)
        
        relacionamentos = cursor.fetchall()
        
        print(f"\n📊 TOTAL DE RELACIONAMENTOS: {len(relacionamentos)}")
        print("\n🔗 RELACIONAMENTOS PRINCIPAIS:")
        for tabela, coluna, tabela_fk, coluna_fk in relacionamentos:
            if any(t in tabela for t in ['core_', 'pessoas_', 'contabil_', 'fiscal_', 'funcionarios_']):
                print(f"  {tabela:25} → {tabela_fk:25} ({coluna} → {coluna_fk})")
    
    except Exception as e:
        print(f"❌ Erro ao analisar relacionamentos: {e}")
    
    print("\n" + "=" * 60)
    print("📈 ANÁLISE DE DADOS PARA ENDPOINTS")
    print("=" * 60)
    
    # Analisar dados específicos para endpoints
    analisar_dados_carteira(cursor)
    analisar_dados_clientes(cursor)
    analisar_dados_usuarios(cursor)

def analisar_dados_carteira(cursor):
    """Analisar dados para endpoints de carteira"""
    
    print("\n🏢 ANÁLISE DE CARTEIRA (Clientes por Contabilidade):")
    
    try:
        # Clientes por contabilidade
        cursor.execute("""
            SELECT 
                c.razao_social as contabilidade,
                COUNT(DISTINCT pj.id) as total_clientes,
                COUNT(DISTINCT CASE WHEN ct.ativo = true THEN pj.id END) as clientes_ativos,
                COUNT(DISTINCT CASE WHEN ct.ativo = false THEN pj.id END) as clientes_inativos
            FROM core_contabilidades c
            LEFT JOIN pessoas_contrato ct ON ct.contabilidade_id = c.id
            LEFT JOIN pessoas_pessoajuridica pj ON pj.id = ct.pessoa_juridica_id
            GROUP BY c.id, c.razao_social
            ORDER BY total_clientes DESC;
        """)
        
        resultados = cursor.fetchall()
        
        for contabilidade, total, ativos, inativos in resultados:
            print(f"  📊 {contabilidade[:30]:30} | Total: {total:3} | Ativos: {ativos:3} | Inativos: {inativos:3}")
    
    except Exception as e:
        print(f"❌ Erro na análise de carteira: {e}")

def analisar_dados_clientes(cursor):
    """Analisar dados para endpoints de clientes"""
    
    print("\n👥 ANÁLISE DE CLIENTES (Dados Contábeis):")
    
    try:
        # Clientes com dados contábeis
        cursor.execute("""
            SELECT 
                pj.razao_social,
                pj.cnpj,
                COUNT(DISTINCT l.id) as total_lancamentos,
                COUNT(DISTINCT nf.id) as total_notas_fiscais,
                MAX(l.data_lancamento) as ultimo_lancamento
            FROM pessoas_pessoajuridica pj
            LEFT JOIN pessoas_contrato ct ON ct.pessoa_juridica_id = pj.id
            LEFT JOIN contabil_lancamento_contabil l ON l.contrato_id = ct.id
            LEFT JOIN fiscal_notafiscal nf ON nf.contrato_id = ct.id
            WHERE ct.ativo = true
            GROUP BY pj.id, pj.razao_social, pj.cnpj
            HAVING COUNT(DISTINCT l.id) > 0 OR COUNT(DISTINCT nf.id) > 0
            ORDER BY total_lancamentos DESC
            LIMIT 10;
        """)
        
        resultados = cursor.fetchall()
        
        for razao, cnpj, lancamentos, notas, ultimo in resultados:
            print(f"  🏢 {razao[:25]:25} | Lançamentos: {lancamentos:3} | Notas: {notas:3} | Último: {ultimo or 'N/A'}")
    
    except Exception as e:
        print(f"❌ Erro na análise de clientes: {e}")

def analisar_dados_usuarios(cursor):
    """Analisar dados para endpoints de usuários"""
    
    print("\n👤 ANÁLISE DE USUÁRIOS (Atividades):")
    
    try:
        # Usuários e suas atividades
        cursor.execute("""
            SELECT 
                u.username,
                u.tipo_usuario,
                c.razao_social as contabilidade,
                u.data_ultima_atividade,
                u.pode_executar_etl,
                u.pode_administrar_usuarios
            FROM core_usuarios u
            LEFT JOIN core_contabilidades c ON c.id = u.contabilidade_id
            ORDER BY u.data_ultima_atividade DESC NULLS LAST;
        """)
        
        resultados = cursor.fetchall()
        
        for username, tipo, contabilidade, ultima_atividade, pode_etl, pode_admin in resultados:
            etl = "✅" if pode_etl else "❌"
            admin = "✅" if pode_admin else "❌"
            print(f"  👤 {username:15} | {tipo:12} | {contabilidade[:20]:20} | ETL: {etl} | Admin: {admin}")
    
    except Exception as e:
        print(f"❌ Erro na análise de usuários: {e}")

if __name__ == "__main__":
    analisar_tabelas()
