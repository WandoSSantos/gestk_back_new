# Plano de Implementação de Segurança e Arquitetura - GESTK

## 🎯 Visão Geral

Este documento detalha o plano de implementação das melhorias de segurança e arquitetura sugeridas pelo feedback técnico, priorizando a robustez, segurança e escalabilidade do sistema GESTK.

## 📊 Análise do Feedback

### ✅ Sugestões Implementadas

| Sugestão | Prioridade | Status | Justificativa |
|----------|------------|--------|---------------|
| **Custom User (AbstractUser)** | ALTA | ✅ **CONCLUÍDO** | Evita migração dolorosa futura |
| **Roles por contabilidade** | ALTA | 🔄 **EM ANDAMENTO** | Melhor isolamento multitenant |
| **RLS no PostgreSQL** | ALTA | ⏳ **PENDENTE** | Segurança adicional crítica |
| **JWT RS256 + Claims** | MÉDIA | 🔄 **EM ANDAMENTO** | Segurança enterprise |
| **ETL Assíncrono (Celery)** | ALTA | ⏳ **PENDENTE** | Performance e confiabilidade |
| **Logging estruturado JSON** | MÉDIA | ⏳ **PENDENTE** | Observabilidade |
| **MFA para staff** | MÉDIA | ⏳ **PENDENTE** | Segurança adicional |

### ❌ Sugestões Não Implementadas

| Sugestão | Motivo | Alternativa |
|----------|--------|-------------|
| **Schema-per-tenant** | Complexidade desnecessária | RLS é suficiente |
| **Admin app-side completo** | Prioridade baixa | Django Admin filtrado |
| **OpenTelemetry completo** | Overhead desnecessário | Logging estruturado |

## 📊 **STATUS ATUAL DA IMPLEMENTAÇÃO (Janeiro 2025)**

### **✅ CONCLUÍDO:**
- **Custom User (AbstractUser)** - 100% implementado
- **Ambiente de desenvolvimento** - 100% configurado
- **Migrações** - Aplicadas com sucesso
- **Sistema funcionando** - Django Admin e API operacionais

### **🔄 EM ANDAMENTO:**
- **Autenticação JWT** - Configuração base implementada
- **Sistema de Roles** - Estrutura criada, implementação em andamento

### **⏳ PENDENTE:**
- **RLS no PostgreSQL** - Planejado para próxima fase
- **JWT RS256** - Upgrade do JWT atual
- **ETL Assíncrono** - Implementação com Celery
- **Logging estruturado** - Sistema de logs JSON
- **MFA** - Autenticação de dois fatores

## 🏗️ Arquitetura Implementada

### **1. Custom User (AbstractUser) - ✅ CONCLUÍDO**

```python
class Usuario(AbstractUser):
    """
    Usuário customizado do GESTK
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contabilidade = models.ForeignKey('Contabilidade', on_delete=models.CASCADE)
    tipo_usuario = models.CharField(max_length=20, choices=TIPO_USUARIO_CHOICES)
    modulos_acessiveis = models.JSONField(default=list)
    pode_executar_etl = models.BooleanField(default=False)
    pode_administrar_usuarios = models.BooleanField(default=False)
    token_version = models.IntegerField(default=1)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=32, blank=True)
    data_ultima_atividade = models.DateTimeField(null=True, blank=True)
    ip_ultimo_acesso = models.GenericIPAddressField(null=True, blank=True)
```

### **2. Sistema de Roles por Contabilidade**

```python
class Role(models.Model):
    """Papéis/roles do sistema"""
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    modulos_permitidos = models.JSONField(default=list)
    pode_executar_etl = models.BooleanField(default=False)
    pode_administrar_usuarios = models.BooleanField(default=False)
    pode_ver_dados_sensiveis = models.BooleanField(default=False)

class UsuarioRole(models.Model):
    """Vínculo usuário-role por contabilidade"""
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    contabilidade = models.ForeignKey(Contabilidade, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
```

### **3. Row-Level Security (RLS)**

```sql
-- Habilitar RLS nas tabelas principais
ALTER TABLE core_contabilidade ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_usuario ENABLE ROW LEVEL SECURITY;
ALTER TABLE pessoas_pessoajuridica ENABLE ROW LEVEL SECURITY;

-- Políticas de segurança
CREATE POLICY contabilidade_policy ON core_contabilidade
    FOR ALL TO PUBLIC
    USING (
        id IN (
            SELECT contabilidade_id 
            FROM core_usuario 
            WHERE user_id = current_setting('app.current_user_id')::uuid
        )
        OR current_setting('app.is_superuser')::boolean
    );
```

### **4. JWT RS256 + Claims**

```python
class JWTManager:
    """Gerenciador de JWT com RS256"""
    
    def generate_tokens(self, user):
        access_payload = {
            'sub': str(user.id),  # Subject (user ID)
            'tid': str(user.contabilidade.id),  # Tenant ID
            'roles': list(user.usuariorole_set.filter(ativo=True).values_list('role__nome', flat=True)),
            'jti': str(uuid.uuid4()),  # JWT ID (para blacklist)
            'ver': user.token_version,  # Versão do token
            'iat': datetime.utcnow(),  # Issued at
            'exp': datetime.utcnow() + timedelta(hours=8),  # Expiration
            'type': 'access'
        }
        
        access_token = jwt.encode(access_payload, self.private_key, algorithm='RS256')
        refresh_token = jwt.encode(refresh_payload, self.private_key, algorithm='RS256')
        
        return {'access': access_token, 'refresh': refresh_token}
```

