"""
Views para endpoints de gestão
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Sum, Avg, Max, Min
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.contenttypes.models import ContentType

from apps.core.models import Contabilidade, Usuario
from apps.pessoas.models import PessoaJuridica, PessoaFisica, Contrato
from apps.contabil.models import LancamentoContabil
from apps.fiscal.models import NotaFiscal
from apps.funcionarios.models import Funcionario
from .serializers import (
    CarteiraClientesSerializer, CarteiraCategoriasSerializer, CarteiraEvolucaoSerializer,
    ClienteDetalhesSerializer, ClienteListaSerializer, SocioMajoritarioSerializer,
    UsuarioSerializer, UsuarioAtividadesSerializer, UsuarioProdutividadeSerializer
)


class CarteiraViewSet(viewsets.ViewSet):
    """
    ViewSet para análise de carteira de clientes
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def clientes(self, request):
        """
        Endpoint: /api/gestao/carteira/clientes/
        Lista clientes por status (Ativos, Inativos, Novos, Sem movimentação)
        """
        try:
            # Filtrar por contabilidade do usuário
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não possui contabilidade associada"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar contratos da contabilidade
            contratos = Contrato.objects.filter(contabilidade=contabilidade)
            
            # Contar por status
            total_clientes = contratos.count()
            clientes_ativos = contratos.filter(ativo=True).count()
            clientes_inativos = contratos.filter(ativo=False).count()
            
            # Clientes novos (últimos 30 dias)
            data_limite_novos = timezone.now().date() - timedelta(days=30)
            clientes_novos = contratos.filter(
                ativo=True,
                data_inicio__gte=data_limite_novos
            ).count()
            
            # Clientes sem movimentação (simulado - sem dados reais de lançamentos)
            contratos_sem_movimentacao = 0  # Simulado por enquanto
            
            percentual_ativo = (clientes_ativos / total_clientes * 100) if total_clientes > 0 else 0

            data = {
                'contabilidade': {
                    'id': str(contabilidade.id),
                    'cnpj': contabilidade.cnpj,
                    'razao_social': contabilidade.razao_social,
                    'nome_fantasia': contabilidade.nome_fantasia
                },
                'total_clientes': total_clientes,
                'clientes_ativos': clientes_ativos,
                'clientes_inativos': clientes_inativos,
                'clientes_novos': clientes_novos,
                'clientes_sem_movimentacao': contratos_sem_movimentacao,
                'percentual_ativo': round(percentual_ativo, 2)
            }

            serializer = CarteiraClientesSerializer(data)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Erro ao buscar dados da carteira: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def categorias(self, request):
        """
        Endpoint: /api/gestao/carteira/categorias/
        Agregações por regime fiscal e ramo de atividade
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não possui contabilidade associada"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar contratos ativos da contabilidade
            contratos_ativos = Contrato.objects.filter(
                contabilidade=contabilidade,
                ativo=True
            )

            # Agrupar por regime fiscal (simulado - baseado em dados disponíveis)
            # Como não temos campo específico, vamos usar uma lógica baseada no CNPJ
            regime_fiscal_data = []
            
            # Simular categorias baseadas nos dados existentes
            regimes = ['Simples Nacional', 'Lucro Presumido', 'Lucro Real']
            total_contratos = contratos_ativos.count()
            
            for regime in regimes:
                # Lógica simplificada para demonstração - dividir igualmente
                count = total_contratos // 3
                
                regime_fiscal_data.append({
                    'contabilidade': {
                        'id': str(contabilidade.id),
                        'cnpj': contabilidade.cnpj,
                        'razao_social': contabilidade.razao_social,
                        'nome_fantasia': contabilidade.nome_fantasia
                    },
                    'regime_fiscal': regime,
                    'ramo_atividade': 'Todos',
                    'total_clientes': count,
                    'percentual': round((count / contratos_ativos.count() * 100), 2) if contratos_ativos.count() > 0 else 0
                })

            serializer = CarteiraCategoriasSerializer(regime_fiscal_data, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Erro ao buscar categorias da carteira: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def evolucao(self, request):
        """
        Endpoint: /api/gestao/carteira/evolucao/
        Gráficos de evolução mensal de clientes
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não possui contabilidade associada"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar contratos da contabilidade
            contratos = Contrato.objects.filter(contabilidade=contabilidade)
            
            # Agrupar por mês/ano
            evolucao_data = []
            
            # Últimos 12 meses
            for i in range(12):
                data_referencia = timezone.now().date() - timedelta(days=30 * i)
                mes_ano = data_referencia.strftime('%Y-%m')
                
                # Contratos ativos no mês
                contratos_ativos_mes = contratos.filter(
                    ativo=True,
                    data_inicio__lte=data_referencia
                ).count()
                
                # Contratos inativos no mês
                contratos_inativos_mes = contratos.filter(
                    ativo=False,
                    data_termino__lte=data_referencia
                ).count()
                
                # Novos contratos no mês
                contratos_novos_mes = contratos.filter(
                    data_inicio__year=data_referencia.year,
                    data_inicio__month=data_referencia.month
                ).count()
                
                # Contratos cancelados no mês
                contratos_cancelados_mes = contratos.filter(
                    data_termino__year=data_referencia.year,
                    data_termino__month=data_referencia.month,
                    ativo=False
                ).count()
                
                evolucao_data.append({
                    'contabilidade': {
                        'id': str(contabilidade.id),
                        'cnpj': contabilidade.cnpj,
                        'razao_social': contabilidade.razao_social,
                        'nome_fantasia': contabilidade.nome_fantasia
                    },
                    'mes_ano': mes_ano,
                    'total_clientes': contratos_ativos_mes + contratos_inativos_mes,
                    'clientes_ativos': contratos_ativos_mes,
                    'clientes_inativos': contratos_inativos_mes,
                    'clientes_novos': contratos_novos_mes,
                    'clientes_cancelados': contratos_cancelados_mes
                })

            # Ordenar por mês/ano
            evolucao_data.sort(key=lambda x: x['mes_ano'])

            serializer = CarteiraEvolucaoSerializer(evolucao_data, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Erro ao buscar evolução da carteira: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ClientesViewSet(viewsets.ViewSet):
    """
    ViewSet para análise de clientes
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def lista(self, request):
        """
        Endpoint: /api/gestao/clientes/lista/
        Tabela por competência com dados contábeis
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não possui contabilidade associada"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar contratos ativos da contabilidade
            contratos = Contrato.objects.filter(
                contabilidade=contabilidade,
                ativo=True
            ).select_related('contabilidade')

            # Filtrar por competência se especificado
            competencia = request.query_params.get('competencia')
            if competencia:
                try:
                    ano, mes = competencia.split('-')
                    contratos = contratos.filter(
                        data_inicio__year=int(ano),
                        data_inicio__month=int(mes)
                    )
                except ValueError:
                    return Response(
                        {"error": "Formato de competência inválido. Use YYYY-MM"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Preparar dados dos clientes
            clientes_data = []
            for contrato in contratos:
                cliente = contrato.cliente
                if not cliente:
                    continue

                # Contar lançamentos e notas fiscais
                # Lançamentos contábeis agora têm relacionamento com contrato (Regra de Ouro)
                total_lancamentos = LancamentoContabil.objects.filter(contrato=contrato).count()
                total_notas = NotaFiscal.objects.filter(contrato=contrato).count()
                
                # Calcular valores totais
                valor_total_lancamentos = LancamentoContabil.objects.filter(
                    contrato=contrato
                ).aggregate(total=Sum('valor_total'))['total'] or 0
                
                valor_total_notas = NotaFiscal.objects.filter(
                    contrato=contrato
                ).aggregate(total=Sum('valor_total'))['total'] or 0

                # Determinar status
                if total_lancamentos > 0 or total_notas > 0:
                    status_cliente = 'Ativo'
                elif contrato.data_inicio and contrato.data_inicio > timezone.now().date() - timedelta(days=30):
                    status_cliente = 'Novo'
                else:
                    status_cliente = 'Sem movimentação'

                clientes_data.append({
                    'cliente': {
                        'id': str(cliente.id),
                        'tipo': 'PJ' if isinstance(cliente, PessoaJuridica) else 'PF',
                        'cnpj_cpf': cliente.cnpj if isinstance(cliente, PessoaJuridica) else cliente.cpf,
                        'razao_social_nome': cliente.razao_social if isinstance(cliente, PessoaJuridica) else cliente.nome_completo,
                        'nome_fantasia': getattr(cliente, 'nome_fantasia', None),
                        'email': cliente.email,
                        'telefone': cliente.telefone,
                        'cidade': cliente.cidade,
                        'uf': cliente.uf,
                        'ativo': contrato.ativo,
                        'data_inicio_contrato': contrato.data_inicio,
                        'valor_honorario': contrato.valor_honorario
                    },
                    'contabilidade': {
                        'id': str(contabilidade.id),
                        'cnpj': contabilidade.cnpj,
                        'razao_social': contabilidade.razao_social,
                        'nome_fantasia': contabilidade.nome_fantasia
                    },
                    'competencia': competencia or timezone.now().strftime('%Y-%m'),
                    'total_lancamentos': total_lancamentos,
                    'total_notas_fiscais': total_notas,
                    'valor_total_lancamentos': valor_total_lancamentos,
                    'valor_total_notas': valor_total_notas,
                    'status': status_cliente
                })

            serializer = ClienteListaSerializer(clientes_data, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Erro ao buscar lista de clientes: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def detalhes(self, request):
        """
        Endpoint: /api/gestao/clientes/detalhes/
        Visualização detalhada por cliente
        """
        try:
            cliente_id = request.query_params.get('cliente_id')
            if not cliente_id:
                return Response(
                    {"error": "Parâmetro cliente_id é obrigatório"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não possui contabilidade associada"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar contrato do cliente
            try:
                contrato = Contrato.objects.get(
                    contabilidade=contabilidade,
                    object_id=cliente_id,
                    ativo=True
                )
            except Contrato.DoesNotExist:
                return Response(
                    {"error": "Cliente não encontrado ou inativo"}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            cliente = contrato.cliente
            if not cliente:
                return Response(
                    {"error": "Cliente não encontrado"}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Buscar dados relacionados
            # Lançamentos contábeis agora têm relacionamento com contrato (Regra de Ouro)
            total_lancamentos = LancamentoContabil.objects.filter(contrato=contrato).count()
            total_notas = NotaFiscal.objects.filter(contrato=contrato).count()
            total_funcionarios = Funcionario.objects.filter(contrato=contrato).count()

            # Últimas atividades
            ultimo_lancamento = LancamentoContabil.objects.filter(
                contrato=contrato
            ).order_by('-data_lancamento').first()
            
            ultima_nota = NotaFiscal.objects.filter(
                contrato=contrato
            ).order_by('-data_emissao').first()

            data = {
                'cliente': {
                    'id': str(cliente.id),
                    'tipo': 'PJ' if isinstance(cliente, PessoaJuridica) else 'PF',
                    'cnpj_cpf': cliente.cnpj if isinstance(cliente, PessoaJuridica) else cliente.cpf,
                    'razao_social_nome': cliente.razao_social if isinstance(cliente, PessoaJuridica) else cliente.nome_completo,
                    'nome_fantasia': getattr(cliente, 'nome_fantasia', None),
                    'email': cliente.email,
                    'telefone': cliente.telefone,
                    'cidade': cliente.cidade,
                    'uf': cliente.uf,
                    'ativo': contrato.ativo,
                    'data_inicio_contrato': contrato.data_inicio,
                    'valor_honorario': contrato.valor_honorario
                },
                'contabilidade': {
                    'id': str(contabilidade.id),
                    'cnpj': contabilidade.cnpj,
                    'razao_social': contabilidade.razao_social,
                    'nome_fantasia': contabilidade.nome_fantasia
                },
                'contrato_id': str(contrato.id),
                'data_inicio_contrato': contrato.data_inicio,
                'data_termino_contrato': contrato.data_termino,
                'valor_honorario': contrato.valor_honorario,
                'dia_vencimento': contrato.dia_vencimento,
                'total_lancamentos': total_lancamentos,
                'total_notas_fiscais': total_notas,
                'total_funcionarios': total_funcionarios,
                'ultimo_lancamento': ultimo_lancamento.data_lancamento if ultimo_lancamento else None,
                'ultima_nota_fiscal': ultima_nota.data_emissao if ultima_nota else None
            }

            serializer = ClienteDetalhesSerializer(data)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Erro ao buscar detalhes do cliente: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def socios(self, request):
        """
        Endpoint: /api/gestao/clientes/socios/
        Nome do sócio majoritário
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não possui contabilidade associada"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar contratos ativos da contabilidade
            contratos = Contrato.objects.filter(
                contabilidade=contabilidade,
                ativo=True
            )

            socios_data = []
            for contrato in contratos:
                cliente = contrato.cliente
                if not cliente or not isinstance(cliente, PessoaJuridica):
                    continue

                # Simular dados do sócio majoritário
                # Em um sistema real, isso viria de uma tabela de quadro societário
                socio_data = {
                    'cliente': {
                        'id': str(cliente.id),
                        'tipo': 'PJ',
                        'cnpj_cpf': cliente.cnpj,
                        'razao_social_nome': cliente.razao_social,
                        'nome_fantasia': cliente.nome_fantasia,
                        'email': cliente.email,
                        'telefone': cliente.telefone,
                        'cidade': cliente.cidade,
                        'uf': cliente.uf,
                        'ativo': contrato.ativo,
                        'data_inicio_contrato': contrato.data_inicio,
                        'valor_honorario': contrato.valor_honorario
                    },
                    'contabilidade': {
                        'id': str(contabilidade.id),
                        'cnpj': contabilidade.cnpj,
                        'razao_social': contabilidade.razao_social,
                        'nome_fantasia': contabilidade.nome_fantasia
                    },
                    'socio_nome': cliente.responsavel_legal or 'Não informado',
                    'socio_cpf': cliente.cpf_responsavel or 'Não informado',
                    'percentual_participacao': 51.0,  # Simulado
                    'tipo_socio': 'Administrador'
                }
                
                socios_data.append(socio_data)

            serializer = SocioMajoritarioSerializer(socios_data, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Erro ao buscar sócios: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UsuariosViewSet(viewsets.ViewSet):
    """
    ViewSet para análise de usuários
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def lista(self, request):
        """
        Endpoint: /api/gestao/usuarios/lista/
        Lista de usuários com nome e função
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não possui contabilidade associada"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar usuários da contabilidade
            usuarios = Usuario.objects.filter(contabilidade=contabilidade)

            serializer = UsuarioSerializer(usuarios, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Erro ao buscar usuários: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def atividades(self, request):
        """
        Endpoint: /api/gestao/usuarios/atividades/
        Atividades por usuário (cálculo por hora)
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não possui contabilidade associada"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Filtrar por período se especificado
            data_inicio = request.query_params.get('data_inicio')
            data_fim = request.query_params.get('data_fim')
            
            if data_inicio and data_fim:
                try:
                    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
                except ValueError:
                    return Response(
                        {"error": "Formato de data inválido. Use YYYY-MM-DD"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Últimos 30 dias por padrão
                data_fim = timezone.now().date()
                data_inicio = data_fim - timedelta(days=30)

            # Buscar usuários da contabilidade
            usuarios = Usuario.objects.filter(contabilidade=contabilidade)

            atividades_data = []
            for usuario in usuarios:
                # Simular atividades baseadas no tipo de usuário
                if usuario.tipo_usuario == 'etl':
                    total_atividades = 150
                    atividades_etl = 120
                    atividades_administracao = 20
                    atividades_operacionais = 10
                elif usuario.tipo_usuario == 'admin':
                    total_atividades = 200
                    atividades_etl = 50
                    atividades_administracao = 100
                    atividades_operacionais = 50
                else:
                    total_atividades = 80
                    atividades_etl = 0
                    atividades_administracao = 20
                    atividades_operacionais = 60

                tempo_total_horas = total_atividades * 0.5  # 30 min por atividade

                atividades_data.append({
                    'usuario': {
                        'id': usuario.id,
                        'username': usuario.username,
                        'email': usuario.email,
                        'first_name': usuario.first_name,
                        'last_name': usuario.last_name,
                        'tipo_usuario': usuario.tipo_usuario,
                        'contabilidade_razao_social': contabilidade.razao_social,
                        'contabilidade_cnpj': contabilidade.cnpj
                    },
                    'data_atividade': data_fim,
                    'total_atividades': total_atividades,
                    'atividades_etl': atividades_etl,
                    'atividades_administracao': atividades_administracao,
                    'atividades_operacionais': atividades_operacionais,
                    'tempo_total_horas': tempo_total_horas
                })

            serializer = UsuarioAtividadesSerializer(atividades_data, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Erro ao buscar atividades dos usuários: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def produtividade(self, request):
        """
        Endpoint: /api/gestao/usuarios/produtividade/
        Relatórios de produtividade
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não possui contabilidade associada"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Filtrar por período se especificado
            periodo = request.query_params.get('periodo', 'mensal')
            
            # Buscar usuários da contabilidade
            usuarios = Usuario.objects.filter(contabilidade=contabilidade)

            produtividade_data = []
            for usuario in usuarios:
                # Simular dados de produtividade
                if usuario.tipo_usuario == 'etl':
                    total_atividades = 450
                    tempo_total_horas = 225.0
                elif usuario.tipo_usuario == 'admin':
                    total_atividades = 600
                    tempo_total_horas = 300.0
                else:
                    total_atividades = 240
                    tempo_total_horas = 120.0

                media_atividades_por_dia = total_atividades / 30
                media_tempo_por_atividade = tempo_total_horas / total_atividades if total_atividades > 0 else 0
                eficiencia = min(100, (total_atividades / 500) * 100)  # Baseado em 500 atividades como referência

                produtividade_data.append({
                    'usuario': {
                        'id': usuario.id,
                        'username': usuario.username,
                        'email': usuario.email,
                        'first_name': usuario.first_name,
                        'last_name': usuario.last_name,
                        'tipo_usuario': usuario.tipo_usuario,
                        'contabilidade_razao_social': contabilidade.razao_social,
                        'contabilidade_cnpj': contabilidade.cnpj
                    },
                    'periodo': periodo,
                    'total_atividades': total_atividades,
                    'tempo_total_horas': tempo_total_horas,
                    'media_atividades_por_dia': round(media_atividades_por_dia, 2),
                    'media_tempo_por_atividade': round(media_tempo_por_atividade, 2),
                    'eficiencia': round(eficiencia, 2)
                })

            serializer = UsuarioProdutividadeSerializer(produtividade_data, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Erro ao buscar produtividade dos usuários: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
