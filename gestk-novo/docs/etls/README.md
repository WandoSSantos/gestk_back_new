# Guia de ETLs - GESTK

## 🎯 Visão Geral

O sistema de ETL (Extract, Transform, Load) do GESTK é responsável pela migração de dados do sistema legado Sybase SQL Anywhere para o novo sistema PostgreSQL. Todos os ETLs seguem padrões rigorosos de:

- **Idempotência**: Execução múltipla sem duplicação
- **Multitenancy**: Isolamento correto por contabilidade
- **Transacionalidade**: Rollback automático em caso de erro
- **Performance**: Processamento em lotes eficiente

## 🏗️ Arquitetura do Sistema ETL

### BaseETLCommand

Todos os ETLs herdam da classe `BaseETLCommand` que fornece:

```python
class BaseETLCommand(BaseCommand):
    """Classe base para comandos de ETL."""
    
    def get_sybase_connection(self):
        """Conexão com Sybase via ODBC."""
        
    def execute_query(self, connection, query):
        """Execução de queries no Sybase."""
        
    def build_historical_contabilidade_map_cached(self):
        """Mapa histórico de contabilidades por CNPJ/CPF com cache."""
        
    def get_contabilidade_for_date_optimized(self, historical_map, codi_emp, event_date):
        """Resolve contabilidade para empresa em data específica."""
        
    def limpar_documento(self, documento):
        """Remove caracteres não numéricos de documentos."""
        
    def print_stats(self, stats):
        """Imprime estatísticas de execução."""
```

## 📋 Lista Completa de ETLs

### **ETLs Base (Executar Primeiro)**

| ETL | Descrição | Status | Dependências | Comando |
|-----|-----------|--------|--------------|---------|
| **ETL 00** | Mapeamento Completo de Empresas | ✅ | Nenhuma | `etl_00_mapeamento_empresas` |
| **ETL 01** | Contabilidades (Tenants) | ✅ | Nenhuma | `etl_01_contabilidades` |
| **ETL 02** | CNAEs | ✅ | Nenhuma | `etl_02_cnaes` |
| **ETL 04** | Contratos, Pessoas Físicas e Jurídicas | ✅ | ETL 01 | `etl_04_contratos` |

### **ETLs Contábeis**

| ETL | Descrição | Status | Dependências | Comando |
|-----|-----------|--------|--------------|---------|
| **ETL 05** | Plano de Contas | ✅ | ETL 01 | `etl_05_plano_contas` |
| **ETL 06** | Lançamentos Contábeis | ✅ | ETL 05 | `etl_06_lancamentos` |

### **ETLs Fiscais**

| ETL | Descrição | Status | Dependências | Comando |
|-----|-----------|--------|--------------|---------|
| **ETL 07** | Notas Fiscais (NFe entrada/saída/serviços) | ✅ | ETL 04 | `etl_07_notas_fiscais` |
| **ETL 17** | Cupons Fiscais Eletrônicos | ✅ | ETL 04 | `etl_17_cupons_fiscais` |

### **ETLs de Recursos Humanos**

| ETL | Descrição | Status | Dependências | Comando |
|-----|-----------|--------|--------------|---------|
| **ETL 08** | Cargos | ✅ | ETL 04 | `etl_08_rh_cargos` |
| **ETL 09** | Departamentos | ✅ | ETL 04 | `etl_09_rh_departamentos` |
| **ETL 10** | Centros de Custo | ✅ | ETL 04 | `etl_10_rh_centros_custo` |
| **ETL 11** | Funcionários, Vínculos e Rubricas | ✅ | ETLs 08-10 | `etl_11_rh_funcionarios_vinculos` |
| **ETL 12** | Históricos de Salário e Cargo | ✅ | ETL 11 | `etl_12_rh_historicos` |
| **ETL 13** | Períodos Aquisitivos de Férias | ✅ | ETL 11 | `etl_13_rh_periodos_aquisitivos` |
| **ETL 14** | Gozo de Férias | ✅ | ETL 13 | `etl_14_rh_gozo_ferias` |
| **ETL 15** | Afastamentos | ✅ | ETL 11 | `etl_15_rh_afastamentos` |
| **ETL 16** | Rescisões e Rubricas de Rescisão | ✅ | ETL 11 | `etl_16_rh_rescisoes` |

