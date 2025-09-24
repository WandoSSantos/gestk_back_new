# Guia de Normalização e Regras de Organização - GESTK

## 🎯 Visão Geral

Este documento estabelece as regras rigorosas de normalização de dados e organização do código no projeto GESTK, garantindo consistência, manutenibilidade e performance.

## 📊 Normalização de Dados

### **3ª Forma Normal (3NF) - Obrigatória**

O GESTK segue rigorosamente a **3ª Forma Normal** para eliminar redundância e garantir integridade dos dados.

#### **Regras da 3NF:**
1. **1NF**: Todos os valores são atômicos (não divisíveis)
2. **2NF**: Dependência funcional completa (sem dependências parciais)
3. **3NF**: Sem dependências transitivas (atributos não-chave dependem apenas da chave primária)

### **Exemplos de Normalização Correta**

#### **✅ CORRETO - Modelo Normalizado**

```python
class PessoaJuridica(models.Model):
    """Pessoa jurídica normalizada."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.CASCADE)
    cnpj = models.CharField(max_length=14, unique=True)
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)
    # Dados de endereço normalizados
    endereco = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    cep = models.CharField(max_length=9, blank=True)
    
    class Meta:
        unique_together = ('contabilidade', 'cnpj')
        indexes = [
            models.Index(fields=['contabilidade', 'cnpj']),
            models.Index(fields=['cnpj']),
        ]

class QuadroSocietario(models.Model):
    """Quadro societário normalizado com relacionamentos."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(PessoaJuridica, on_delete=models.CASCADE)
    socio = models.ForeignKey('pessoas.PessoaFisica', on_delete=models.CASCADE)  # Relacionamento direto
    participacao_percentual = models.DecimalField(max_digits=5, decimal_places=2)
    quantidade_quotas = models.IntegerField()
    
    class Meta:
        unique_together = ('empresa', 'socio')
```

#### **❌ INCORRETO - Modelo Não Normalizado**

```python
# NUNCA FAZER ISSO
class QuadroSocietario(models.Model):
    """Modelo com dados redundantes - VIOLA 3NF."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(PessoaJuridica, on_delete=models.CASCADE)
    
    # ❌ DADOS REDUNDANTES - VIOLAM 3NF
    socio_nome = models.CharField(max_length=255)  # Deveria ser ForeignKey
    socio_cpf = models.CharField(max_length=11)    # Deveria ser ForeignKey
    empresa_cnpj = models.CharField(max_length=14) # Já existe na empresa
    empresa_nome = models.CharField(max_length=255) # Já existe na empresa
    
    participacao_percentual = models.DecimalField(max_digits=5, decimal_places=2)
```

### **Regras de Normalização**

#### **1. Eliminação de Redundância**
```python
# ✅ CORRETO - Dados em um único lugar
class NotaFiscal(models.Model):
    cliente = models.ForeignKey(PessoaJuridica, on_delete=models.CASCADE)
    # Dados do cliente acessados via relacionamento

# ❌ INCORRETO - Dados duplicados
class NotaFiscal(models.Model):
    cliente = models.ForeignKey(PessoaJuridica, on_delete=models.CASCADE)
    cliente_nome = models.CharField(max_length=255)  # Redundante!
    cliente_cnpj = models.CharField(max_length=14)   # Redundante!
```

#### **2. Relacionamentos Explícitos**
```python
# ✅ CORRETO - Relacionamento direto
class LancamentoContabil(models.Model):
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.CASCADE)
    plano_conta = models.ForeignKey('contabil.PlanoConta', on_delete=models.CASCADE)
    pessoa = models.ForeignKey('pessoas.PessoaJuridica', on_delete=models.CASCADE)

# ❌ INCORRETO - IDs legados sem relacionamento
class LancamentoContabil(models.Model):
    contabilidade = models.ForeignKey('core.Contabilidade', on_delete=models.CASCADE)
    plano_conta_id_legado = models.CharField(max_length=50)  # Deveria ser ForeignKey
    pessoa_id_legado = models.CharField(max_length=50)       # Deveria ser ForeignKey
```

#### **3. Campos Calculados vs. Armazenados**
```python
# ✅ CORRETO - Campo calculado
class NotaFiscal(models.Model):
    valor_total = models.DecimalField(max_digits=15, decimal_places=2)
    
    @property
    def valor_liquido(self):
        """Calcula valor líquido baseado nos itens."""
        return sum(item.valor_total for item in self.itens.all())

# ❌ INCORRETO - Campo redundante
class NotaFiscal(models.Model):
    valor_total = models.DecimalField(max_digits=15, decimal_places=2)
    valor_liquido = models.DecimalField(max_digits=15, decimal_places=2)  # Redundante!
```

