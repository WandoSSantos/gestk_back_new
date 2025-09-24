#!/usr/bin/env python3
"""
Script para testar os endpoints de gestão
"""

import requests
import json
import time

# Configurações
BASE_URL = "http://127.0.0.1:8000"
LOGIN_URL = f"{BASE_URL}/api/auth/login/"
GESTAO_URL = f"{BASE_URL}/api/gestao/"

def fazer_login():
    """Fazer login e obter token"""
    print("🔐 Fazendo login...")
    
    login_data = {
        "username": "wando",
        "password": "H33tsupa!"
    }
    
    try:
        response = requests.post(LOGIN_URL, json=login_data)
        response.raise_for_status()
        
        data = response.json()
        token = data['access']
        print(f"✅ Login realizado com sucesso!")
        print(f"   Token: {token[:50]}...")
        
        return token
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro no login: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status: {e.response.status_code}")
            print(f"   Response: {e.response.text}")
        return None

def testar_endpoint(token, endpoint, nome):
    """Testar um endpoint específico"""
    print(f"\n🧪 Testando {nome}...")
    print(f"   URL: {GESTAO_URL}{endpoint}")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(f"{GESTAO_URL}{endpoint}", headers=headers)
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Sucesso!")
            print(f"   📊 Dados retornados: {len(data) if isinstance(data, list) else 'objeto'}")
            
            # Mostrar estrutura dos dados
            if isinstance(data, list) and len(data) > 0:
                print(f"   📋 Primeiro item: {list(data[0].keys())}")
            elif isinstance(data, dict):
                print(f"   📋 Chaves: {list(data.keys())}")
            
            return True
        else:
            print(f"   ❌ Erro: {response.status_code}")
            print(f"   📝 Response: {response.text}")
            return False
    
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erro na requisição: {e}")
        return False

def main():
    """Função principal"""
    print("🚀 TESTE DOS ENDPOINTS DE GESTÃO")
    print("=" * 50)
    
    # Fazer login
    token = fazer_login()
    if not token:
        print("❌ Não foi possível fazer login. Abortando testes.")
        return
    
    # Lista de endpoints para testar
    endpoints = [
        ("carteira/clientes/", "Carteira - Clientes"),
        ("carteira/categorias/", "Carteira - Categorias"),
        ("carteira/evolucao/", "Carteira - Evolução"),
        ("clientes/lista/", "Clientes - Lista"),
        ("clientes/detalhes/?cliente_id=123", "Clientes - Detalhes"),
        ("clientes/socios/", "Clientes - Sócios"),
        ("usuarios/lista/", "Usuários - Lista"),
        ("usuarios/atividades/", "Usuários - Atividades"),
        ("usuarios/produtividade/", "Usuários - Produtividade"),
    ]
    
    # Testar cada endpoint
    sucessos = 0
    total = len(endpoints)
    
    for endpoint, nome in endpoints:
        if testar_endpoint(token, endpoint, nome):
            sucessos += 1
        time.sleep(0.5)  # Pequena pausa entre testes
    
    # Resumo
    print(f"\n📊 RESUMO DOS TESTES")
    print("=" * 50)
    print(f"✅ Sucessos: {sucessos}/{total}")
    print(f"❌ Falhas: {total - sucessos}/{total}")
    print(f"📈 Taxa de sucesso: {(sucessos/total)*100:.1f}%")
    
    if sucessos == total:
        print("\n🎉 Todos os endpoints estão funcionando!")
    else:
        print(f"\n⚠️  {total - sucessos} endpoint(s) com problemas")

if __name__ == "__main__":
    main()