### **ETLs de Administração**

| ETL | Descrição | Status | Dependências | Comando |
|-----|-----------|--------|--------------|---------|
| **ETL 18** | Usuários e Configurações | ✅ | ETL 04 | `etl_18_usuarios` |
| **ETL 19** | Logs de Acesso e Atividades | ✅ | ETL 18 | `etl_19_logs_unificado_corrigido` |
| **ETL 21** | Quadro Societário | ✅ | ETL 04 | `etl_21_quadro_societario` |

### **ETLs Pendentes**

| ETL | Descrição | Status | Dependências | Comando |
|-----|-----------|--------|--------------|---------|
| **ETL 20** | Lançamentos por Usuário | 🚧 | ETL 18 | `etl_20_lancamentos_usuario` |

## 🔄 Fluxo de Execução

### **Ordem Obrigatória de Execução**

```bash
# 1. ETLs Base (executar primeiro)
python manage.py etl_00_mapeamento_empresas
python manage.py etl_01_contabilidades
python manage.py etl_02_cnaes
python manage.py etl_04_contratos
python manage.py etl_21_quadro_societario

# 2. ETLs Contábeis
python manage.py etl_05_plano_contas
python manage.py etl_06_lancamentos

# 3. ETLs Fiscais
python manage.py etl_07_notas_fiscais
python manage.py etl_17_cupons_fiscais

# 4. ETLs de RH (em ordem)
python manage.py etl_08_rh_cargos
python manage.py etl_09_rh_departamentos
python manage.py etl_10_rh_centros_custo
python manage.py etl_11_rh_funcionarios_vinculos
python manage.py etl_12_rh_historicos
python manage.py etl_13_rh_periodos_aquisitivos
python manage.py etl_14_rh_gozo_ferias
python manage.py etl_15_rh_afastamentos
python manage.py etl_16_rh_rescisoes

# 5. ETLs de Administração
python manage.py etl_18_usuarios
python manage.py etl_19_logs_unificado_corrigido
```

### **Opções de Execução**

```bash
# Modo de teste (não salva no banco)
python manage.py etl_XX_nome --dry-run

# Limitar quantidade de registros
python manage.py etl_XX_nome --limit 1000

# Apenas atualizar registros existentes
python manage.py etl_04_contratos --update-only

# Executar com progresso detalhado
python manage.py etl_18_usuarios --batch-size 1000 --progress-interval 50

# Executar com data específica
python manage.py etl_19_logs_unificado_corrigido --data-inicio 2020-01-01 --data-fim 2020-12-31
```

## 🎯 Padrões de Implementação

### **1. Estrutura Básica de ETL**

```python
from ._base import BaseETLCommand
from django.db import transaction
from tqdm import tqdm

class Command(BaseETLCommand):
    help = 'Descrição do ETL'
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Modo de teste')
        parser.add_argument('--limit', type=int, help='Limitar registros')
        parser.add_argument('--batch-size', type=int, default=1000, help='Tamanho do lote')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL ---'))
        
        # 1. Construir mapas de referência
        historical_map = self.build_historical_contabilidade_map_cached()
        
        # 2. Extrair dados do Sybase
        connection = self.get_sybase_connection()
        if not connection:
            return
        
        try:
            data = self.extract_data(connection)
            
            # 3. Processar e carregar
            stats = self.processar_dados(data, historical_map, options)
            
            # 4. Relatório final
            self.print_stats(stats)
            
        finally:
            connection.close()
    
    def extract_data(self, connection):
        """Extrai dados do Sybase."""
        query = """
        SELECT campo1, campo2, campo3
        FROM bethadba.tabela
        WHERE condicao = 'valor'
        """
        return self.execute_query(connection, query)
    
    def processar_dados(self, data, historical_map, options):
        """Processa e carrega dados no PostgreSQL."""
        stats = {'criados': 0, 'atualizados': 0, 'erros': 0}
        
        for row in tqdm(data, desc="Processando dados"):
            try:
                # Resolver contabilidade
                contabilidade = self.get_contabilidade_for_date_optimized(
                    historical_map, 
                    row['codi_emp'], 
                    row['data_evento']
                )
                
                if not contabilidade:
                    stats['erros'] += 1
                    continue
                
                # Criar/atualizar registro
                obj, created = MeuModelo.objects.update_or_create(
                    contabilidade=contabilidade,
                    id_legado=row['id_legado'],
                    defaults={
                        'campo1': row['campo1'],
                        'campo2': row['campo2'],
                    }
                )
                
                if created:
                    stats['criados'] += 1
                else:
                    stats['atualizados'] += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro: {e}"))
                stats['erros'] += 1
        
        return stats
```

