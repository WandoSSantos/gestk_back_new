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

## 3. Status Atual do Projeto (17 de Setembro de 2025)

Estamos atualmente na **Fase de Migração de Dados (ETL)**.

### Processos Concluídos:

1.  **Setup do Ambiente:** Criação do projeto Django, configuração do banco de dados PostgreSQL e conexão com o Sybase.
2.  **ETL - Módulos Base:**
    -   `Contabilidades` (Tenants)
    -   `CNAEs`
    -   `Contratos`, `Pessoas Físicas` e `Pessoas Jurídicas`
    -   `Plano de Contas`
    -   `Lançamentos Contábeis`
3.  **Refatoração da Arquitetura Fiscal:** Reestruturamos os modelos `NotaFiscal` e `Pessoa` para remover complexidade e aumentar a performance e a segurança dos relacionamentos.

### Processo em Andamento:

-   **ETL Unificado de Documentos Fiscais:** Estamos finalizando o desenvolvimento do script que importará todos os tipos de documentos fiscais (NFe de Entrada, NFe de Saída, NFS-e e Cupons Fiscais) de uma só vez.
-   **Nosso próximo passo imediato é:** Validar este ETL unificado executando um script de teste (`etl_07_unificado_test.py`) com um lote limitado de ~1000 registros para garantir que a lógica de importação para todos os quatro tipos de documentos está correta antes de executar a importação completa de mais de 1.3 milhão de notas.

### Próximas Fases do Projeto:

1.  **Concluir a Importação Fiscal:** Executar o ETL unificado completo.
2.  **Iniciar ETL do Módulo RH:** Mapear e importar as tabelas de funcionários.
3.  **Desenvolvimento da API REST:** Construir os endpoints para que o frontend possa consumir os dados, garantindo que todas as consultas respeitem o isolamento multi-tenant.
4.  **Testes Automatizados:** Criar uma suíte de testes para validar as regras de negócio e a segurança do sistema.
