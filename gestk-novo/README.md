# GESTK - Sistema de Gestão Contábil SaaS

[![Django](https://img.shields.io/badge/Django-4.2.15-green.svg)](https://djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue.svg)](https://postgresql.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-yellow.svg)](https://python.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

## 🎯 Visão Geral

O **GESTK** é um sistema de gestão contábil moderno, desenvolvido no modelo **SaaS (Software as a Service)**, projetado para atender múltiplos escritórios de contabilidade de forma segura, escalável e isolada. 

O sistema migra dados de um legado **Sybase SQL Anywhere** para uma arquitetura moderna em **PostgreSQL**, garantindo integridade, segurança e total isolamento dos dados de cada cliente (tenant).

---

## 2. Fundamentos e Arquitetura

A arquitetura do novo GESTK se baseia em quatro pilares fundamentais:

### a. Multi-Tenancy Estrito

Este é o princípio mais importante do sistema. Cada escritório de contabilidade é um "tenant" isolado no banco de dados.

-   **Modelo Central:** `core.Contabilidade` é a tabela que representa cada tenant.
-   **Isolamento de Dados:** Praticamente todos os outros modelos de dados no sistema (como `PessoaJuridica`, `NotaFiscal`, `LancamentoContabil`, etc.) possuem uma chave estrangeira (`ForeignKey`) obrigatória para `Contabilidade`. Isso garante, no nível do banco de dados, que os dados de um escritório nunca possam ser acessados por outro.

### b. Normalização e Estrutura do Banco de Dados

Seguimos uma abordagem de banco de dados relacional clássica para garantir consistência e evitar redundância.

-   **Chaves Primárias UUID:** Todas as tabelas usam `UUID` como chave primária (`id = models.UUIDField`). Isso previne conflitos de IDs que poderiam ocorrer durante a importação de dados de múltiplas fontes e facilita a escalabilidade horizontal do banco de dados no futuro.
-   **Relacionamentos Explícitos:** Usamos chaves estrangeiras (`ForeignKey`) diretas para criar relacionamentos claros e explícitos entre as tabelas. Um exemplo disso foi a refatoração que removeu o modelo genérico `ParceiroNegocio` em favor de relacionamentos diretos na tabela `NotaFiscal`, tornando a estrutura mais simples, rápida e segura.
-   **Consistência:** A normalização garante que uma informação (como o cadastro de uma pessoa jurídica) exista em um único lugar, e todas as outras tabelas que precisam dessa informação apenas a referenciam.

### c. Processo de ETL Robusto e Idempotente

A migração de dados do Sybase é um processo crítico e foi desenhada para ser segura e confiável.

-   **Idempotência:** Todos os scripts de ETL são "idempotentes". Isso significa que eles podem ser executados múltiplas vezes sem criar dados duplicados. Eles utilizam a lógica `update_or_create` do Django, que verifica se um registro já existe (com base em uma chave única, como CNPJ ou Chave da NFe) antes de decidir se deve criá-lo ou apenas atualizá-lo.
-   **Transações Atômicas:** Cada lote de dados importado é envolvido em uma transação de banco de dados (`transaction.atomic`). Se ocorrer qualquer erro durante o processamento de um lote, todas as alterações daquele lote são desfeitas (rollback), garantindo que o banco de dados nunca fique em um estado inconsistente.

### d. Auditoria Completa

Para rastreabilidade e segurança, todas as alterações importantes nos dados são registradas.

-   **Histórico de Alterações:** Utilizamos a biblioteca `django-simple-history`, que cria automaticamente uma tabela de histórico para cada modelo monitorado. Qualquer criação, alteração ou exclusão de um registro gera uma nova linha nessa tabela de histórico, guardando quem fez a alteração, quando e quais eram os valores antigos.

---

## 📋 Status Atual do Projeto (Janeiro 2025)

### ✅ **FASE 1: MIGRAÇÃO DE DADOS (ETL) - CONCLUÍDA**

#### **ETLs Implementados e Funcionais:**

| Categoria | ETL | Descrição | Status | Dependências |
|-----------|-----|-----------|--------|--------------|
| **Base** | ETL 00 | Mapeamento Completo de Empresas | ✅ | Nenhuma |
| **Base** | ETL 01 | Contabilidades (Tenants) | ✅ | Nenhuma |
| **Base** | ETL 02 | CNAEs | ✅ | Nenhuma |
| **Base** | ETL 04 | Contratos, Pessoas Físicas e Jurídicas | ✅ | ETL 01 |
| **Base** | ETL 21 | Quadro Societário | ✅ | ETL 04 |
| **Contábil** | ETL 05 | Plano de Contas | ✅ | ETL 01 |
| **Contábil** | ETL 06 | Lançamentos Contábeis | ✅ | ETL 05 |
| **Fiscal** | ETL 07 | Notas Fiscais (NFe entrada/saída/serviços) | ✅ | ETL 04 |
| **Fiscal** | ETL 17 | Cupons Fiscais Eletrônicos | ✅ | ETL 04 |
| **RH** | ETL 08 | Cargos | ✅ | ETL 04 |
| **RH** | ETL 09 | Departamentos | ✅ | ETL 04 |
| **RH** | ETL 10 | Centros de Custo | ✅ | ETL 04 |
| **RH** | ETL 11 | Funcionários, Vínculos e Rubricas | ✅ | ETLs 08-10 |
| **RH** | ETL 12 | Históricos de Salário e Cargo | ✅ | ETL 11 |
| **RH** | ETL 13 | Períodos Aquisitivos de Férias | ✅ | ETL 11 |
| **RH** | ETL 14 | Gozo de Férias | ✅ | ETL 13 |
| **RH** | ETL 15 | Afastamentos | ✅ | ETL 11 |
| **RH** | ETL 16 | Rescisões e Rubricas de Rescisão | ✅ | ETL 11 |
| **Admin** | ETL 18 | Usuários e Configurações | ✅ | ETL 04 |
| **Admin** | ETL 19 | Logs de Acesso e Atividades | ✅ | ETL 18 |

#### **ETLs Pendentes:**
- **ETL 20** - Lançamentos por Usuário (Em desenvolvimento)

### 🏗️ **FASE 2: ARQUITETURA E ESTRUTURA - CONCLUÍDA**

#### **Reorganização do Projeto:**
```
gestk-novo/
├── apps/                          # Aplicações Django
│   ├── core/                     # Módulo central (Contabilidades, Usuários)
│   ├── pessoas/                  # Pessoas e Contratos
│   ├── fiscal/                   # Documentos Fiscais
│   ├── funcionarios/             # Recursos Humanos
│   ├── contabil/                 # Contabilidade
│   ├── administracao/            # Administração e Logs
│   ├── cadastros_gerais/         # Cadastros Gerais
│   ├── contabilidade_fiscal/     # Contabilidade Fiscal
│   ├── importacao/               # Sistema ETL
│   │   └── management/commands/  # Comandos ETL
│   └── api/                      # API REST (NOVO)
│       ├── auth/                 # Autenticação
│       ├── gestao/               # Módulo Gestão
│       ├── dashboards/           # Módulo Dashboards
│       ├── export/               # Módulo Exportação
│       └── shared/               # Código compartilhado da API
├── shared/                       # Código compartilhado
│   ├── mixins/                   # Mixins reutilizáveis
│   ├── utils/                    # Utilitários
│   └── validators/               # Validadores
├── tests/                        # Testes automatizados
├── docs/                         # Documentação técnica
├── gestk/                        # Configurações Django
└── requirements.txt              # Dependências
```

### 🚀 **FASE 3: DESENVOLVIMENTO DA API - EM ANDAMENTO**

#### **Status da API REST (Janeiro 2025):**

| Módulo | Componente | Status | Descrição |
|--------|------------|--------|-----------|
| **Base** | Estrutura Inicial | ✅ | Estrutura de diretórios e arquivos |
| **Base** | Middleware Multitenant | ✅ | Regra de Ouro implementada |
| **Base** | Filtros Automáticos | ✅ | Isolamento por contabilidade |
| **Base** | ViewSets Base | ✅ | Classes base com multitenancy |
| **Base** | Serializers Base | ✅ | Serializers com validação |
| **Base** | Permissões | ✅ | Permissões customizadas |
| **Base** | URLs | ✅ | Estrutura de rotas configurada |
| **Auth** | Autenticação JWT | 🔄 | Em desenvolvimento |
| **Gestão** | Análise de Carteira | ⏳ | Pendente |
| **Gestão** | Análise de Clientes | ⏳ | Pendente |
| **Gestão** | Análise de Usuários | ⏳ | Pendente |
| **Dashboards** | Dashboard Fiscal | ⏳ | Pendente |
| **Dashboards** | Dashboard Contábil | ⏳ | Pendente |
| **Dashboards** | Dashboard RH | ⏳ | Pendente |
| **Export** | Relatórios | ⏳ | Pendente |

#### **Funcionalidades Implementadas:**
- ✅ **Multitenancy Automático:** Todos os ViewSets aplicam filtros por contabilidade
- ✅ **Regra de Ouro:** Middleware aplica regra automaticamente
- ✅ **Cache Inteligente:** Mapa histórico em cache por 5 minutos
- ✅ **Validação de Acesso:** Permissões rigorosas por contabilidade
- ✅ **Estrutura Modular:** Fácil expansão e manutenção
- ✅ **Padrões Consistentes:** Serializers e ViewSets padronizados

#### **Próximas Implementações:**
1. **API REST Completa** - Endpoints para todas as entidades
2. **Sistema de Autenticação** - JWT + OAuth2
3. **Documentação da API** - Swagger/OpenAPI
4. **Testes Automatizados** - Cobertura completa
5. **Monitoramento** - Logs, métricas e alertas

---

## 🚀 Como Executar o Projeto

### **Pré-requisitos:**
- Python 3.11+
- PostgreSQL 13+
- Git
- IDE (VS Code, PyCharm, etc.)

### **Configuração Inicial:**

```bash
# 1. Clone o repositório
git clone <repository-url>
cd gestk-novo

# 2. Configure ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# 3. Instale dependências
pip install -r requirements.txt

# 4. Configure variáveis de ambiente
cp .env.example .env
# Edite o arquivo .env com suas configurações

# 5. Execute migrações
python manage.py migrate

# 6. Crie superuser
python manage.py createsuperuser

# 7. Execute ETLs (sequência recomendada)
python manage.py etl_00_mapeamento_empresas
python manage.py etl_01_contabilidades
python manage.py etl_02_cnaes
python manage.py etl_04_contratos
# ... demais ETLs conforme necessário
```

### **Execução dos ETLs:**

```bash
# ETLs Base (executar primeiro)
python manage.py etl_00_mapeamento_empresas
python manage.py etl_01_contabilidades
python manage.py etl_02_cnaes
python manage.py etl_04_contratos
python manage.py etl_21_quadro_societario

# ETLs Contábeis
python manage.py etl_05_plano_contas
python manage.py etl_06_lancamentos

# ETLs Fiscais
python manage.py etl_07_notas_fiscais
python manage.py etl_17_cupons_fiscais

# ETLs de RH
python manage.py etl_08_rh_cargos
python manage.py etl_09_rh_departamentos
python manage.py etl_10_rh_centros_custo
python manage.py etl_11_rh_funcionarios_vinculos
python manage.py etl_12_rh_historicos
python manage.py etl_13_rh_periodos_aquisitivos
python manage.py etl_14_rh_gozo_ferias
python manage.py etl_15_rh_afastamentos
python manage.py etl_16_rh_rescisoes

# ETLs de Administração
python manage.py etl_18_usuarios
python manage.py etl_19_logs_unificado_corrigido
```

### **Opções de Execução:**

```bash
# Modo de teste (não salva no banco)
python manage.py etl_XX_nome --dry-run

# Limitar quantidade de registros
python manage.py etl_XX_nome --limit 1000

# Apenas atualizar registros existentes
python manage.py etl_04_contratos --update-only

# Executar com progresso detalhado
python manage.py etl_18_usuarios --batch-size 1000 --progress-interval 50
```

---

## 🏗️ Estrutura Técnica Detalhada

### **Tecnologias:**
- **Backend:** Django 4.2.15
- **Banco de Dados:** PostgreSQL 13+
- **Sistema Legado:** Sybase SQL Anywhere (ODBC)
- **Python:** 3.11+
- **Cache:** Redis (planejado)
- **Frontend:** React/Vue (planejado)

### **Características Técnicas:**
- **Multi-tenancy Estrito:** Isolamento total por contabilidade
- **UUIDs:** Chaves primárias para escalabilidade
- **Auditoria:** Histórico completo de alterações
- **ETLs Idempotentes:** Execução segura múltiplas vezes
- **Transações Atômicas:** Consistência garantida
- **Processamento em Lotes:** Performance otimizada
- **Cache Inteligente:** TTL de 5 minutos para mapas

### **Padrões de Desenvolvimento:**
- **PEP 8:** Padrão de código Python
- **Django Best Practices:** Convenções do framework
- **Clean Architecture:** Separação de responsabilidades
- **SOLID Principles:** Princípios de design
- **Test-Driven Development:** Desenvolvimento orientado a testes

---

## 📊 Sistema de Mapeamento de Contabilidades

### **Regra de Ouro (Golden Rule):**

O sistema utiliza um mapeamento histórico robusto que resolve corretamente a contabilidade para cada empresa em qualquer data:

1. **Ponto de Partida:** `codi_emp` (Sybase) → `cgce_emp` (CNPJ/CPF) via `bethadba.geempre`
2. **Mapeamento Temporal:** Resolve a contabilidade correta baseada na data do evento
3. **Suporte a Contratos Ativos/Inativos:** Mantém histórico de 5 anos (2019-2024)
4. **Cache Inteligente:** Cache com TTL de 5 minutos para otimizar performance

### **Filtros de Qualidade:**
- Ignora empresas exemplo/modelo padrão
- Filtra CNPJs/CPFs fictícios
- Valida integridade dos dados
- Detecta sobreposições temporais

---

## 📚 Documentação Técnica

### **Guias Disponíveis:**
- **[Guia de Desenvolvimento](docs/desenvolvimento/README.md)** - Configuração e padrões
- **[Guia de ETLs](docs/etls/README.md)** - Sistema de migração
- **[Guia de Arquitetura](docs/arquitetura/README.md)** - Design e padrões
- **[Documentação da API](docs/api/README.md)** - Endpoints e exemplos
- **[Guia de Deploy](docs/deploy/README.md)** - Configuração de produção

### **Regras de Organização:**

#### **1. Estrutura de Apps:**
```
apps/
├── core/                    # Módulo central (Contabilidades, Usuários)
├── pessoas/                 # Pessoas e Contratos
├── fiscal/                  # Documentos Fiscais
├── funcionarios/            # Recursos Humanos
├── contabil/                # Contabilidade
├── administracao/           # Administração e Logs
├── cadastros_gerais/        # Cadastros Gerais
├── contabilidade_fiscal/    # Contabilidade Fiscal
└── importacao/              # Sistema ETL
```

#### **2. Padrões de Modelos:**
```python
class MeuModelo(models.Model):
    """Docstring descritiva do modelo."""
    
    # Campos obrigatórios
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.CASCADE)
    
    # Campos de negócio
    nome = models.CharField(max_length=255)
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = 'Meu Modelo'
        verbose_name_plural = 'Meus Modelos'
        db_table = 'app_meu_modelo'
        unique_together = ('contabilidade', 'nome')
        indexes = [
            models.Index(fields=['contabilidade', 'ativo']),
        ]
```

#### **3. Padrões de ETL:**
```python
from ._base import BaseETLCommand

class Command(BaseETLCommand):
    help = 'Descrição do ETL'
    
    def handle(self, *args, **options):
        # 1. Construir mapas de referência
        historical_map = self.build_historical_contabilidade_map_cached()
        
        # 2. Extrair dados do Sybase
        connection = self.get_sybase_connection()
        data = self.extract_data(connection)
        
        # 3. Processar e carregar
        stats = self.processar_dados(data, historical_map)
        
        # 4. Relatório final
        self.print_stats(stats)
```

---

## 🔒 Segurança e Multitenancy

### **Isolamento de Dados:**
- **Nível de Banco:** ForeignKey obrigatória para Contabilidade
- **Nível de Aplicação:** Filtros automáticos por contabilidade
- **Nível de API:** Validação de permissões
- **Nível de Cache:** Chaves isoladas por tenant

### **Validações de Segurança:**
- **CNPJ/CPF como Identificador Universal**
- **Resolução por Data do Evento**
- **Validação de Permissões de Usuário**
- **Auditoria de Acessos e Alterações**

---

## 📈 Performance e Otimização

### **Estratégias Implementadas:**
- **Processamento em Lotes:** Máximo 1000 registros por lote
- **Cache Inteligente:** TTL de 5 minutos para mapas
- **Índices Otimizados:** Consultas multitenant eficientes
- **Queries Otimizadas:** select_related e prefetch_related
- **Transações Atômicas:** Rollback automático em caso de erro

### **Monitoramento:**
- **Logs Detalhados:** Rastreamento de progresso e erros
- **Estatísticas de Execução:** Métricas de performance
- **Validação Pós-Execução:** Verificação de integridade

---

## 🚀 Roadmap e Próximas Fases

### **Fase 3: API REST (Em Andamento)**
- [ ] Endpoints para todas as entidades
- [ ] Sistema de autenticação JWT
- [ ] Documentação Swagger/OpenAPI
- [ ] Testes automatizados completos

### **Fase 4: Frontend (Planejado)**
- [ ] Interface React/Vue
- [ ] Dashboard de administração
- [ ] Relatórios e gráficos
- [ ] Sistema de notificações

### **Fase 5: Produção (Planejado)**
- [ ] Deploy em produção
- [ ] Monitoramento e alertas
- [ ] Backup e recuperação
- [ ] Escalabilidade horizontal

---

## 🤝 Contribuição

### **Para Desenvolvedores:**
1. Leia o [Guia de Desenvolvimento](docs/desenvolvimento/README.md)
2. Consulte a [Arquitetura](docs/arquitetura/README.md)
3. Use o [Guia de ETLs](docs/etls/README.md) para migração

### **Para DevOps:**
1. Consulte o [Guia de Deploy](docs/deploy/README.md)
2. Revise a [Arquitetura](docs/arquitetura/README.md)
3. Use o [Plano de Ação](docs/PLANO_ACAO_GAPS.md) para melhorias

---

## 📞 Suporte e Contato

- **Issues:** [GitHub Issues](https://github.com/gestk/issues)
- **Email:** suporte@gestk.com.br
- **Documentação:** [docs/README.md](docs/README.md)

---

**Última atualização:** 24/09/2025  
**Versão:** 2.0  
**Status:** Em Desenvolvimento Ativo
