# Execução Sequencial de ETLs - GESTK

## 🎯 Visão Geral

Este documento descreve como executar os ETLs do GESTK de forma sequencial, respeitando as dependências e garantindo a integridade dos dados.

## 📋 Scripts Disponíveis

### 1. Script Python (Recomendado)
**Arquivo:** `executar_etls_sequencial.py`
**Plataforma:** Windows, Linux, Mac
**Funcionalidades:** Controle completo de execução, relatórios detalhados, tratamento de erros

### 2. Script Batch (Windows)
**Arquivo:** `executar_etls_sequencial.bat`
**Plataforma:** Windows
**Funcionalidades:** Interface simples para Windows

### 3. Script Shell (Linux/Mac)
**Arquivo:** `executar_etls_sequencial.sh`
**Plataforma:** Linux, Mac
**Funcionalidades:** Interface simples para Unix

## 🚀 Como Usar

### Execução Básica

```bash
# Execução completa (produção)
python executar_etls_sequencial.py

# Execução em modo de teste
python executar_etls_sequencial.py --dry-run

# Usando script batch (Windows)
executar_etls_sequencial.bat --dry-run

# Usando script shell (Linux/Mac)
./executar_etls_sequencial.sh --dry-run
```

### Opções Avançadas

```bash
# Iniciar a partir de um ETL específico
python executar_etls_sequencial.py --etl-inicial 05

# Parar em um ETL específico
python executar_etls_sequencial.py --etl-final 10

# Pular ETLs específicos
python executar_etls_sequencial.py --skip-etls 05,06,07

# Configurar tamanho do lote
python executar_etls_sequencial.py --batch-size 2000

# Configurar intervalo de progresso
python executar_etls_sequencial.py --progress-interval 100

# Combinando opções
python executar_etls_sequencial.py --dry-run --etl-inicial 05 --etl-final 10 --batch-size 1500
```

## 📊 Sequência de Execução

### ETLs Base (Executar Primeiro)
1. **ETL 00** - Mapeamento Completo de Empresas ⚠️ **CRÍTICO**
2. **ETL 01** - Contabilidades (Tenants) ⚠️ **CRÍTICO**
3. **ETL 02** - CNAEs ⚠️ **CRÍTICO**
4. **ETL 03** - Contratos, Pessoas Físicas e Jurídicas ⚠️ **CRÍTICO**
5. **ETL 04** - Quadro Societário

### ETLs Contábeis
6. **ETL 05** - Plano de Contas
7. **ETL 06** - Lançamentos Contábeis

### ETLs Fiscais
8. **ETL 07** - Notas Fiscais (entrada/saída/serviços)
9. **ETL 17** - Cupons Fiscais Eletrônicos

### ETLs de RH
10. **ETL 08** - Cargos
11. **ETL 09** - Departamentos
12. **ETL 10** - Centros de Custo
13. **ETL 11** - Funcionários e Vínculos
14. **ETL 11b** - Rubricas de RH
15. **ETL 12** - Históricos de Salário e Cargo
16. **ETL 13** - Períodos Aquisitivos de Férias
17. **ETL 14** - Gozo de Férias
18. **ETL 15** - Afastamentos
19. **ETL 16** - Rescisões
20. **ETL 16b** - Rubricas de Rescisão

### ETLs de Administração
21. **ETL 18** - Usuários e Configurações
22. **ETL 19** - Logs de Acesso e Atividades

## 🔄 Dependências

### Mapa de Dependências
```
ETL 00 (Mapeamento) → ETL 01, 02, 03
ETL 01 (Contabilidades) → ETL 03, 05, 18
ETL 02 (CNAEs) → Nenhuma dependência
ETL 03 (Contratos) → ETL 04, 07, 17, 08, 09, 10, 11, 18
ETL 04 (Quadro Societário) → Nenhuma dependência adicional
ETL 05 (Plano de Contas) → ETL 06
ETL 08 (Cargos) → ETL 11
ETL 09 (Departamentos) → ETL 11
ETL 10 (Centros de Custo) → ETL 11
ETL 11 (Funcionários) → ETL 11b, 12, 13, 15, 16
ETL 13 (Períodos Aquisitivos) → ETL 14
ETL 16 (Rescisões) → ETL 16b
ETL 18 (Usuários) → ETL 19
```

