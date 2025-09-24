# ETLs Disponíveis - GESTK

## 📋 Visão Geral

Este documento lista todos os ETLs disponíveis no sistema GESTK, organizados por módulo e com instruções detalhadas de execução.

## 🗂️ ETLs por Módulo

### 1. Mapeamento e Base

#### ETL 00 - Mapeamento Completo de Empresas
**Arquivo:** `etl_00_mapeamento_empresas.py`
**Descrição:** Pré-processamento que garante cobertura completa de todas as empresas do Sybase
**Status:** ✅ Implementado e Testado

**Funcionalidades:**
- Identifica todas as empresas no Sybase
- Filtra empresas exemplo/modelo padrão
- Cria Pessoas Jurídicas/Físicas faltantes
- Cria Contratos padrão (2019-2024)
- Valida integridade do mapeamento

**Comando:**
```bash
python manage.py etl_00_mapeamento_empresas [--dry-run] [--limit N]
```

**Opções:**
- `--dry-run`: Modo de teste (não salva no banco)
- `--limit N`: Limita quantidade de empresas processadas

#### ETL 01 - Contabilidades
**Arquivo:** `etl_01_contabilidades.py`
**Descrição:** Importa contabilidades (tenants) do sistema legado
**Status:** ✅ Implementado

#### ETL 02 - CNAEs
**Arquivo:** `etl_02_cnaes.py`
**Descrição:** Importa códigos CNAE do sistema legado
**Status:** ✅ Implementado

#### ETL 04 - Contratos
**Arquivo:** `etl_04_contratos.py`
**Descrição:** Importa contratos e cria Pessoas Físicas/Jurídicas com dados específicos
**Status:** ✅ Implementado e Otimizado

**Comando:**
```bash
python manage.py etl_04_contratos [--dry-run] [--limit N] [--update-only]
```

**Opções:**
- `--dry-run`: Modo de teste
- `--limit N`: Limita quantidade de contratos
- `--update-only`: Apenas atualiza registros existentes

### 2. Contábeis

#### ETL 05 - Plano de Contas
**Arquivo:** `etl_05_plano_contas.py`
**Descrição:** Importa plano de contas do sistema legado
**Status:** ✅ Implementado e Otimizado

#### ETL 06 - Lançamentos Contábeis
**Arquivo:** `etl_06_lancamentos.py`
**Descrição:** Importa lançamentos contábeis do sistema legado
**Status:** ✅ Implementado e Otimizado

### 3. Fiscais

#### ETL 07 - Notas Fiscais
**Arquivo:** `etl_07_notas_fiscais.py`
**Descrição:** Importa notas fiscais (entrada/saída) e serviços
**Status:** ✅ Implementado

**Funcionalidades:**
- NFe de entrada e saída
- NFS-e (serviços)
- Tratamento correto de CFOPs 1933/2933
- Mapeamento de parceiros de negócio

#### ETL 17 - Cupons Fiscais
**Arquivo:** `etl_17_cupons_fiscais.py`
**Descrição:** Importa cupons fiscais eletrônicos
**Status:** ✅ Implementado

**Funcionalidades:**
- Cupons fiscais eletrônicos (CFE)
- Cupons fiscais ECF
- Importação de itens detalhados
- Criação de pessoa genérica para clientes sem CPF
- Processamento em lotes

**Comando:**
```bash
python manage.py etl_17_cupons_fiscais [--dry-run] [--limit N]
```

### 4. Recursos Humanos

#### ETL 08 - Cargos
**Arquivo:** `etl_08_cargos.py`
**Descrição:** Importa cargos do sistema legado
**Status:** ✅ Implementado

#### ETL 09 - Departamentos
**Arquivo:** `etl_09_departamentos.py`
**Descrição:** Importa departamentos do sistema legado
**Status:** ✅ Implementado

#### ETL 10 - Centros de Custo
**Arquivo:** `etl_10_centros_custo.py`
**Descrição:** Importa centros de custo do sistema legado
**Status:** ✅ Implementado