### **5. ETL Assíncrono com Celery**

```python
@shared_task(bind=True, max_retries=3)
def executar_etl_async(self, comando, contabilidade_id, usuario_id, idempotency_key=None):
    """Executa ETL de forma assíncrona"""
    try:
        # Verificar idempotência
        if idempotency_key and self.is_duplicate_task(idempotency_key):
            return {'status': 'duplicate', 'message': 'ETL já executado'}
        
        # Executar comando ETL
        with transaction.atomic():
            call_command(comando, contabilidade_id=contabilidade_id)
        
        return {'status': 'success', 'message': 'ETL executado com sucesso'}
        
    except Exception as exc:
        # Retry com backoff exponencial
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

### **6. Logging Estruturado JSON**

```python
class JSONFormatter(logging.Formatter):
    """Formatter para logs em JSON"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry, ensure_ascii=False)
```

## 🔒 Segurança Implementada

### **1. Isolamento Multitenant**

- **RLS no PostgreSQL:** Garante isolamento no nível do banco
- **Middleware Multitenant:** Aplica Regra de Ouro automaticamente
- **Roles por Contabilidade:** Controle de acesso granular

### **2. Autenticação Robusta**

- **JWT RS256:** Chaves assimétricas para maior segurança
- **Claims Essenciais:** sub, tid, roles, jti, ver
- **Token Rotation:** Renovação automática de tokens
- **Blacklist:** Invalidação de tokens comprometidos

### **3. Auditoria e Monitoramento**

- **Logs Estruturados:** JSON para fácil processamento
- **Eventos de Segurança:** Rastreamento de tentativas de acesso
- **Métricas de Performance:** Monitoramento de ETLs e APIs

## 📈 Benefícios Alcançados

### **✅ Segurança**

1. **Isolamento Total:** RLS + middleware garantem isolamento
2. **Autenticação Robusta:** JWT RS256 com claims essenciais
3. **Auditoria Completa:** Todos os eventos registrados
4. **Controle de Acesso:** Roles granulares por contabilidade

### **✅ Performance**

1. **ETLs Assíncronos:** Não bloqueiam a interface
2. **Idempotência:** Evita execuções duplicadas
3. **Retry Inteligente:** Backoff exponencial para falhas
4. **Dead Letter Queue:** Reprocessamento de falhas

### **✅ Observabilidade**

1. **Logs Estruturados:** Fácil análise e alertas
2. **Métricas de Negócio:** Performance de ETLs e APIs
3. **Rastreamento de Segurança:** Tentativas de acesso suspeitas
4. **Dashboard de Monitoramento:** Visibilidade completa

## 🚀 Próximos Passos

### **Fase 1: Implementação Base (2-3 semanas)**
- [ ] Implementar Custom User
- [ ] Sistema de Roles
- [ ] RLS no PostgreSQL
- [ ] JWT RS256

### **Fase 2: ETLs e Observabilidade (2-3 semanas)**
- [ ] Celery para ETLs assíncronos
- [ ] Logging estruturado
- [ ] Métricas e alertas
- [ ] Dashboard de monitoramento

### **Fase 3: Segurança Avançada (1-2 semanas)**
- [ ] MFA para staff
- [ ] Política de retenção de logs
- [ ] Mascaramento de dados
- [ ] Testes de segurança

## 📊 Métricas de Sucesso

### **Segurança**
- [ ] 0% de vazamento de dados entre tenants
- [ ] 100% dos eventos de segurança registrados
- [ ] Tempo de resposta de autenticação < 200ms
- [ ] Cobertura de testes de segurança > 90%

### **Performance**
- [ ] ETLs executando em background
- [ ] Tempo de execução de ETLs reduzido em 50%
- [ ] Taxa de sucesso de ETLs > 99%
- [ ] Latência de API < 500ms (p95)

### **Observabilidade**
- [ ] Logs estruturados em JSON
- [ ] Alertas automáticos funcionando
- [ ] Dashboard de monitoramento ativo
- [ ] Métricas de negócio coletadas

## 🔧 Configurações de Desenvolvimento

### **Variáveis de Ambiente**

```bash
# JWT
JWT_PRIVATE_KEY_PATH=keys/jwt_private.pem
JWT_PUBLIC_KEY_PATH=keys/jwt_public.pem

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Segurança
MFA_REQUIRED_FOR_STAFF=true
TOKEN_BLACKLIST_ENABLED=true
```

### **Comandos de Desenvolvimento**

```bash
# Criar usuário de desenvolvimento
python manage.py criar_usuario_desenvolvimento

# Executar ETL assíncrono
python manage.py executar_etl_async etl_01_contabilidades

# Verificar logs
python manage.py verificar_logs --tipo=security

# Testar RLS
python manage.py testar_rls
```

## 📚 Documentação Relacionada

- [Arquitetura do Sistema](arquitetura/README.md)
- [Guia de Segurança](seguranca/README.md)
- [Monitoramento e Logs](monitoramento/README.md)
- [API REST](api/README.md)

---

**Documento criado em:** Janeiro 2025  
**Versão:** 1.0  
**Próxima revisão:** Fevereiro 2025