## ⚙️ Configurações

### Parâmetros Recomendados

#### Para Desenvolvimento/Teste
```bash
python executar_etls_sequencial.py --dry-run --batch-size 500 --progress-interval 25
```

#### Para Produção (Pequeno Volume)
```bash
python executar_etls_sequencial.py --batch-size 1000 --progress-interval 50
```

#### Para Produção (Grande Volume)
```bash
python executar_etls_sequencial.py --batch-size 2500 --progress-interval 100
```

## 📈 Monitoramento

### Relatórios Automáticos
O script gera relatórios automáticos incluindo:
- Tempo de execução por ETL
- Tempo total de execução
- Número de ETLs executados com sucesso
- Número de ETLs com erro
- Número de ETLs pulados
- Logs detalhados de cada execução

### Exemplo de Saída
```
======================================================================
EXECUTANDO ETL 00 - Mapeamento Completo de Empresas
======================================================================
✅ ETL 00 executado com sucesso em 45.32s

======================================================================
EXECUTANDO ETL 01 - Contabilidades (Tenants)
======================================================================
✅ ETL 01 executado com sucesso em 12.15s

...

======================================================================
RELATÓRIO FINAL DE EXECUÇÃO
======================================================================
Início: 24/09/2025 14:30:15
Fim: 24/09/2025 16:45:30
Tempo total: 8100.00s
ETLs executados: 22
ETLs com sucesso: 22
ETLs com erro: 0
ETLs pulados: 0

✅ Todos os ETLs executados com sucesso!
```

## 🚨 Tratamento de Erros

### ETLs Críticos
Se um ETL crítico falhar, a execução é interrompida:
- ETL 00 (Mapeamento)
- ETL 01 (Contabilidades)
- ETL 02 (CNAEs)
- ETL 04 (Contratos)

### ETLs Não-Críticos
Se um ETL não-crítico falhar, a execução continua:
- Todos os demais ETLs

### Recuperação de Erros
1. Verifique os logs de erro
2. Corrija o problema identificado
3. Execute novamente a partir do ETL que falhou:
   ```bash
   python executar_etls_sequencial.py --etl-inicial 05
   ```

## 🔧 Troubleshooting

### Problemas Comuns

#### 1. "ETL não encontrado"
- Verifique se o comando está correto
- Execute `python manage.py help` para listar ETLs disponíveis

#### 2. "Dependências não atendidas"
- Execute os ETLs base primeiro (00, 01, 02, 04)
- Verifique se os ETLs dependentes foram executados com sucesso

#### 3. "Erro de conexão com Sybase"
- Verifique as configurações em `settings.py`
- Teste a conexão manualmente

#### 4. "Erro de permissão"
- Verifique se o usuário tem permissões adequadas
- Execute como administrador se necessário

### Logs Detalhados
Para logs mais detalhados, execute individualmente:
```bash
python manage.py etl_XX_nome --dry-run
```

## 📚 Exemplos Práticos

### Exemplo 1: Primeira Execução Completa
```bash
# 1. Executar em modo de teste primeiro
python executar_etls_sequencial.py --dry-run

# 2. Se tudo estiver OK, executar em produção
python executar_etls_sequencial.py
```

### Exemplo 2: Executar Apenas ETLs de RH
```bash
python executar_etls_sequencial.py --etl-inicial 08 --etl-final 16b
```

### Exemplo 3: Pular ETLs Fiscais
```bash
python executar_etls_sequencial.py --skip-etls 07,17
```

### Exemplo 4: Execução com Configurações Otimizadas
```bash
python executar_etls_sequencial.py --batch-size 2000 --progress-interval 75
```

## 🎯 Próximos Passos

Após a execução sequencial dos ETLs:
1. Verifique os relatórios de execução
2. Valide os dados importados
3. Execute testes de integridade
4. Configure backups automáticos
5. Monitore performance do sistema

---

**Documento criado em**: 24/09/2025  
**Versão**: 1.0  
**Próxima revisão**: 01/10/2025
