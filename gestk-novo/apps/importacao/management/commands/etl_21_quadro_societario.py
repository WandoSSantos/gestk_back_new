"""
ETL 21 - Quadro Societário das Empresas

Importa informações do quadro societário das empresas incluindo:
- Sócios (Pessoa Física e Jurídica)
- Participações e quotas
- Capital social
- Dados da empresa

Aplicação da regra de ouro para mapeamento multitenant via CNPJ.
"""

from django.db import transaction
from ._base import BaseETLCommand
from core.models import Contabilidade
from pessoas.models import PessoaJuridica, PessoaFisica
from pessoas.models_quadro_societario import QuadroSocietario, CapitalSocial
from django.contrib.contenttypes.models import ContentType
import re
from datetime import date
from decimal import Decimal


class Command(BaseETLCommand):
    help = 'ETL 21 - Importação do Quadro Societário das Empresas com Sócios e Participações'

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
        parser.add_argument(
            '--update-only',
            action='store_true',
            help='Apenas atualizar dados existentes (não criar novos)',
        )
        parser.add_argument(
            '--data-inicio',
            type=str,
            default='2019-01-01',
            help='Data de início para importação (formato: YYYY-MM-DD)',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.limit = options['limit']
        self.update_only = options['update_only']
        self.data_inicio = options['data_inicio']
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhum dado será salvo no banco'))
        
        self.stdout.write(self.style.SUCCESS('=== ETL 21 - QUADRO SOCIETÁRIO DAS EMPRESAS ==='))
        self.stdout.write('NOTA: Execute ETL 04 (Contratos) primeiro para garantir dados de empresas!')
        
        # Construir mapa histórico para validação
        self.stdout.write('\n[1] Construindo mapa histórico de contabilidades...')
        historical_map = self.build_historical_contabilidade_map_cached()

        connection = self.get_sybase_connection()
        if not connection:
            return

        # Query otimizada para quadro societário
        query = f"""
        SELECT 
            bethadba.gequadrosocietario_socios.participacao, 
            bethadba.gequadrosocietario_socios.qdade_quotas,
            bethadba.gequadrosocietario_socios.codi_emp, 
            bethadba.gequadrosocietario_socios.i_socio,              
            bethadba.gesocios.i_socio, 
            bethadba.gesocios.nome, 
            bethadba.gesocios.inscricao,
            bethadba.geempre.nome_emp,
            capital_social = Isnull(( SELECT bethadba.gequadrosocietario.capital_social 
                                     FROM bethadba.gequadrosocietario
                                    WHERE bethadba.gequadrosocietario.codi_emp = bethadba.geempre.codi_emp 
                                      AND bethadba.gequadrosocietario.data = (SELECT max(q2.data) 
                                                                                FROM bethadba.gequadrosocietario AS q2
                                                                               WHERE q2.codi_emp = bethadba.geempre.codi_emp ) ),0), 
            geempre.ende_emp,
            geempre.cepe_emp,
            geempre.cgce_emp,
            geempre.imun_emp,
            geempre.bair_emp,
            geempre.nume_emp,
            geempre_cidade = IsNull((SELECT g.nome_municipio 
                                       FROM bethadba.gemunicipio AS g
                                      WHERE g.codigo_municipio = bethadba.geempre.codigo_municipio),''),
            geempre.esta_emp                                   
        FROM bethadba.geempre,
             bethadba.gequadrosocietario_socios, 
             bethadba.gesocios 
        WHERE bethadba.geempre.codi_emp = bethadba.gequadrosocietario_socios.codi_emp AND 
              bethadba.gequadrosocietario_socios.i_socio = bethadba.gesocios.i_socio AND
              bethadba.gequadrosocietario_socios.data = (SELECT max(s.data)
                                                           FROM bethadba.gequadrosocietario_socios AS s
                                                          WHERE s.codi_emp = bethadba.gequadrosocietario_socios.codi_emp)
              AND bethadba.geempre.cgce_emp IS NOT NULL 
              AND bethadba.geempre.cgce_emp != ''
        ORDER BY bethadba.geempre.codi_emp, bethadba.gesocios.i_socio
        """
        
        if self.limit:
            query = f"SELECT TOP {self.limit} * FROM ({query}) AS quadro_societario"

        self.stdout.write("\n[2] Extraindo dados do Quadro Societário do Sybase...")
        data = self.execute_query(connection, query)
        connection.close()

        if not data:
            self.stdout.write(self.style.WARNING('Nenhum registro de quadro societário encontrado.'))
            return

        self.stdout.write(f"{len(data)} registros de quadro societário extraídos. Iniciando o carregamento...")
        
        # Estatísticas
        stats = {
            'empresas_processadas': 0,
            'socios_criados': 0,
            'socios_atualizados': 0,
            'empresas_atualizadas': 0,
            'erros': 0,
            'socios_pf_criados': 0,
            'socios_pj_criados': 0,
        }

        try:
            if not self.dry_run:
                with transaction.atomic():
                    self.processar_quadro_societario(data, historical_map, stats)
            else:
                self.processar_quadro_societario(data, historical_map, stats)
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocorreu um erro durante o carregamento: {e}'))
            raise
        finally:
            if hasattr(self, '_sybase_connection') and self._sybase_connection:
                try:
                    self.close_sybase_connection()
                except:
                    pass

        # Relatório final
        self.gerar_relatorio_final(stats)

    def processar_quadro_societario(self, data, historical_map, stats):
        """Processa os dados do quadro societário"""
        
        # Agrupar dados por empresa (codi_emp)
        empresas_data = {}
        for item in data:
            codi_emp = item.get('codi_emp')
            if codi_emp not in empresas_data:
                empresas_data[codi_emp] = {
                    'dados_empresa': item,
                    'socios': []
                }
            empresas_data[codi_emp]['socios'].append(item)
        
        self.stdout.write(f"Processando {len(empresas_data)} empresas com quadro societário...")
        
        for i, (codi_emp, empresa_data) in enumerate(empresas_data.items(), 1):
            if i % 50 == 0:
                self.stdout.write(f"Processando empresa {i}/{len(empresas_data)}...")
            
            try:
                self.processar_empresa_quadro_societario(empresa_data, historical_map, stats)
                stats['empresas_processadas'] += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erro ao processar empresa {codi_emp}: {e}'))
                stats['erros'] += 1
                continue

    def processar_empresa_quadro_societario(self, empresa_data, historical_map, stats):
        """Processa uma empresa específica e seu quadro societário"""
        
        dados_empresa = empresa_data['dados_empresa']
        socios = empresa_data['socios']
        
        # 1. Buscar empresa no banco pelo CNPJ
        cnpj_empresa = self.limpar_documento(dados_empresa.get('cgce_emp'))
        if not cnpj_empresa:
            self.stdout.write(self.style.WARNING(f"CNPJ inválido para empresa {dados_empresa.get('codi_emp')}. Pulando."))
            stats['erros'] += 1
            return
        
        # Buscar empresa usando regra de ouro
        empresa = self.buscar_empresa_por_cnpj(cnpj_empresa, historical_map)
        if not empresa:
            self.stdout.write(self.style.WARNING(f"Empresa com CNPJ {cnpj_empresa} não encontrada. Pulando."))
            stats['erros'] += 1
            return
        
        # 2. Atualizar dados da empresa (endereço)
        if not self.dry_run:
            self.atualizar_dados_empresa(empresa, dados_empresa)
            stats['empresas_atualizadas'] += 1
        
        # 3. Criar capital social
        self.criar_capital_social(empresa, dados_empresa)
        
        # 4. Processar sócios
        for socio_data in socios:
            try:
                self.processar_socio(socio_data, empresa, stats)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erro ao processar sócio {socio_data.get("i_socio")}: {e}'))
                stats['erros'] += 1
                continue

    def buscar_empresa_por_cnpj(self, cnpj, historical_map):
        """Busca empresa pelo CNPJ usando regra de ouro"""
        try:
            # Buscar diretamente na tabela PessoaJuridica
            empresa = PessoaJuridica.objects.filter(cnpj=cnpj).first()
            if empresa:
                return empresa
            
            # Se não encontrou, tentar criar usando dados do Sybase
            # (Isso seria necessário se a empresa não foi importada no ETL 04)
            self.stdout.write(self.style.WARNING(f"Empresa com CNPJ {cnpj} não encontrada. Seria necessário criar via ETL 04 primeiro."))
            return None
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao buscar empresa por CNPJ {cnpj}: {e}'))
            return None

    def processar_socio(self, socio_data, empresa, stats):
        """Processa um sócio específico"""
        
        inscricao = self.limpar_documento(socio_data.get('inscricao'))
        nome = str(socio_data.get('nome') or '').strip()
        
        if not inscricao or not nome:
            self.stdout.write(self.style.WARNING(f"Sócio com dados inválidos: inscrição='{inscricao}', nome='{nome}'. Pulando."))
            stats['erros'] += 1
            return
        
        # Determinar se é PF ou PJ baseado no tamanho da inscrição
        if len(inscricao) == 11:
            # Pessoa Física
            socio = self.buscar_ou_criar_pessoa_fisica(inscricao, nome, socio_data)
            if socio:
                stats['socios_pf_criados'] += 1
        elif len(inscricao) == 14:
            # Pessoa Jurídica
            socio = self.buscar_ou_criar_pessoa_juridica(inscricao, nome, socio_data)
            if socio:
                stats['socios_pj_criados'] += 1
        else:
            self.stdout.write(self.style.WARNING(f"Inscrição inválida '{inscricao}' para sócio {nome}. Pulando."))
            stats['erros'] += 1
            return
        
        if not socio:
            stats['erros'] += 1
            return
        
        # Criar relacionamento sócio-empresa no quadro societário
        self.criar_quadro_societario(socio, empresa, socio_data, stats)

    def buscar_ou_criar_pessoa_fisica(self, cpf, nome, socio_data):
        """Busca ou cria pessoa física"""
        try:
            if not self.dry_run:
                pessoa, created = PessoaFisica.objects.get_or_create(
                    cpf=cpf,
                    defaults={
                        'id_legado': socio_data.get('i_socio'),
                        'nome_completo': nome,
                    }
                )
                return pessoa
            else:
                # Modo dry-run: verificar se existe
                if PessoaFisica.objects.filter(cpf=cpf).exists():
                    return PessoaFisica.objects.filter(cpf=cpf).first()
                else:
                    return PessoaFisica(cpf=cpf, nome_completo=nome)  # Objeto temporário
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao criar/buscar PF {cpf}: {e}'))
            return None

    def buscar_ou_criar_pessoa_juridica(self, cnpj, nome, socio_data):
        """Busca ou cria pessoa jurídica"""
        try:
            if not self.dry_run:
                pessoa, created = PessoaJuridica.objects.get_or_create(
                    cnpj=cnpj,
                    defaults={
                        'id_legado': socio_data.get('i_socio'),
                        'razao_social': nome,
                    }
                )
                return pessoa
            else:
                # Modo dry-run: verificar se existe
                if PessoaJuridica.objects.filter(cnpj=cnpj).exists():
                    return PessoaJuridica.objects.filter(cnpj=cnpj).first()
                else:
                    return PessoaJuridica(cnpj=cnpj, razao_social=nome)  # Objeto temporário
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao criar/buscar PJ {cnpj}: {e}'))
            return None

    def atualizar_dados_empresa(self, empresa, dados_empresa):
        """Atualiza dados da empresa com informações do quadro societário"""
        try:
            # Atualizar endereço se não estiver preenchido
            if not empresa.endereco and dados_empresa.get('ende_emp'):
                empresa.endereco = str(dados_empresa.get('ende_emp', '')).strip()
            
            if not empresa.numero and dados_empresa.get('nume_emp'):
                empresa.numero = str(dados_empresa.get('nume_emp', '')).strip()
            
            if not empresa.bairro and dados_empresa.get('bair_emp'):
                empresa.bairro = str(dados_empresa.get('bair_emp', '')).strip()
            
            if not empresa.cidade and dados_empresa.get('geempre_cidade'):
                empresa.cidade = str(dados_empresa.get('geempre_cidade', '')).strip()
            
            if not empresa.uf and dados_empresa.get('esta_emp'):
                empresa.uf = str(dados_empresa.get('esta_emp', '')).strip()
            
            if not empresa.cep and dados_empresa.get('cepe_emp'):
                cep = str(dados_empresa.get('cepe_emp', '')).strip()
                empresa.cep = self.formatar_cep(cep)
            
            if not empresa.inscricao_municipal and dados_empresa.get('imun_emp'):
                empresa.inscricao_municipal = str(dados_empresa.get('imun_emp', '')).strip()
            
            # Salvar alterações
            empresa.save()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao atualizar dados da empresa {empresa.cnpj}: {e}'))

    def limpar_documento(self, documento):
        """Limpa e valida documento (CPF/CNPJ)"""
        if not documento:
            return None
        
        # Remove caracteres não numéricos
        documento_limpo = re.sub(r'\D', '', str(documento))
        
        # Valida tamanho
        if len(documento_limpo) in [11, 14]:
            return documento_limpo
        
        return None

    def formatar_cep(self, cep):
        """Formata CEP no padrão brasileiro"""
        if not cep:
            return None
        
        cep_limpo = re.sub(r'\D', '', str(cep))
        if len(cep_limpo) == 8:
            return f"{cep_limpo[:5]}-{cep_limpo[5:]}"
        
        return cep_limpo

    def criar_quadro_societario(self, socio, empresa, socio_data, stats):
        """Cria registro no quadro societário"""
        try:
            if not self.dry_run:
                # Obter ContentType do sócio
                content_type = ContentType.objects.get_for_model(socio)
                
                # Converter participação para decimal
                participacao = socio_data.get('participacao')
                participacao_decimal = None
                if participacao:
                    try:
                        participacao_decimal = Decimal(str(participacao))
                    except (ValueError, TypeError):
                        pass
                
                # Converter quantidade de quotas
                qdade_quotas = socio_data.get('qdade_quotas')
                quantidade_quotas = None
                if qdade_quotas:
                    try:
                        quantidade_quotas = int(qdade_quotas)
                    except (ValueError, TypeError):
                        pass
                
                # Criar ou atualizar quadro societário
                quadro, created = QuadroSocietario.objects.update_or_create(
                    empresa=empresa,
                    content_type=content_type,
                    object_id=socio.id,
                    defaults={
                        'participacao_percentual': participacao_decimal,
                        'quantidade_quotas': quantidade_quotas,
                        'id_legado_socio': socio_data.get('i_socio'),
                        'id_legado_empresa': socio_data.get('codi_emp'),
                        'ativo': True,
                    }
                )
                
                if created:
                    stats['socios_criados'] += 1
                else:
                    stats['socios_atualizados'] += 1
            else:
                # Modo dry-run: apenas contar
                if QuadroSocietario.objects.filter(
                    empresa=empresa,
                    content_type=ContentType.objects.get_for_model(socio),
                    object_id=socio.id
                ).exists():
                    stats['socios_atualizados'] += 1
                else:
                    stats['socios_criados'] += 1
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao criar quadro societário: {e}'))
            stats['erros'] += 1

    def criar_capital_social(self, empresa, dados_empresa):
        """Cria registro de capital social"""
        try:
            capital_social = dados_empresa.get('capital_social')
            if not capital_social or capital_social == 0:
                return
            
            if not self.dry_run:
                # Converter para decimal
                try:
                    valor_capital = Decimal(str(capital_social))
                except (ValueError, TypeError):
                    return
                
                # Criar registro de capital social
                CapitalSocial.objects.update_or_create(
                    empresa=empresa,
                    data_referencia=date.today(),
                    fonte='QUADRO_SOCIETARIO',
                    defaults={
                        'valor_capital': valor_capital,
                    }
                )
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao criar capital social: {e}'))

    def gerar_relatorio_final(self, stats):
        """Gera relatório final da importação"""
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('RELATÓRIO FINAL - ETL 21 QUADRO SOCIETÁRIO'))
        self.stdout.write('='*70)
        self.stdout.write(f'Empresas processadas: {stats["empresas_processadas"]}')
        self.stdout.write(f'Empresas atualizadas: {stats["empresas_atualizadas"]}')
        self.stdout.write(f'Sócios criados: {stats["socios_criados"]}')
        self.stdout.write(f'  - Pessoas Físicas: {stats["socios_pf_criados"]}')
        self.stdout.write(f'  - Pessoas Jurídicas: {stats["socios_pj_criados"]}')
        self.stdout.write(f'Erros: {stats["erros"]}')
        
        # Estatísticas de performance
        self.print_stats()
        
        self.stdout.write('\n' + '='*70)
        if self.dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhum dado foi salvo no banco'))
        else:
            self.stdout.write(self.style.SUCCESS('ETL 21 CONCLUÍDO COM SUCESSO!'))
        self.stdout.write('='*70)
