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
        
    def build_historical_contabilidade_map(self):
        """Mapa histórico de contabilidades por CNPJ/CPF."""
        
    def get_contabilidade_for_date(self, historical_map, codi_emp, event_date):
        """Resolve contabilidade para empresa em data específica."""
        
    def limpar_documento(self, documento):
        """Remove caracteres não numéricos de documentos."""
```

## 📋 Lista de ETLs

### ETLs Base (Executar Primeiro)

| ETL | Descrição | Status | Dependências |
|-----|-----------|--------|--------------|
| `etl_01_contabilidades` | Importa contabilidades (tenants) | ✅ | Nenhuma |
| `etl_02_cnaes` | Importa códigos CNAE | ✅ | Nenhuma |
| `etl_04_contratos` | Importa contratos de clientes | ✅ | ETL 01 |
| `etl_05_plano_contas` | Importa plano de contas | ✅ | ETL 01 |
| `etl_06_lancamentos` | Importa lançamentos contábeis | ✅ | ETL 05 |

### ETLs de Pessoas

| ETL | Descrição | Status | Dependências |
|-----|-----------|--------|--------------|
| `etl_05_plano_contas` | Pessoas Jurídicas | ✅ | ETL 04 |
| `etl_06_lancamentos` | Pessoas Físicas | ✅ | ETL 04 |

### ETLs Fiscais

| ETL | Descrição | Status | Dependências |
|-----|-----------|--------|--------------|
| `etl_07_notas_fiscais` | Notas Fiscais e Itens | ✅ | ETLs Pessoas |

### ETLs de RH

| ETL | Descrição | Status | Dependências |
|-----|-----------|--------|--------------|
| `etl_08_rh_cargos` | Cargos | ✅ | ETLs Pessoas |
| `etl_09_rh_departamentos` | Departamentos | ✅ | ETLs Pessoas |
| `etl_10_rh_centros_custo` | Centros de Custo | ✅ | ETLs Pessoas |
| `etl_11_rh_funcionarios_vinculos` | Funcionários e Vínculos | ✅ | ETLs 08-10 |
| `etl_11_rh_rubricas` | Rubricas | ✅ | ETL 11 |
| `etl_12_rh_historicos` | Históricos de Salário e Cargo | ✅ | ETL 11 |
| `etl_13_rh_periodos_aquisitivos` | Períodos Aquisitivos de Férias | ✅ | ETL 11 |
| `etl_14_rh_gozo_ferias` | Gozo de Férias | ✅ | ETL 13 |
| `etl_15_rh_afastamentos` | Afastamentos | ✅ | ETL 11 |
| `etl_16_rh_rescisoes` | Rescisões | ✅ | ETL 11 |
| `etl_16_rh_rescisoes_rubricas` | Rubricas de Rescisão | ✅ | ETL 16 |

## 🔄 Fluxo de Execução

### Ordem Obrigatória

```bash
# 1. ETLs Base
python manage.py etl_01_contabilidades
python manage.py etl_02_cnaes
python manage.py etl_04_contratos
python manage.py etl_05_plano_contas
python manage.py etl_06_lancamentos

# 2. ETLs de Pessoas
python manage.py etl_05_plano_contas  # Pessoas Jurídicas
python manage.py etl_06_lancamentos   # Pessoas Físicas

# 3. ETLs Fiscais
python manage.py etl_07_notas_fiscais

# 4. ETLs de RH (em ordem)
python manage.py etl_08_rh_cargos
python manage.py etl_09_rh_departamentos
python manage.py etl_10_rh_centros_custo
python manage.py etl_11_rh_funcionarios_vinculos
python manage.py etl_11_rh_rubricas
python manage.py etl_12_rh_historicos
python manage.py etl_13_rh_periodos_aquisitivos
python manage.py etl_14_rh_gozo_ferias
python manage.py etl_15_rh_afastamentos
python manage.py etl_16_rh_rescisoes
python manage.py etl_16_rh_rescisoes_rubricas
```

## 🎯 Padrões de Implementação

### 1. Estrutura Básica

```python
from ._base import BaseETLCommand
from django.db import transaction
from tqdm import tqdm

