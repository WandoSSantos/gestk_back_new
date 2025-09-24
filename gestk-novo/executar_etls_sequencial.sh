#!/bin/bash
# Script para Execução Sequencial dos ETLs - GESTK (Linux/Mac)
# 
# Este script executa todos os ETLs na ordem correta para Linux/Mac
# 
# Uso:
#     ./executar_etls_sequencial.sh [opções]
# 
# Opções:
#     --dry-run          Executa em modo de teste (não salva no banco)
#     --etl-inicial N    Inicia a partir do ETL N
#     --etl-final N      Para no ETL N
#     --skip-etls LIST   Pula ETLs específicos (ex: --skip-etls 05,06,07)
#     --batch-size N     Tamanho do lote para ETLs que suportam
#     --progress-interval N  Intervalo de progresso para ETLs que suportam

echo ""
echo "======================================================================"
echo "                    EXECUCAO SEQUENCIAL DE ETLs - GESTK"
echo "======================================================================"
echo ""

# Verificar se o ambiente virtual está ativo
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Ativando ambiente virtual..."
    source venv/bin/activate
fi

# Executar script Python
python executar_etls_sequencial.py "$@"

echo ""
echo "======================================================================"
echo "                    EXECUCAO CONCLUIDA"
echo "======================================================================"
echo ""
