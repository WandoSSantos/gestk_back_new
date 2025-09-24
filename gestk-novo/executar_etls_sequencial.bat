@echo off
REM Script para Execução Sequencial dos ETLs - GESTK (Windows)
REM 
REM Este script executa todos os ETLs na ordem correta para Windows
REM 
REM Uso:
REM     executar_etls_sequencial.bat [opções]
REM 
REM Opções:
REM     --dry-run          Executa em modo de teste (não salva no banco)
REM     --etl-inicial N    Inicia a partir do ETL N
REM     --etl-final N      Para no ETL N
REM     --skip-etls LIST   Pula ETLs específicos (ex: --skip-etls 05,06,07)
REM     --batch-size N     Tamanho do lote para ETLs que suportam
REM     --progress-interval N  Intervalo de progresso para ETLs que suportam

echo.
echo ======================================================================
echo                    EXECUCAO SEQUENCIAL DE ETLs - GESTK
echo ======================================================================
echo.

REM Verificar se o ambiente virtual está ativo
if not defined VIRTUAL_ENV (
    echo Ativando ambiente virtual...
    call venv\Scripts\activate.bat
)

REM Executar script Python
python executar_etls_sequencial.py %*

echo.
echo ======================================================================
echo                    EXECUCAO CONCLUIDA
echo ======================================================================
echo.
pause
