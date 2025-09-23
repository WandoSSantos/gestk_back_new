# ETL de Notas Fiscais - Solução Implementada

## 🎯 Problemas Resolvidos

### 1. **Identificação Correta da Contabilidade**
- **ANTES**: Usava `codi_emp` (código da empresa) para identificar contabilidade
- **AGORA**: Usa **CNPJ/CPF do parceiro** para buscar na tabela `Contrato` onde ele é cliente
- **LÓGICA**: `CNPJ/CPF → Buscar Pessoa → Buscar Contrato → Encontrar Contabilidade`

### 2. **Cadastro de Pessoas com Unicidade**
- **Verificação por CNPJ/CPF** em todas as contabilidades
- **Criação automática** se não existir
- **Evita duplicação** usando `update_or_create`
- **Mantém consistência** entre PessoaJuridica/PessoaFisica e ParceiroNegocio

### 3. **Tratamento de CFOP de Serviços**
- **CFOP 1933 e 2933**: Identificados como serviços
- **Itens de serviços**: Não recebem CFOP (campo `cfop = None`)
- **Itens de produtos**: Recebem CFOP do item ou da nota

### 4. **Multitenancy Correto**
- **Isolamento por contabilidade**: Cada nota fiscal pertence à contabilidade correta
- **Parceiros únicos por contabilidade**: Mesmo CNPJ pode ser cliente em contabilidades diferentes
- **Contexto preservado**: Fornecedor vs Cliente mantido por contabilidade

## 🔄 Fluxo de Processamento

```
1. Receber dados da nota fiscal (Sybase)
   ↓
2. Extrair CNPJ/CPF do parceiro
   ↓
3. Buscar pessoa existente no sistema
   ↓
4. Buscar contrato onde pessoa é cliente
   ↓
5. Identificar contabilidade do contrato
   ↓
6. Criar/atualizar pessoa na contabilidade correta
   ↓
7. Criar/atualizar ParceiroNegocio
   ↓
8. Criar/atualizar NotaFiscal
   ↓
9. Criar itens (com CFOP correto para serviços)
```

## 📊 Estrutura de Dados

### **NotaFiscal**
- `chave_acesso`: Chave única da NFe
- `contabilidade`: Contabilidade onde o parceiro é cliente
- `parceiro_negocio`: Parceiro identificado pelo CNPJ/CPF
- `tipo_nota`: ENTRADA ou SAIDA
- `cfop`: CFOP da nota (1933/2933 para serviços)

### **NotaFiscalItem**
- `nota_fiscal`: Referência à nota
- `cfop`: CFOP do item (None para serviços)
- `produto`: Dados do produto/serviço
- `valores`: Valores fiscais e tributários

### **ParceiroNegocio**
- `contabilidade`: Contabilidade onde é cliente
- `pessoa_juridica` ou `pessoa_fisica`: Pessoa associada
- `tipo_inscricao`: Tipo de inscrição

## 🛡️ Garantias de Qualidade

### **Idempotência**
- `update_or_create` para todas as entidades
- Execução múltipla sem duplicação
- Atualização de dados existentes

### **Unicidade**
- CNPJ/CPF como chave única para pessoas
- Chave da NFe como chave única para notas
- Isolamento por contabilidade

### **Integridade**
- Transações atômicas por lote
- Validação de documentos (CNPJ/CPF)
- Tratamento de erros com rollback

## 🚀 Benefícios da Solução

1. **Escalabilidade**: Suporta centenas de bancos de dados
2. **Flexibilidade**: Mesma empresa pode ser fornecedor/cliente
3. **Consistência**: Dados únicos e não duplicados
4. **Auditabilidade**: Rastreamento completo de alterações
5. **Performance**: Cache de entidades e processamento em lotes
6. **Confiabilidade**: Tratamento robusto de erros

## 📝 Exemplo de Uso

```python
# Executar ETL de teste
python manage.py etl_07_notas_fiscais_test

# Executar ETL completo
python manage.py etl_07_notas_fiscais
```

## 🔍 Validações Implementadas

- **Documentos válidos**: CNPJ (14 dígitos) ou CPF (11 dígitos)
- **Contabilidade existente**: Parceiro deve ser cliente de alguma contabilidade
- **CFOP de serviços**: Tratamento especial para 1933/2933
- **Dados obrigatórios**: Chave da NFe, valores, etc.

## 📈 Estatísticas de Processamento

- **Notas processadas**: Criadas e atualizadas
- **Itens criados**: Produtos e serviços
- **Parceiros processados**: Pessoas criadas/atualizadas
- **Lotes processados**: Controle de progresso
- **Erros tratados**: Logs detalhados

Esta solução atende aos padrões internacionais de arquitetura e engenharia de dados, garantindo escalabilidade, confiabilidade e manutenibilidade do sistema.