class Command(BaseETLCommand):
    help = 'Descrição do ETL'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando ETL ---'))
        
        connection = self.get_sybase_connection()
        if not connection:
            return
        
        try:
            # 1. Construir mapas de referência
            historical_map = self.build_historical_contabilidade_map()
            
            # 2. Extrair dados do Sybase
            data = self.extract_data(connection)
            
            # 3. Processar e carregar
            stats = self.processar_dados(data, historical_map)
            
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
    
    def processar_dados(self, data, historical_map):
        """Processa e carrega dados no PostgreSQL."""
        stats = {'criados': 0, 'atualizados': 0, 'erros': 0}
        
        for row in tqdm(data, desc="Processando dados"):
            try:
                # Resolver contabilidade
                contabilidade = self.get_contabilidade_for_date(
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

### 2. Resolução de Multitenancy

```python
def get_contabilidade_for_date(self, historical_map, codi_emp, event_date):
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

### 3. Processamento em Lotes

```python
def processar_dados(self, data, historical_map):
    """Processamento em lotes para performance."""
    BATCH_SIZE = 1000
    stats = {'criados': 0, 'atualizados': 0, 'erros': 0}
    
    for i in range(0, len(data), BATCH_SIZE):
        batch = data[i:i + BATCH_SIZE]
        
        with transaction.atomic():
            for row in batch:
                # Processar registro
                pass
```

## 🔍 Validações e Regras

### 1. Regras de Multitenancy

- **CNPJ/CPF como Identificador Universal**: Sempre usar documento limpo
- **Resolução por Data**: Contabilidade ativa na data do evento
- **Isolamento Total**: Impossível vazamento entre contabilidades

### 2. Regras de Idempotência

- **Chaves Únicas**: `(contabilidade, id_legado)` ou similar
- **update_or_create**: Sempre usar para evitar duplicação
- **Validação de Dados**: Verificar integridade antes de salvar

### 3. Regras de Performance

- **Processamento em Lotes**: Máximo 1000 registros por lote
- **Transações Atômicas**: Rollback automático em caso de erro
- **Logs Detalhados**: Rastreamento de progresso e erros

## 🐛 Debugging e Troubleshooting

### 1. Logs de Debug

```python
# Adicionar logs detalhados
self.stdout.write(f"Processando registro: {row['id']}")
self.stdout.write(f"Contabilidade encontrada: {contabilidade.razao_social}")
```

### 2. Validação de Dados

```python
def validar_dados(self, row):
    """Valida dados antes do processamento."""
    if not row.get('campo_obrigatorio'):
        raise ValueError("Campo obrigatório ausente")
    
    if not self.validar_documento(row.get('cnpj')):
        raise ValueError("CNPJ inválido")
```

### 3. Tratamento de Erros

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

### 1. Estatísticas de Execução

```python
def print_stats(self, stats):
    """Imprime estatísticas de execução."""
    self.stdout.write(self.style.SUCCESS('--- Resumo da Execução ---'))
    self.stdout.write(f"  - Registros Criados: {stats['criados']}")
    self.stdout.write(f"  - Registros Atualizados: {stats['atualizados']}")
    self.stdout.write(f"  - Erros: {stats['erros']}")
```

### 2. Validação Pós-Execução

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

### 1. Queries Otimizadas

```python
# Usar select_related para evitar N+1 queries
contratos = Contrato.objects.select_related('contabilidade', 'content_type')

# Usar prefetch_related para relacionamentos many-to-many
pessoas = PessoaJuridica.objects.prefetch_related('cnaes_secundarios')
```

### 2. Cache de Dados

```python
def build_cache_map(self):
    """Constrói mapa em memória para performance."""
    cache = {}
    for obj in MeuModelo.objects.all():
        cache[obj.id_legado] = obj
    return cache
```

### 3. Processamento Paralelo

```python
from concurrent.futures import ThreadPoolExecutor

def processar_paralelo(self, data):
    """Processamento paralelo para grandes volumes."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(self.processar_lote, lote) for lote in lotes]
        results = [future.result() for future in futures]
```

## 📚 Referências

- [Django Management Commands](https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/)
- [PostgreSQL Performance](https://www.postgresql.org/docs/current/performance-tips.html)
- [PyODBC Documentation](https://github.com/mkleehammer/pyodbc)
- [Django Transactions](https://docs.djangoproject.com/en/4.2/topics/db/transactions/)
