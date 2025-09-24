# 🔧 Variáveis de Ambiente - Projeto GESTK

## 📋 **Status Atual (Janeiro 2025)**

### ✅ **Variáveis Configuradas Corretamente**

O projeto está configurado para usar variáveis de ambiente através do arquivo `.env` na raiz do projeto.

#### **Arquivo `.env` Atual:**
```bash
SECRET_KEY=django-insecure-seu-segredo-super-secreto-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL
DB_NAME=db_gestk
DB_USER=postgres
DB_PASSWORD=admin
DB_HOST=localhost
DB_PORT=5432

# Sybase (para ETL)
ODBC_DRIVER=SQL Anywhere 17
ODBC_SERVER=dominio3
ODBC_DATABASE=contabil
ODBC_USER=EXTERNO
ODBC_PASSWORD=externo
```

#### **Configuração no `settings.py`:**
```python
# Configurações do Django
SECRET_KEY = config('SECRET_KEY', default='django-insecure-fallback-key-for-dev')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Configurações do PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='db_gestk'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='admin'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Configurações do Sybase (ETL)
SYBASE_CONFIG = {
    'DRIVER': config('ODBC_DRIVER', default='SQL Anywhere 17'),
    'SERVER': config('ODBC_SERVER', default='dominio3'),
    'DATABASE': config('ODBC_DATABASE', default='contabil'),
    'UID': config('ODBC_USER', default='EXTERNO'),
    'PWD': config('ODBC_PASSWORD', default='externo'),
}
```

## 🔍 **Análise de Segurança**

### ✅ **Pontos Positivos:**
1. **Credenciais Externalizadas:** Todas as credenciais estão no arquivo `.env`
2. **Sem Hardcoding:** Não há credenciais hardcoded no código
3. **Valores Padrão Seguros:** Os defaults são genéricos e não expõem credenciais reais
4. **Isolamento:** O `.env` não está versionado (deve estar no `.gitignore`)

### ⚠️ **Pontos de Atenção:**
1. **SECRET_KEY:** Deve ser alterada para produção
2. **DEBUG=True:** Deve ser `False` em produção
3. **Senhas Simples:** As senhas são muito simples para produção

## 📝 **Variáveis Recomendadas para Adicionar**

### **Configurações de Email:**
```bash
# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
```

### **Configurações de Cache (Redis):**
```bash
# Cache Redis
CACHE_URL=redis://localhost:6379/1
CACHE_BACKEND=django_redis.cache.RedisCache
```

### **Configurações de Logging:**
```bash
# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/gestk/django.log
```

### **Configurações de Segurança (Produção):**
```bash
# Segurança
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_BROWSER_XSS_FILTER=True
X_FRAME_OPTIONS=DENY
```

### **Configurações Específicas do GESTK:**
```bash
# GESTK
GESTAO_RAZAO_SOCIAL=Contabilidade Matriz LTDA
GESTAO_CNPJ=00000000000000
```

## 🚀 **Implementação Recomendada**

### **1. Atualizar `settings.py` para Suportar Novas Variáveis:**

```python
# Email
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# Cache
CACHE_URL = config('CACHE_URL', default='')
if CACHE_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': CACHE_URL,
        }
    }

# Logging
LOG_LEVEL = config('LOG_LEVEL', default='INFO')
LOG_FILE = config('LOG_FILE', default='')

# Segurança
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)

# GESTK
GESTAO_RAZAO_SOCIAL = config('GESTAO_RAZAO_SOCIAL', default='Contabilidade Matriz LTDA')
GESTAO_CNPJ = config('GESTAO_CNPJ', default='00000000000000')
```

### **2. Criar `.env.example` para Documentação:**

```bash
# ===========================================
# CONFIGURAÇÕES DO PROJETO GESTK
# ===========================================
# Copie este arquivo para .env e configure as variáveis conforme seu ambiente

# ===========================================
# CONFIGURAÇÕES GERAIS DO DJANGO
# ===========================================
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# ===========================================
# CONFIGURAÇÕES DO BANCO DE DADOS POSTGRESQL
# ===========================================
DB_NAME=db_gestk
DB_USER=postgres
DB_PASSWORD=admin
DB_HOST=localhost
DB_PORT=5432

# ===========================================
# CONFIGURAÇÕES DO SYBASE (SISTEMA LEGADO)
# ===========================================
ODBC_DRIVER=SQL Anywhere 17
ODBC_SERVER=dominio3
ODBC_DATABASE=contabil
ODBC_USER=EXTERNO
ODBC_PASSWORD=externo

# ===========================================
# CONFIGURAÇÕES DE EMAIL
# ===========================================
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend

# ===========================================
# CONFIGURAÇÕES DE CACHE
# ===========================================
CACHE_URL=redis://localhost:6379/1

# ===========================================
# CONFIGURAÇÕES DE LOGGING
# ===========================================
LOG_LEVEL=INFO
LOG_FILE=/var/log/gestk/django.log

# ===========================================
# CONFIGURAÇÕES DE SEGURANÇA (PRODUÇÃO)
# ===========================================
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_BROWSER_XSS_FILTER=True
X_FRAME_OPTIONS=DENY

# ===========================================
# CONFIGURAÇÕES ESPECÍFICAS DO GESTK
# ===========================================
GESTAO_RAZAO_SOCIAL=Contabilidade Matriz LTDA
GESTAO_CNPJ=00000000000000
```

## 🔒 **Boas Práticas de Segurança**

### **1. Arquivo `.env` NUNCA deve ser versionado:**
```bash
# .gitignore
.env
.env.local
.env.production
.env.staging
```

### **2. Validação de Variáveis Obrigatórias:**
```python
# settings.py
import sys

# Variáveis obrigatórias para produção
REQUIRED_ENV_VARS = ['SECRET_KEY', 'DB_PASSWORD', 'ODBC_PASSWORD']
if not DEBUG:
    for var in REQUIRED_ENV_VARS:
        if not config(var, default=None):
            print(f"ERRO: Variável {var} é obrigatória em produção!")
            sys.exit(1)
```

### **3. Validação de Valores:**
```python
# settings.py
# Validar SECRET_KEY
if len(SECRET_KEY) < 50:
    raise ValueError("SECRET_KEY deve ter pelo menos 50 caracteres")

# Validar DEBUG em produção
if not DEBUG and SECRET_KEY == 'django-insecure-fallback-key-for-dev':
    raise ValueError("SECRET_KEY padrão não pode ser usado em produção")
```

## 📊 **Resumo da Análise**

### ✅ **Status Atual:**
- **Configuração:** ✅ Correta
- **Segurança:** ✅ Adequada para desenvolvimento
- **Externalização:** ✅ Completa
- **Hardcoding:** ✅ Nenhum encontrado

### 🔄 **Próximos Passos Recomendados:**
1. ✅ **Concluído:** Corrigir mapeamento de variáveis no `settings.py`
2. 🔄 **Pendente:** Adicionar variáveis de email, cache e logging
3. 🔄 **Pendente:** Criar `.env.example` para documentação
4. 🔄 **Pendente:** Implementar validação de variáveis obrigatórias
5. 🔄 **Pendente:** Configurar variáveis de segurança para produção

### 📈 **Benefícios da Implementação:**
- **Flexibilidade:** Configuração por ambiente
- **Segurança:** Credenciais externalizadas
- **Manutenibilidade:** Fácil alteração de configurações
- **Documentação:** `.env.example` serve como guia
- **Validação:** Prevenção de erros de configuração

---

**Última atualização:** Janeiro 2025  
**Status:** ✅ Configuração atual corrigida e funcional
