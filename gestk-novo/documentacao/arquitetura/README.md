# Arquitetura do Sistema GESTK

## 🏗️ Visão Geral da Arquitetura

O GESTK foi projetado seguindo os princípios de **Clean Architecture** e **Domain-Driven Design (DDD)**, com foco em:

- **Multi-tenancy estrito** para isolamento total de dados
- **Escalabilidade horizontal** para crescimento futuro
- **Manutenibilidade** através de código limpo e bem estruturado
- **Segurança** como prioridade máxima

## 🎯 Princípios Arquiteturais

### 1. Multi-Tenancy Estrito
- **Isolamento Total**: Cada contabilidade é um tenant completamente isolado
- **Segurança por Design**: Impossível acesso cruzado entre tenants
- **Escalabilidade**: Suporte a centenas de contabilidades

### 2. Separação de Responsabilidades
- **Core**: Funcionalidades centrais (Contabilidades, Usuários)
- **Módulos de Domínio**: Pessoas, Fiscal, Contabil, Funcionários
- **Infraestrutura**: ETL, Importação, APIs

### 3. Inversão de Dependências
- **Abstrações**: Interfaces bem definidas
- **Injeção de Dependências**: Baixo acoplamento
- **Testabilidade**: Fácil mock e teste unitário

## 📊 Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA DE APRESENTAÇÃO                    │
├─────────────────────────────────────────────────────────────┤
│  Frontend (React)  │  API REST (Django)  │  Admin Django   │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA DE APLICAÇÃO                       │
├─────────────────────────────────────────────────────────────┤
│  Services  │  ETLs  │  Commands  │  Serializers  │  Views   │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA DE DOMÍNIO                         │
├─────────────────────────────────────────────────────────────┤
│  Models  │  Business Logic  │  Validators  │  Rules         │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                  CAMADA DE INFRAESTRUTURA                    │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Sybase  │  Redis  │  Celery  │  Logs       │
└─────────────────────────────────────────────────────────────┘
```

## 🗄️ Estrutura de Dados

### Modelo de Multi-Tenancy

```python
# Tenant Central
class Contabilidade(models.Model):
    id = models.UUIDField(primary_key=True)
    cnpj = models.CharField(unique=True)
    razao_social = models.TextField()
    # ... outros campos

# Todos os modelos principais herdam o isolamento
class PessoaJuridica(models.Model):
    # Sem FK direta para Contabilidade
    # Isolamento via Contrato
    
class NotaFiscal(models.Model):
    contabilidade = models.ForeignKey('core.Contabilidade')
    # Isolamento direto
```

### Relacionamentos

1. **Diretos**: FK direta para Contabilidade
2. **Indiretos**: Via Contrato (GenericForeignKey)
3. **Históricos**: Mapeamento temporal de contratos

## 🔄 Sistema ETL

### Arquitetura do ETL

```
Sybase (Legado)
       │
       ▼
┌─────────────┐
│ BaseETLCommand │
└─────────────┘
       │
       ▼
┌─────────────┐
│ Transformação │
└─────────────┘
       │
       ▼
┌─────────────┐
│ PostgreSQL  │
└─────────────┘
```

### Características

- **Idempotência**: Execução múltipla sem duplicação
- **Transacional**: Rollback automático em caso de erro
- **Multitenant**: Resolução correta de contabilidades
- **Eficiente**: Processamento em lotes

## 🔒 Segurança

### Isolamento de Dados

1. **Nível de Banco**: Constraints de FK
2. **Nível de Aplicação**: Validação em views
3. **Nível de API**: Filtros automáticos por tenant

### Auditoria

- **django-simple-history**: Histórico automático
- **Logs Estruturados**: Rastreamento completo
- **Compliance**: Atendimento a requisitos legais

## 📈 Escalabilidade

### Estratégias Implementadas

1. **UUIDs**: Evita conflitos em sharding
2. **Índices Estratégicos**: Performance otimizada
3. **Cache**: Redis para dados frequentes
4. **Processamento Assíncrono**: Celery para ETLs

### Próximos Passos

1. **Sharding Horizontal**: Por contabilidade
2. **CDN**: Para arquivos estáticos
3. **Load Balancer**: Para múltiplas instâncias

## 🧪 Testabilidade

### Estratégias de Teste

1. **Testes Unitários**: Modelos e lógica de negócio
2. **Testes de Integração**: ETLs e APIs
3. **Testes de Isolamento**: Multi-tenancy
4. **Testes de Performance**: Carga e stress

## 📚 Padrões Utilizados

### Design Patterns

- **Repository Pattern**: Para acesso a dados
- **Factory Pattern**: Para criação de objetos
- **Strategy Pattern**: Para diferentes tipos de ETL
- **Observer Pattern**: Para auditoria

### Django Patterns

- **Generic Views**: Para APIs REST
- **Model Forms**: Para validação
- **Custom Managers**: Para queries complexas
- **Signals**: Para eventos de modelo

## 🔧 Configuração

### Ambientes

1. **Development**: Configuração local
2. **Staging**: Ambiente de testes
3. **Production**: Ambiente de produção

### Variáveis de Ambiente

```bash
# Banco de Dados
DB_NAME=gestk
DB_USER=postgres
DB_PASSWORD=senha
DB_HOST=localhost
DB_PORT=5432

# Sybase (ETL)
ODBC_DRIVER=SQL Anywhere 17
ODBC_SERVER=dominio3
ODBC_DATABASE=contabil
ODBC_USER=EXTERNO
ODBC_PASSWORD=externo

# Segurança
SECRET_KEY=chave-secreta
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
```

## 📖 Referências

- [Django Best Practices](https://djangoproject.com/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Multi-Tenancy Patterns](https://docs.microsoft.com/en-us/azure/sql-database/saas-tenancy-app-design-patterns)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
