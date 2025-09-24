#!/usr/bin/env python
"""
ETL 00 - Mapeamento Completo de Empresas

Este ETL é executado ANTES de qualquer outro ETL para garantir que:
1. Todas as empresas do Sybase tenham Pessoas Jurídicas/Físicas no db_gestk
2. Todas as empresas tenham Contratos para o período 2019-2024
3. O mapeamento de contabilidades funcione corretamente

Sequência de execução:
- ETL 00 (este) - Mapeamento Completo
- ETL 01 - Contabilidades
- ETL 02 - CNAEs
- ETL 04 - Contratos (dados específicos)
- ETLs subsequentes...
"""

from datetime import date, datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from importacao.management.commands._base import BaseETLCommand
from pessoas.models import PessoaJuridica, PessoaFisica, Contrato
from core.models import Contabilidade


class Command(BaseETLCommand):
    help = 'ETL 00 - Mapeamento Completo de Empresas do Sybase'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executar em modo de teste (não salva no banco)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limitar número de empresas para processar (para testes)',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.limit = options['limit']
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhum dado será salvo no banco'))
        
        self.stdout.write(self.style.SUCCESS('=== ETL 00 - MAPEAMENTO COMPLETO DE EMPRESAS ==='))
        
        try:
            # 1. Construir mapa histórico de contabilidades
            self.stdout.write('\n[1] Construindo mapa histórico de contabilidades...')
            historical_map = self.build_historical_contabilidade_map_cached()
            
            # 2. Identificar todas as empresas no Sybase
            self.stdout.write('\n[2] Identificando empresas no Sybase...')
            empresas_sybase = self.identificar_empresas_sybase()
            
            # 3. Identificar empresas sem contratos
            self.stdout.write('\n[3] Identificando empresas sem contratos...')
            empresas_sem_contratos = self.identificar_empresas_sem_contratos(empresas_sybase, historical_map)
            
            # 4. Criar Pessoas Jurídicas/Físicas faltantes
            self.stdout.write('\n[4] Criando Pessoas Jurídicas/Físicas faltantes...')
            pessoas_criadas = self.criar_pessoas_faltantes(empresas_sem_contratos)
            
            # 5. Validar que não há empresas reais sem contratos
            self.stdout.write('\n[5] Validando empresas sem contratos...')
            if empresas_sem_contratos:
                self.stdout.write(self.style.WARNING(f'⚠️  ATENÇÃO: {len(empresas_sem_contratos)} empresas sem contratos encontradas:'))
                for empresa in empresas_sem_contratos:
                    self.stdout.write(f'  - {empresa["nome_emp"]} ({empresa["cgce_emp"]})')
                self.stdout.write(self.style.ERROR('❌ ETL 00 não deve criar contratos padrão!'))
                self.stdout.write(self.style.ERROR('❌ Contratos devem vir sempre do Sybase via ETL 04!'))
                return
            
            # 6. Validar mapeamento
            self.stdout.write('\n[6] Validando mapeamento...')
            self.validar_mapeamento()
            
            # 7. Relatório final
            empresas_exemplo_ignoradas = self.contar_empresas_exemplo_ignoradas(empresas_sybase)
            self.relatorio_final(empresas_sybase, empresas_sem_contratos, pessoas_criadas, 0, empresas_exemplo_ignoradas)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro durante execução: {e}'))
            raise
        finally:
            self.close_sybase_connection()

    def identificar_empresas_sybase(self):
        """Identifica todas as empresas únicas no Sybase"""
        self.stdout.write('Buscando empresas no Sybase...')
        
        query = """
        SELECT DISTINCT 
            ge.codi_emp,
            ge.nome_emp,
            ge.cgce_emp,
            CASE 
                WHEN LENGTH(TRIM(ge.cgce_emp)) = 14 THEN 'J'
                WHEN LENGTH(TRIM(ge.cgce_emp)) = 11 THEN 'F'
                ELSE 'U'
            END as tipo_pessoa
        FROM bethadba.geempre ge
        WHERE ge.cgce_emp IS NOT NULL 
        AND TRIM(ge.cgce_emp) != ''
        ORDER BY ge.codi_emp
        """
        
        if self.limit:
            query = f"SELECT TOP {self.limit} * FROM ({query}) AS empresas"
        
        connection = self.get_sybase_connection()
        if not connection:
            return []
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [column[0] for column in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            self.stdout.write(f'Encontradas {len(results)} empresas no Sybase')
            return results
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao buscar empresas: {e}'))
            return []

    def identificar_empresas_sem_contratos(self, empresas_sybase, historical_map):
        """Identifica empresas que não possuem contratos no db_gestk"""
        self.stdout.write('Verificando empresas sem contratos...')
        
        empresas_sem_contratos = []
        empresas_exemplo_ignoradas = 0
        
        for empresa in empresas_sybase:
            cgce_emp = empresa['cgce_emp']
            documento_limpo = self.limpar_documento(cgce_emp)
            
            if not documento_limpo:
                continue
            
            # Verificar se é empresa exemplo
            if self.eh_empresa_exemplo(empresa):
                empresas_exemplo_ignoradas += 1
                self.stdout.write(f'  ⚠ {empresa["nome_emp"]} ({documento_limpo}) - EMPRESA EXEMPLO (IGNORADA)')
                continue
            
            # Verificar se empresa tem contratos no mapeamento
            if documento_limpo not in historical_map:
                empresas_sem_contratos.append(empresa)
                self.stdout.write(f'  - {empresa["nome_emp"]} ({documento_limpo}) - SEM CONTRATOS')
        
        self.stdout.write(f'Encontradas {len(empresas_sem_contratos)} empresas sem contratos')
        self.stdout.write(f'Empresas exemplo ignoradas: {empresas_exemplo_ignoradas}')
        return empresas_sem_contratos
    
    def eh_empresa_exemplo(self, empresa):
        """Verifica se a empresa é um exemplo/modelo padrão"""
        nome_emp = empresa['nome_emp'].upper()
        cgce_emp = empresa['cgce_emp']
        
        # Validar CNPJ/CPF completos
        if not self.validar_documento_completo(cgce_emp):
            return True
        
        # Filtros por nome
        palavras_exemplo = [
            'EXEMPLO', 'MODELO', 'TESTE', 'DEMO', 'SAMPLE',
            'TEMPLATE', 'PADRAO', 'DEFAULT', 'DUMMY'
        ]
        
        for palavra in palavras_exemplo:
            if palavra in nome_emp:
                return True
        
        # Filtros por CNPJ/CPF (documentos fictícios)
        cnpj_ficticios = [
            '77777777', '88888888', '99999999', '00000000',
            '11111111', '22222222', '33333333', '44444444',
            '55555555', '66666666'
        ]
        
        for cnpj_ficticio in cnpj_ficticios:
            if cgce_emp.startswith(cnpj_ficticio):
                return True
        
        # Filtros específicos por padrões conhecidos
        if 'SIMPLES' in nome_emp and any(x in nome_emp for x in ['COMERCIO', 'SERVICO', 'INDUSTRIA']):
            return True
        
        # Filtros para empresas de regime tributário (exemplos)
        regimes_tributarios = ['LUCRO PRESUMIDO', 'LUCRO REAL', 'REAL']
        atividades = ['COMERCIO', 'SERVICO', 'SERVIÇO', 'INDUSTRIA', 'POSTO DE COMBUSTIVEL', 'COM, SERV E IND']
        
        for regime in regimes_tributarios:
            if regime in nome_emp:
                for atividade in atividades:
                    if atividade in nome_emp:
                        return True
        
        # Filtros adicionais para empresas exemplo
        padroes_exemplo = [
            'MATRIZ PRESUMIDO', 'FILIAL PRESUMIDO', 'FOLHA PROFESSOR',
            'ATIVIDADE IMOB', 'SIMPLES TRANSPORTADORA', 'EMPRESA JUNIOR',
            'TRANSPORTADORA', 'POSTO DE COMBUSTIVEL'
        ]
        
        for padrao in padroes_exemplo:
            if padrao in nome_emp:
                return True
        
        # Filtrar contabilidades (não são empresas)
        contabilidades = [
            'ASSESSORIA CONTABIL', 'TAX SIMPLES CONTABILIDADE', 'CONTABILIS',
            'CONTABILIDADE', 'ASSESSORIA', 'OFFICE'
        ]
        
        for contabilidade in contabilidades:
            if contabilidade in nome_emp:
                return True
        
        return False
    
    def validar_documento_completo(self, documento):
        """Valida se o CNPJ/CPF está completo e válido"""
        if not documento or not documento.strip():
            return False
        
        documento_limpo = self.limpar_documento(documento)
        if not documento_limpo:
            return False
        
        # CNPJ deve ter 14 dígitos
        if len(documento_limpo) == 14:
            return True
        
        # CPF deve ter 11 dígitos
        if len(documento_limpo) == 11:
            return True
        
        return False
    
    def contar_empresas_exemplo_ignoradas(self, empresas_sybase):
        """Conta quantas empresas exemplo foram ignoradas"""
        count = 0
        for empresa in empresas_sybase:
            if self.eh_empresa_exemplo(empresa):
                count += 1
        return count

    def criar_pessoas_faltantes(self, empresas_sem_contratos):
        """Cria Pessoas Jurídicas/Físicas faltantes"""
        self.stdout.write('Criando Pessoas Jurídicas/Físicas...')
        
        pessoas_criadas = {
            'juridicas': 0,
            'fisicas': 0,
            'erros': 0
        }
        
        for empresa in empresas_sem_contratos:
            try:
                documento_limpo = self.limpar_documento(empresa['cgce_emp'])
                tipo_pessoa = empresa['tipo_pessoa']
                
                if tipo_pessoa == 'J':
                    # Criar Pessoa Jurídica
                    pessoa, created = PessoaJuridica.objects.get_or_create(
                        cnpj=documento_limpo,
                        defaults={
                            'razao_social': empresa['nome_emp'],
                            'nome_fantasia': empresa['nome_emp'],
                            'id_legado': str(empresa['codi_emp']),
                        }
                    )
                    
                    if created:
                        pessoas_criadas['juridicas'] += 1
                        self.stdout.write(f'  ✓ Pessoa Jurídica criada: {pessoa.razao_social}')
                    else:
                        self.stdout.write(f'  - Pessoa Jurídica já existe: {pessoa.razao_social}')
                
                elif tipo_pessoa == 'F':
                    # Criar Pessoa Física
                    pessoa, created = PessoaFisica.objects.get_or_create(
                        cpf=documento_limpo,
                        defaults={
                            'nome_completo': empresa['nome_emp'],
                            'id_legado': str(empresa['codi_emp']),
                        }
                    )
                    
                    if created:
                        pessoas_criadas['fisicas'] += 1
                        self.stdout.write(f'  ✓ Pessoa Física criada: {pessoa.nome}')
                    else:
                        self.stdout.write(f'  - Pessoa Física já existe: {pessoa.nome}')
                
                else:
                    self.stdout.write(f'  ⚠ Tipo de pessoa desconhecido: {empresa["nome_emp"]}')
                    pessoas_criadas['erros'] += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erro ao criar pessoa {empresa["nome_emp"]}: {e}'))
                pessoas_criadas['erros'] += 1
        
        return pessoas_criadas


    def validar_mapeamento(self):
        """Valida se o mapeamento está funcionando corretamente"""
        self.stdout.write('Validando mapeamento...')
        
        # Reconstruir mapa histórico
        historical_map = self.build_historical_contabilidade_map_cached()
        
        # Testar algumas buscas
        empresas_teste = list(historical_map.keys())[:5]
        
        for documento in empresas_teste:
            contratos = historical_map[documento]
            self.stdout.write(f'  {documento}: {len(contratos)} contratos')
            
            # Testar busca por data
            data_teste = date(2023, 6, 1)
            contabilidade = self.get_contabilidade_for_date_optimized(historical_map, 1, data_teste)
            
            if contabilidade:
                self.stdout.write(f'    ✓ Busca por {data_teste}: {contabilidade}')
            else:
                self.stdout.write(f'    ⚠ Busca por {data_teste}: Nenhuma contabilidade encontrada')

    def relatorio_final(self, empresas_sybase, empresas_sem_contratos, pessoas_criadas, contratos_criados, empresas_exemplo_ignoradas):
        """Gera relatório final da execução"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('RELATÓRIO FINAL - ETL 00'))
        self.stdout.write('='*60)
        
        self.stdout.write(f'Total de empresas no Sybase: {len(empresas_sybase)}')
        self.stdout.write(f'Empresas exemplo ignoradas: {empresas_exemplo_ignoradas}')
        self.stdout.write(f'Empresas reais sem contratos: {len(empresas_sem_contratos)}')
        self.stdout.write(f'Pessoas Jurídicas criadas: {pessoas_criadas["juridicas"]}')
        self.stdout.write(f'Pessoas Físicas criadas: {pessoas_criadas["fisicas"]}')
        self.stdout.write(f'Erros na criação de pessoas: {pessoas_criadas["erros"]}')
        self.stdout.write(f'Contratos criados: {contratos_criados}')
        
        # Estatísticas de performance
        self.print_stats()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('ETL 00 CONCLUÍDO COM SUCESSO!'))
        self.stdout.write('='*60)