## 🏗️ Regras de Organização do Código

### **1. Estrutura de Apps**

#### **Organização por Domínio**
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

#### **Regras de Apps:**
- **Um domínio por app**: Cada app representa um domínio de negócio
- **Baixo acoplamento**: Apps não devem depender diretamente uns dos outros
- **Alta coesão**: Funcionalidades relacionadas ficam no mesmo app

### **2. Estrutura de Arquivos**

#### **Estrutura Padrão por App**
```
app_name/
├── __init__.py
├── apps.py                  # Configuração do app
├── models.py                # Modelos principais
├── models_*.py              # Modelos específicos (ex: models_etl19.py)
├── admin.py                 # Interface administrativa
├── views.py                 # Views/ViewSets
├── serializers.py           # Serializers DRF
├── services.py              # Lógica de negócio
├── utils.py                 # Utilitários específicos
├── validators.py            # Validadores customizados
├── tests.py                 # Testes
├── migrations/              # Migrações do banco
│   ├── __init__.py
│   └── *.py
└── management/              # Comandos Django
    └── commands/
        ├── __init__.py
        └── *.py
```

### **3. Convenções de Nomenclatura**

#### **Modelos**
```python
# ✅ CORRETO
class PessoaJuridica(models.Model):  # PascalCase
class QuadroSocietario(models.Model):  # PascalCase
class LancamentoContabil(models.Model):  # PascalCase

# ❌ INCORRETO
class pessoa_juridica(models.Model):  # snake_case
class QuadroSocietarioModel(models.Model):  # Sufixo desnecessário
```

#### **Campos**
```python
# ✅ CORRETO
class PessoaJuridica(models.Model):
    cnpj = models.CharField(max_length=14)  # snake_case
    razao_social = models.CharField(max_length=255)  # snake_case
    data_criacao = models.DateTimeField(auto_now_add=True)  # snake_case

# ❌ INCORRETO
class PessoaJuridica(models.Model):
    CNPJ = models.CharField(max_length=14)  # UPPER_CASE
    razaoSocial = models.CharField(max_length=255)  # camelCase
    DataCriacao = models.DateTimeField(auto_now_add=True)  # PascalCase
```

#### **Métodos e Funções**
```python
# ✅ CORRETO
def buscar_pessoa_por_cnpj(self, cnpj):  # snake_case
def calcular_valor_total(self):  # snake_case
def validar_documento(self, documento):  # snake_case

# ❌ INCORRETO
def buscarPessoaPorCnpj(self, cnpj):  # camelCase
def CalcularValorTotal(self):  # PascalCase
def validarDocumento(self, documento):  # camelCase
```

### **4. Padrões de Modelos**

#### **Estrutura Padrão de Modelo**
```python
class MeuModelo(models.Model):
    """Docstring descritiva do modelo."""
    
    # 1. Chave primária (sempre primeiro)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # 2. ForeignKey para contabilidade (obrigatório)
    contabilidade = models.ForeignKey(
        'core.Contabilidade',
        on_delete=models.CASCADE,
        db_index=True,
        help_text="Contabilidade responsável pelos dados"
    )
    
    # 3. Campos de negócio (em ordem lógica)
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    
    # 4. Campos de relacionamento
    categoria = models.ForeignKey('outro_app.Categoria', on_delete=models.PROTECT)
    
    # 5. Campos de auditoria (sempre no final)
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_criados'
    )
    atualizado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_atualizados'
    )
    
    # 6. Auditoria automática
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = 'Meu Modelo'
        verbose_name_plural = 'Meus Modelos'
        db_table = 'app_meu_modelo'
        unique_together = ('contabilidade', 'nome')
        indexes = [
            models.Index(fields=['contabilidade', 'ativo']),
            models.Index(fields=['nome']),
        ]
        ordering = ['nome']
    
    def __str__(self):
        return f"{self.nome} ({self.contabilidade.razao_social})"
    
    def clean(self):
        """Validações de negócio."""
        super().clean()
        if not self.nome:
            raise ValidationError("Nome é obrigatório")
```

### **5. Padrões de ETL**