### **2. Resolução de Multitenancy**

```python
def get_contabilidade_for_date_optimized(self, historical_map, codi_emp, event_date):
    """
    Resolve a contabilidade correta para uma empresa em uma data específica.
    
    Fluxo:
    1. Busca CNPJ/CPF da empresa no Sybase usando CODI_EMP
    2. Usa o documento para encontrar contratos na data
    3. Retorna a contabilidade do contrato ativo
    """
    # Implementação na BaseETLCommand
    pass
```

### **3. Processamento em Lotes**

```python
def processar_dados(self, data, historical_map, options):
    """Processamento em lotes para performance."""
    BATCH_SIZE = options.get('batch_size', 1000)
    stats = {'criados': 0, 'atualizados': 0, 'erros': 0}
    
    for i in range(0, len(data), BATCH_SIZE):
        batch = data[i:i + BATCH_SIZE]
        
        with transaction.atomic():
            for row in batch:
                # Processar registro
                pass
```

## 🔍 Validações e Regras

### **1. Regras de Multitenancy**

- **CNPJ/CPF como Identificador Universal**: Sempre usar documento limpo
- **Resolução por Data**: Contabilidade ativa na data do evento
- **Isolamento Total**: Impossível vazamento entre contabilidades

### **2. Regras de Idempotência**

- **Chaves Únicas**: `(contabilidade, id_legado)` ou similar
- **update_or_create**: Sempre usar para evitar duplicação
- **Validação de Dados**: Verificar integridade antes de salvar

### **3. Regras de Performance**

- **Processamento em Lotes**: Máximo 1000 registros por lote
- **Transações Atômicas**: Rollback automático em caso de erro
- **Logs Detalhados**: Rastreamento de progresso e erros

## 🐛 Debugging e Troubleshooting

### **1. Logs de Debug**

```python
# Adicionar logs detalhados
self.stdout.write(f"Processando registro: {row['id']}")
self.stdout.write(f"Contabilidade encontrada: {contabilidade.razao_social}")
```

### **2. Validação de Dados**

```python
def validar_dados(self, row):
    """Valida dados antes do processamento."""
    if not row.get('campo_obrigatorio'):
        raise ValueError("Campo obrigatório ausente")
    
    if not self.validar_documento(row.get('cnpj')):
        raise ValueError("CNPJ inválido")
```

### **3. Tratamento de Erros**

```python
try:
    # Processamento
    pass
except Exception as e:
    self.stdout.write(self.style.ERROR(f"Erro no registro {row['id']}: {e}"))
    # Continuar processamento
    continue
```

## 📊 Monitoramento

### **1. Estatísticas de Execução**

```python
def print_stats(self, stats):
    """Imprime estatísticas de execução."""
    self.stdout.write(self.style.SUCCESS('--- Resumo da Execução ---'))
    self.stdout.write(f"  - Registros Criados: {stats['criados']}")
    self.stdout.write(f"  - Registros Atualizados: {stats['atualizados']}")
    self.stdout.write(f"  - Erros: {stats['erros']}")
```

### **2. Validação Pós-Execução**

```python
def validar_execucao(self):
    """Valida se a execução foi bem-sucedida."""
    total_sybase = self.count_sybase_records()
    total_postgres = MeuModelo.objects.count()
    
    if total_sybase != total_postgres:
        self.stdout.write(self.style.WARNING(
            f"Divergência: Sybase={total_sybase}, PostgreSQL={total_postgres}"
        ))
```