#### ETL 11 - Funcionários
**Arquivo:** `etl_11_funcionarios.py`
**Descrição:** Importa funcionários, vínculos empregatícios e rubricas
**Status:** ✅ Implementado

#### ETL 16 - Rescisões
**Arquivo:** `etl_16_rh_rescisoes.py`
**Descrição:** Importa rescisões de funcionários
**Status:** ✅ Implementado

**Arquivo:** `etl_16_rh_rescisoes_rubricas.py`
**Descrição:** Importa rubricas de rescisões
**Status:** ✅ Implementado

### 5. Administração (Em Desenvolvimento)

#### ETL 18 - Usuários e Configurações
**Arquivo:** `etl_18_usuarios.py` (a ser criado)
**Descrição:** Importa usuários e configurações do sistema legado
**Status:** ❌ Planejado

#### ETL 19 - Logs de Acesso
**Arquivo:** `etl_19_logs_acesso.py` (a ser criado)
**Descrição:** Importa logs de acesso e tempo no sistema
**Status:** ❌ Planejado

#### ETL 20 - Lançamentos por Usuário
**Arquivo:** `etl_20_lancamentos_usuario.py` (a ser criado)
**Descrição:** Importa lançamentos realizados por usuário
**Status:** ❌ Planejado

## 🔄 Sequência de Execução Recomendada

### Ordem Obrigatória:
1. **ETL 00** - Mapeamento Completo de Empresas (execute primeiro)
2. **ETL 01** - Contabilidades
3. **ETL 02** - CNAEs
4. **ETL 04** - Contratos

### Ordem Recomendada:
5. **ETL 05** - Plano de Contas
6. **ETL 06** - Lançamentos Contábeis
7. **ETL 07** - Notas Fiscais
8. **ETL 17** - Cupons Fiscais
9. **ETL 08-11** - ETLs de RH (cargos, departamentos, funcionários)
10. **ETL 16** - Rescisões

## ⚙️ Opções Comuns de Execução

### Modo de Teste (Dry Run)
```bash
python manage.py etl_XX_nome --dry-run
```
- Não salva dados no banco
- Útil para validar lógica antes da execução real

### Limitar Quantidade
```bash
python manage.py etl_XX_nome --limit 1000
```
- Processa apenas N registros
- Útil para testes e validações

### Apenas Atualizar
```bash
python manage.py etl_04_contratos --update-only
```
- Apenas atualiza registros existentes
- Não cria novos registros

## 📊 Monitoramento e Logs

### Estatísticas de Performance
Todos os ETLs otimizados incluem:
- Cache hits/misses
- Consultas Sybase executadas
- Registros processados
- Tempo de execução
- Taxa de sucesso

### Logs Detalhados
- Progresso em tempo real
- Erros detalhados
- Relatórios de execução
- Validações de integridade

## 🚨 Troubleshooting

### Problemas Comuns:

1. **"Sem Contabilidade"**
   - Execute ETL 00 primeiro
   - Verifique se ETL 01 foi executado

2. **"Empresa não encontrada"**
   - Execute ETL 00 para mapeamento completo
   - Verifique filtros de qualidade

3. **Performance lenta**
   - Use `--limit` para testar com menos dados
   - Verifique conexão com Sybase

4. **Dados duplicados**
   - ETLs são idempotentes, execute novamente
   - Verifique chaves de unicidade

### Validação de Integridade:
```bash
# Verificar mapeamento
python manage.py etl_00_mapeamento_empresas --dry-run

# Validar contratos
python manage.py etl_04_contratos --dry-run --limit 100
```

## 📈 Métricas de Sucesso

### ETL 00:
- ✅ Empresas exemplo ignoradas
- ✅ Empresas reais processadas
- ✅ Contratos criados com sucesso

### ETL 04:
- ✅ Contratos importados/atualizados
- ✅ Pessoas criadas/atualizadas
- ✅ Zero erros de mapeamento

### ETLs Fiscais:
- ✅ Notas fiscais importadas
- ✅ Cupons fiscais processados
- ✅ Itens detalhados importados

### ETLs RH:
- ✅ Funcionários importados
- ✅ Vínculos criados
- ✅ Rescisões processadas