#### **Estrutura Padrão de ETL**
```python
from ._base import BaseETLCommand
from django.db import transaction
from tqdm import tqdm

class Command(BaseETLCommand):
    help = 'Descrição clara do ETL'
    
    def add_arguments(self, parser):
        """Argumentos do comando."""
        parser.add_argument('--dry-run', action='store_true', help='Modo de teste')
        parser.add_argument('--limit', type=int, help='Limitar registros')
        parser.add_argument('--batch-size', type=int, default=1000, help='Tamanho do lote')
    
    def handle(self, *args, **options):
        """Ponto de entrada principal."""
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

### **6. Padrões de API**

#### **ViewSet Padrão**
```python
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

class MeuModeloViewSet(viewsets.ModelViewSet):
    """ViewSet para MeuModelo."""
    
    serializer_class = MeuModeloSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['ativo', 'categoria']
    search_fields = ['nome', 'descricao']
    ordering_fields = ['nome', 'data_criacao']
    ordering = ['nome']
    
    def get_queryset(self):
        """Filtra por contabilidade do usuário."""
        return MeuModelo.objects.filter(
            contabilidade=self.request.user.contabilidade
        )
    
    def perform_create(self, serializer):
        """Define contabilidade automaticamente."""
        serializer.save(contabilidade=self.request.user.contabilidade)
    
    @action(detail=True, methods=['post'])
    def acao_customizada(self, request, pk=None):
        """Ação customizada do endpoint."""
        obj = self.get_object()
        # Implementação da ação
        return Response({'status': 'success'})
```

#### **Serializer Padrão**
```python
class MeuModeloSerializer(serializers.ModelSerializer):
    """Serializer para MeuModelo."""
    
    contabilidade_nome = serializers.CharField(
        source='contabilidade.razao_social',
        read_only=True
    )
    
    class Meta:
        model = MeuModelo
        fields = [
            'id', 'contabilidade', 'contabilidade_nome',
            'nome', 'descricao', 'ativo', 'categoria',
            'data_criacao', 'data_atualizacao'
        ]
        read_only_fields = ['id', 'contabilidade', 'data_criacao', 'data_atualizacao']
    
    def validate(self, data):
        """Validações customizadas."""
        if not data.get('nome'):
            raise serializers.ValidationError("Nome é obrigatório")
        return data
```

## 🔒 Regras de Multitenancy

### **1. Isolamento Obrigatório**

#### **Nível de Modelo**
```python
# ✅ CORRETO - Sempre incluir contabilidade
class MeuModelo(models.Model):
    contabilidade = models.ForeignKey(
        'core.Contabilidade',
        on_delete=models.CASCADE,
        db_index=True
    )
    # ... outros campos

# ❌ INCORRETO - Sem isolamento
class MeuModelo(models.Model):
    nome = models.CharField(max_length=255)
    # Sem contabilidade - VIOLA multitenancy
```

#### **Nível de Query**
```python
# ✅ CORRETO - Sempre filtrar por contabilidade
def get_queryset(self):
    return MeuModelo.objects.filter(
        contabilidade=self.request.user.contabilidade
    )

# ❌ INCORRETO - Vaza dados de outras contabilidades
def get_queryset(self):
    return MeuModelo.objects.all()  # PERIGOSO!
```

### **2. Validação de Permissões**

```python
def clean(self):
    """Validação de isolamento multitenant."""
    super().clean()
    
    if not self.contabilidade:
        raise ValidationError("Contabilidade é obrigatória")
    
    # Verificar se o usuário tem acesso à contabilidade
    if hasattr(self, 'user') and self.user.contabilidade != self.contabilidade:
        raise ValidationError("Acesso negado à contabilidade")
```

## 📊 Regras de Performance

### **1. Índices Otimizados**

```python
class Meta:
    indexes = [
        # Índice composto para consultas multitenant
        models.Index(fields=['contabilidade', 'ativo']),
        # Índice para busca por nome
        models.Index(fields=['nome']),
        # Índice para ordenação
        models.Index(fields=['data_criacao']),
    ]
```

### **2. Queries Otimizadas**

```python
# ✅ CORRETO - select_related para evitar N+1
pessoas = PessoaJuridica.objects.select_related('contabilidade')

# ✅ CORRETO - prefetch_related para many-to-many
pessoas = PessoaJuridica.objects.prefetch_related('cnaes_secundarios')

# ❌ INCORRETO - N+1 queries
for pessoa in PessoaJuridica.objects.all():
    print(pessoa.contabilidade.razao_social)  # N+1 query!
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

## 🧪 Regras de Testes

### **1. Estrutura de Testes**