## 🚀 Otimizações

### **1. Queries Otimizadas**

```python
# Usar select_related para evitar N+1 queries
contratos = Contrato.objects.select_related('contabilidade', 'content_type')

# Usar prefetch_related para relacionamentos many-to-many
pessoas = PessoaJuridica.objects.prefetch_related('cnaes_secundarios')
```

### **2. Cache de Dados**

```python
def build_cache_map(self):
    """Constrói mapa em memória para performance."""
    cache = {}
    for obj in MeuModelo.objects.all():
        cache[obj.id_legado] = obj
    return cache
```

### **3. Processamento Paralelo**

```python
from concurrent.futures import ThreadPoolExecutor

def processar_paralelo(self, data):
    """Processamento paralelo para grandes volumes."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(self.processar_lote, lote) for lote in lotes]
        results = [future.result() for future in futures]
```

## 📚 ETLs Específicos Detalhados

### **ETL 00 - Mapeamento Completo de Empresas**

**Objetivo:** Pré-processamento que garante cobertura completa de todas as empresas do Sybase.

**Funcionalidades:**
- Extrai todas as empresas do Sybase
- Cria Pessoas Jurídicas/Físicas no PostgreSQL
- Cria contratos para o período 2019-2024
- Garante que o mapeamento de contabilidades funcione

**Comando:**
```bash
python manage.py etl_00_mapeamento_empresas
```

### **ETL 18 - Usuários e Configurações**

**Objetivo:** Importa usuários do sistema legado com mapeamento multitenant.

**Funcionalidades:**
- Importa usuários do USCONFUSUARIO
- Cria vínculos usuário-empresa-contabilidade
- Importa módulos acessíveis
- Aplica regra de ouro para mapeamento

**Comando:**
```bash
python manage.py etl_18_usuarios --batch-size 1000 --progress-interval 50
```

### **ETL 19 - Logs de Acesso e Atividades**

**Objetivo:** Importa logs unificados (atividades, importações, lançamentos).

**Funcionalidades:**
- GELOGUSER → LogAtividade
- EFSAIDAS, EFENTRADAS, EFSERVICOS → LogImportacao
- CTLANCTO → LogLancamento
- Estatísticas consolidadas

**Comando:**
```bash
python manage.py etl_19_logs_unificado_corrigido --tipo todos --data-inicio 2019-01-01
```

### **ETL 21 - Quadro Societário**

**Objetivo:** Importa quadro societário das empresas com sócios e participações.

**Funcionalidades:**
- Importa sócios (PF e PJ)
- Cria participações e quotas
- Importa capital social
- Atualiza dados de endereço das empresas

**Comando:**
```bash
python manage.py etl_21_quadro_societario --limit 100
```

## 🔧 Configuração e Troubleshooting

### **Configuração do Sybase**

```python
# settings.py
SYBASE_CONFIG = {
    'DRIVER': 'SQL Anywhere 17',
    'SERVER': 'servidor_sybase',
    'DATABASE': 'nome_banco',
    'UID': 'usuario',
    'PWD': 'senha',
}
```

### **Problemas Comuns**

1. **Erro de Conexão Sybase**
   - Verificar configuração ODBC
   - Testar conexão manual
   - Verificar firewall e rede

2. **Erro de Multitenancy**
   - Verificar se ETL 00 foi executado
   - Verificar mapa histórico
   - Validar CNPJ/CPF

3. **Erro de Performance**
   - Reduzir batch_size
   - Verificar índices do banco
   - Monitorar uso de memória

## 📚 Referências

- [Django Management Commands](https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/)
- [PostgreSQL Performance](https://www.postgresql.org/docs/current/performance-tips.html)
- [PyODBC Documentation](https://github.com/mkleehammer/pyodbc)
- [Django Transactions](https://docs.djangoproject.com/en/4.2/topics/db/transactions/)

---

**Última atualização:** 24/09/2025  
**Versão:** 2.0  
**Status:** Documentação Completa