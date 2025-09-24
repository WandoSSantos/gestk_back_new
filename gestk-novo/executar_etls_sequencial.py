#!/usr/bin/env python
"""
Script para Execução Sequencial dos ETLs - GESTK

Este script executa todos os ETLs na ordem correta, garantindo que as dependências
sejam respeitadas e que o processo seja idempotente.

Uso:
    python executar_etls_sequencial.py [opções]

Opções:
    --dry-run          Executa em modo de teste (não salva no banco)
    --etl-inicial N    Inicia a partir do ETL N
    --etl-final N      Para no ETL N
    --skip-etls LIST   Pula ETLs específicos (ex: --skip-etls 05,06,07)
    --batch-size N     Tamanho do lote para ETLs que suportam
    --progress-interval N  Intervalo de progresso para ETLs que suportam
    --help             Exibe esta ajuda
"""

import os
import sys
import subprocess
import argparse
import time
from datetime import datetime

# Configuração do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestk.settings')
import django
django.setup()

class ETLSequencialExecutor:
    """Executor sequencial de ETLs com controle de dependências"""
    
    def __init__(self):
        self.etls_sequence = [
            # ETLs Base (executar primeiro)
            {
                'numero': '00',
                'nome': 'mapeamento_empresas',
                'descricao': 'Mapeamento Completo de Empresas',
                'dependencias': [],
                'critico': True,
                'comando': 'etl_00_mapeamento_empresas'
            },
            {
                'numero': '01',
                'nome': 'contabilidades',
                'descricao': 'Contabilidades (Tenants)',
                'dependencias': [],
                'critico': True,
                'comando': 'etl_01_contabilidades'
            },
            {
                'numero': '02',
                'nome': 'cnaes',
                'descricao': 'CNAEs',
                'dependencias': [],
                'critico': True,
                'comando': 'etl_02_cnaes'
            },
            {
                'numero': '04',
                'nome': 'contratos',
                'descricao': 'Contratos, Pessoas Físicas e Jurídicas',
                'dependencias': ['01'],
                'critico': True,
                'comando': 'etl_04_contratos'
            },
            {
                'numero': '21',
                'nome': 'quadro_societario',
                'descricao': 'Quadro Societário',
                'dependencias': ['04'],
                'critico': False,
                'comando': 'etl_21_quadro_societario'
            },
            
            # ETLs Contábeis
            {
                'numero': '05',
                'nome': 'plano_contas',
                'descricao': 'Plano de Contas',
                'dependencias': ['01'],
                'critico': False,
                'comando': 'etl_05_plano_contas'
            },
            {
                'numero': '06',
                'nome': 'lancamentos',
                'descricao': 'Lançamentos Contábeis',
                'dependencias': ['05'],
                'critico': False,
                'comando': 'etl_06_lancamentos'
            },
            
            # ETLs Fiscais
            {
                'numero': '07',
                'nome': 'notas_fiscais',
                'descricao': 'Notas Fiscais (entrada/saída/serviços)',
                'dependencias': ['04'],
                'critico': False,
                'comando': 'etl_07_notas_fiscais'
            },
            {
                'numero': '17',
                'nome': 'cupons_fiscais',
                'descricao': 'Cupons Fiscais Eletrônicos',
                'dependencias': ['04'],
                'critico': False,
                'comando': 'etl_17_cupons_fiscais'
            },
            
            # ETLs de RH
            {
                'numero': '08',
                'nome': 'rh_cargos',
                'descricao': 'Cargos',
                'dependencias': ['04'],
                'critico': False,
                'comando': 'etl_08_rh_cargos'
            },
            {
                'numero': '09',
                'nome': 'rh_departamentos',
                'descricao': 'Departamentos',
                'dependencias': ['04'],
                'critico': False,
                'comando': 'etl_09_rh_departamentos'
            },
            {
                'numero': '10',
                'nome': 'rh_centros_custo',
                'descricao': 'Centros de Custo',
                'dependencias': ['04'],
                'critico': False,
                'comando': 'etl_10_rh_centros_custo'
            },
            {
                'numero': '11',
                'nome': 'rh_funcionarios_vinculos',
                'descricao': 'Funcionários e Vínculos',
                'dependencias': ['08', '09', '10'],
                'critico': False,
                'comando': 'etl_11_rh_funcionarios_vinculos'
            },
            {
                'numero': '11b',
                'nome': 'rh_rubricas',
                'descricao': 'Rubricas de RH',
                'dependencias': ['11'],
                'critico': False,
                'comando': 'etl_11_rh_rubricas'
            },
            {
                'numero': '12',
                'nome': 'rh_historicos',
                'descricao': 'Históricos de Salário e Cargo',
                'dependencias': ['11'],
                'critico': False,
                'comando': 'etl_12_rh_historicos'
            },
            {
                'numero': '13',
                'nome': 'rh_periodos_aquisitivos',
                'descricao': 'Períodos Aquisitivos de Férias',
                'dependencias': ['11'],
                'critico': False,
                'comando': 'etl_13_rh_periodos_aquisitivos'
            },
            {
                'numero': '14',
                'nome': 'rh_gozo_ferias',
                'descricao': 'Gozo de Férias',
                'dependencias': ['13'],
                'critico': False,
                'comando': 'etl_14_rh_gozo_ferias'
            },
            {
                'numero': '15',
                'nome': 'rh_afastamentos',
                'descricao': 'Afastamentos',
                'dependencias': ['11'],
                'critico': False,
                'comando': 'etl_15_rh_afastamentos'
            },
            {
                'numero': '16',
                'nome': 'rh_rescisoes',
                'descricao': 'Rescisões',
                'dependencias': ['11'],
                'critico': False,
                'comando': 'etl_16_rh_rescisoes'
            },
            {
                'numero': '16b',
                'nome': 'rh_rescisoes_rubricas',
                'descricao': 'Rubricas de Rescisão',
                'dependencias': ['16'],
                'critico': False,
                'comando': 'etl_16_rh_rescisoes_rubricas'
            },
            
            # ETLs de Administração
            {
                'numero': '18',
                'nome': 'usuarios',
                'descricao': 'Usuários e Configurações',
                'dependencias': ['04'],
                'critico': False,
                'comando': 'etl_18_usuarios'
            },
            {
                'numero': '19',
                'nome': 'logs_unificado',
                'descricao': 'Logs de Acesso e Atividades',
                'dependencias': ['18'],
                'critico': False,
                'comando': 'etl_19_logs_unificado_corrigido'
            }
        ]
        
        self.stats = {
            'inicio': None,
            'fim': None,
            'etls_executados': 0,
            'etls_sucesso': 0,
            'etls_erro': 0,
            'etls_pulados': 0,
            'tempo_total': 0
        }
    
    def executar_etl(self, etl, dry_run=False, batch_size=None, progress_interval=None):
        """Executa um ETL específico"""
        print(f"\n{'='*70}")
        print(f"EXECUTANDO ETL {etl['numero']} - {etl['descricao']}")
        print(f"{'='*70}")
        
        # Construir comando
        comando = ['python', 'manage.py', etl['comando']]
        
        if dry_run:
            comando.append('--dry-run')
        
        if batch_size:
            comando.extend(['--batch-size', str(batch_size)])
        
        if progress_interval:
            comando.extend(['--progress-interval', str(progress_interval)])
        
        # Executar comando
        inicio_etl = time.time()
        try:
            resultado = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                check=True
            )
            
            fim_etl = time.time()
            tempo_etl = fim_etl - inicio_etl
            
            print(f"✅ ETL {etl['numero']} executado com sucesso em {tempo_etl:.2f}s")
            if resultado.stdout:
                print("Saída:", resultado.stdout[-500:])  # Últimas 500 caracteres
            
            self.stats['etls_sucesso'] += 1
            return True
            
        except subprocess.CalledProcessError as e:
            fim_etl = time.time()
            tempo_etl = fim_etl - inicio_etl
            
            print(f"❌ ERRO no ETL {etl['numero']} após {tempo_etl:.2f}s")
            print(f"Código de erro: {e.returncode}")
            if e.stdout:
                print("Saída:", e.stdout[-500:])
            if e.stderr:
                print("Erro:", e.stderr[-500:])
            
            self.stats['etls_erro'] += 1
            return False
    
    def verificar_dependencias(self, etl, etls_executados):
        """Verifica se as dependências do ETL foram executadas"""
        for dep in etl['dependencias']:
            if dep not in etls_executados:
                return False
        return True
    
    def executar_sequencia(self, dry_run=False, etl_inicial=None, etl_final=None, 
                          skip_etls=None, batch_size=None, progress_interval=None):
        """Executa a sequência completa de ETLs"""
        
        self.stats['inicio'] = datetime.now()
        etls_executados = []
        skip_etls = skip_etls or []
        
        print(f"\n🚀 INICIANDO EXECUÇÃO SEQUENCIAL DE ETLs")
        print(f"Modo: {'DRY-RUN' if dry_run else 'PRODUÇÃO'}")
        print(f"Data/Hora: {self.stats['inicio'].strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"ETLs a pular: {skip_etls}")
        
        for etl in self.etls_sequence:
            # Verificar se deve pular este ETL
            if etl['numero'] in skip_etls:
                print(f"⏭️  Pulando ETL {etl['numero']} - {etl['descricao']}")
                self.stats['etls_pulados'] += 1
                continue
            
            # Verificar se está no range de execução
            if etl_inicial and etl['numero'] < etl_inicial:
                continue
            if etl_final and etl['numero'] > etl_final:
                break
            
            # Verificar dependências
            if not self.verificar_dependencias(etl, etls_executados):
                print(f"⚠️  ETL {etl['numero']} pulado - dependências não atendidas")
                self.stats['etls_pulados'] += 1
                continue
            
            # Executar ETL
            self.stats['etls_executados'] += 1
            sucesso = self.executar_etl(etl, dry_run, batch_size, progress_interval)
            
            if sucesso:
                etls_executados.append(etl['numero'])
            else:
                if etl['critico']:
                    print(f"\n💥 ETL CRÍTICO {etl['numero']} falhou! Interrompendo execução.")
                    break
                else:
                    print(f"⚠️  ETL {etl['numero']} falhou, mas não é crítico. Continuando...")
        
        self.stats['fim'] = datetime.now()
        self.stats['tempo_total'] = (self.stats['fim'] - self.stats['inicio']).total_seconds()
        
        self.imprimir_relatorio_final()
    
    def imprimir_relatorio_final(self):
        """Imprime relatório final da execução"""
        print(f"\n{'='*70}")
        print("RELATÓRIO FINAL DE EXECUÇÃO")
        print(f"{'='*70}")
        print(f"Início: {self.stats['inicio'].strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"Fim: {self.stats['fim'].strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"Tempo total: {self.stats['tempo_total']:.2f}s")
        print(f"ETLs executados: {self.stats['etls_executados']}")
        print(f"ETLs com sucesso: {self.stats['etls_sucesso']}")
        print(f"ETLs com erro: {self.stats['etls_erro']}")
        print(f"ETLs pulados: {self.stats['etls_pulados']}")
        
        if self.stats['etls_erro'] > 0:
            print(f"\n⚠️  {self.stats['etls_erro']} ETL(s) falharam. Verifique os logs acima.")
        else:
            print(f"\n✅ Todos os ETLs executados com sucesso!")

def main():
    parser = argparse.ArgumentParser(description='Execução Sequencial de ETLs - GESTK')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Executa em modo de teste (não salva no banco)')
    parser.add_argument('--etl-inicial', type=str, 
                       help='Inicia a partir do ETL especificado (ex: 05)')
    parser.add_argument('--etl-final', type=str, 
                       help='Para no ETL especificado (ex: 10)')
    parser.add_argument('--skip-etls', type=str, 
                       help='Pula ETLs específicos separados por vírgula (ex: 05,06,07)')
    parser.add_argument('--batch-size', type=int, default=1000,
                       help='Tamanho do lote para ETLs que suportam (padrão: 1000)')
    parser.add_argument('--progress-interval', type=int, default=50,
                       help='Intervalo de progresso para ETLs que suportam (padrão: 50)')
    
    args = parser.parse_args()
    
    # Processar argumentos
    skip_etls = []
    if args.skip_etls:
        skip_etls = [etl.strip() for etl in args.skip_etls.split(',')]
    
    # Executar sequência
    executor = ETLSequencialExecutor()
    executor.executar_sequencia(
        dry_run=args.dry_run,
        etl_inicial=args.etl_inicial,
        etl_final=args.etl_final,
        skip_etls=skip_etls,
        batch_size=args.batch_size,
        progress_interval=args.progress_interval
    )

if __name__ == '__main__':
    main()