```python
class MeuModeloTestCase(TestCase):
    def setUp(self):
        """Setup para testes."""
        self.contabilidade = Contabilidade.objects.create(
            razao_social="Teste Contabilidade",
            cnpj="12345678000199"
        )
        self.user = get_user_model().objects.create_user(
            username="teste",
            contabilidade=self.contabilidade
        )
    
    def test_criacao_modelo(self):
        """Testa criação de modelo."""
        modelo = MeuModelo.objects.create(
            contabilidade=self.contabilidade,
            nome="Teste"
        )
        self.assertEqual(modelo.nome, "Teste")
        self.assertEqual(modelo.contabilidade, self.contabilidade)
    
    def test_isolamento_multitenant(self):
        """Testa isolamento entre contabilidades."""
        contabilidade2 = Contabilidade.objects.create(
            razao_social="Contabilidade 2",
            cnpj="98765432000188"
        )
        
        # Criar modelo para contabilidade1
        modelo1 = MeuModelo.objects.create(
            contabilidade=self.contabilidade,
            nome="Modelo 1"
        )
        
        # Verificar que contabilidade2 não vê o modelo
        self.assertEqual(
            MeuModelo.objects.filter(contabilidade=contabilidade2).count(),
            0
        )
```

### **2. Testes de ETL**

```python
class ETLTestCase(TestCase):
    def test_etl_multitenant(self):
        """Testa isolamento em ETL."""
        # Criar duas contabilidades
        cont1 = Contabilidade.objects.create(...)
        cont2 = Contabilidade.objects.create(...)
        
        # Executar ETL
        call_command('etl_teste')
        
        # Verificar isolamento
        self.assertEqual(MeuModelo.objects.filter(contabilidade=cont1).count(), 1)
        self.assertEqual(MeuModelo.objects.filter(contabilidade=cont2).count(), 1)
```

## 📝 Regras de Documentação

### **1. Docstrings**

```python
def meu_metodo(self, parametro1, parametro2=None):
    """
    Descrição breve do método.
    
    Args:
        parametro1 (str): Descrição do parâmetro
        parametro2 (int, optional): Descrição opcional
        
    Returns:
        bool: Descrição do retorno
        
    Raises:
        ValidationError: Quando o parâmetro é inválido
        
    Example:
        >>> obj.meu_metodo("teste", 123)
        True
    """
    pass
```

### **2. Comentários**

```python
# ✅ CORRETO - Comentários úteis
def processar_dados(self, data, historical_map):
    """Processa dados do ETL."""
    # Construir cache de contabilidades para performance
    contabilidade_cache = {}
    for cont in Contabilidade.objects.all():
        contabilidade_cache[cont.id_legado] = cont
    
    # Processar cada registro
    for row in data:
        # Resolver contabilidade usando regra de ouro
        contabilidade = self.get_contabilidade_for_date_optimized(
            historical_map, row['codi_emp'], row['data_evento']
        )

# ❌ INCORRETO - Comentários óbvios
def processar_dados(self, data, historical_map):
    # Incrementar contador
    contador += 1
    # Retornar resultado
    return resultado
```

## 🚀 Regras de Deploy

### **1. Variáveis de Ambiente**

```bash
# .env
DEBUG=False
SECRET_KEY=chave-super-secreta
DATABASE_URL=postgresql://user:pass@localhost/gestk
REDIS_URL=redis://localhost:6379/0
SYBASE_DRIVER=SQL Anywhere 17
SYBASE_SERVER=servidor_sybase
```

### **2. Configuração por Ambiente**

```python
# settings/base.py
class BaseSettings:
    # Configurações comuns

# settings/development.py
class DevelopmentSettings(BaseSettings):
    DEBUG = True
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console'],
                'level': 'DEBUG',
            },
        },
    }

# settings/production.py
class ProductionSettings(BaseSettings):
    DEBUG = False
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'file': {
                'class': 'logging.FileHandler',
                'filename': '/var/log/gestk/django.log',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['file'],
                'level': 'INFO',
            },
        },
    }
```

## 📚 Checklist de Conformidade

### **Antes de Commitar:**

- [ ] Modelos seguem 3NF
- [ ] Campos de contabilidade obrigatórios
- [ ] Índices otimizados
- [ ] Testes de multitenancy
- [ ] Docstrings completas
- [ ] Código segue PEP 8
- [ ] ETLs são idempotentes
- [ ] Queries otimizadas
- [ ] Validações de segurança

### **Antes de Deploy:**

- [ ] Testes passando
- [ ] Migrações aplicadas
- [ ] Variáveis de ambiente configuradas
- [ ] Logs configurados
- [ ] Backup realizado
- [ ] Monitoramento ativo

---

**Última atualização:** 24/09/2025  
**Versão:** 2.0  
**Status:** Regras Estabelecidas
