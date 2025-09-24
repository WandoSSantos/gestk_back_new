from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType

from apps.core.models import Contabilidade, Usuario
from apps.pessoas.models import PessoaJuridica, PessoaFisica, Contrato
from apps.contabil.models import LancamentoContabil
from apps.fiscal.models import NotaFiscal
from ..serializers import (
    CarteiraClientesSerializer, CarteiraCategoriasSerializer, CarteiraEvolucaoSerializer
)

class CarteiraViewSet(viewsets.ViewSet):
    """ViewSet para análise de carteira"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def clientes(self, request):
        """
        Endpoint para listar clientes da carteira com status.
        Aplica a Regra de Ouro para filtrar por contabilidade do usuário logado.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Obter todos os contratos ativos para a contabilidade
            contratos = Contrato.objects.filter(contabilidade=contabilidade, ativo=True)

            # Inicializar contadores
            total_clientes = contratos.count()
            clientes_ativos = 0
            clientes_inativos = 0
            clientes_novos = 0
            clientes_sem_movimentacao = 0

            # Definir período para "novos" (ex: últimos 30 dias)
            data_limite_novos = timezone.now().date() - timedelta(days=30)

            results = []
            for contrato in contratos:
                cliente = contrato.cliente
                if not cliente:
                    continue

                # Contar lançamentos e notas fiscais
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
                status_cliente = 'Inativo'
                if total_lancamentos > 0 or total_notas > 0:
                    status_cliente = 'Ativo'
                elif contrato.data_inicio and contrato.data_inicio > timezone.now().date() - timedelta(days=30):
                    status_cliente = 'Novo'

                if status_cliente == 'Ativo':
                    clientes_ativos += 1
                elif status_cliente == 'Inativo':
                    clientes_inativos += 1
                elif status_cliente == 'Novo':
                    clientes_novos += 1

                serializer_data = {
                    'id': str(cliente.id),
                    'tipo': 'PJ' if isinstance(cliente, PessoaJuridica) else 'PF',
                    'nome': cliente.razao_social if isinstance(cliente, PessoaJuridica) else cliente.nome_completo,
                    'documento': cliente.cnpj if isinstance(cliente, PessoaJuridica) else cliente.cpf,
                    'status_cliente': status_cliente,
                    'data_inicio_contrato': contrato.data_inicio,
                    'data_termino_contrato': contrato.data_termino,
                    'total_lancamentos': total_lancamentos,
                    'valor_total_lancamentos': valor_total_lancamentos,
                    'total_notas_fiscais': total_notas,
                    'valor_total_notas_fiscais': valor_total_notas,
                }
                results.append(serializer_data)

            summary = {
                'total_clientes': total_clientes,
                'clientes_ativos': clientes_ativos,
                'clientes_inativos': clientes_inativos,
                'clientes_novos': clientes_novos,
                'clientes_sem_movimentacao': clientes_sem_movimentacao,
                'percentual_ativo': (clientes_ativos / total_clientes * 100) if total_clientes > 0 else 0
            }

            return Response({'summary': summary, 'results': results}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar dados da carteira: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def categorias(self, request):
        """
        Endpoint para agregações de clientes por categoria (regime fiscal, ramo de atividade).
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            contratos_ativos = Contrato.objects.filter(
                contabilidade=contabilidade,
                ativo=True
            )

            # Agrupar por regime fiscal
            regime_fiscal_data = []
            
            # Buscar pessoas jurídicas com contratos ativos
            pj_content_type = ContentType.objects.get_for_model(PessoaJuridica)
            contratos_pj = contratos_ativos.filter(content_type=pj_content_type)
            
            # Agrupar por regime tributário
            regimes = ['1', '2', '3', '4']  # Simples Nacional, Lucro Presumido, Lucro Real, MEI
            regime_labels = {
                '1': 'Simples Nacional',
                '2': 'Lucro Presumido', 
                '3': 'Lucro Real',
                '4': 'MEI - Microempreendedor Individual'
            }
            
            for regime in regimes:
                # Contar contratos por regime
                count = 0
                for contrato in contratos_pj:
                    cliente = contrato.cliente
                    if isinstance(cliente, PessoaJuridica) and cliente.regime_tributario == regime:
                        count += 1
                
                regime_fiscal_data.append({
                    'contabilidade': {
                        'id': str(contabilidade.id),
                        'cnpj': contabilidade.cnpj,
                        'razao_social': contabilidade.razao_social
                    },
                    'categoria': regime_labels.get(regime, 'Outros'),
                    'total_clientes': count
                })

            return Response(regime_fiscal_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar categorias da carteira: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def evolucao(self, request):
        """
        Endpoint para gráficos de evolução mensal de clientes.
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Simular dados de evolução mensal
            evolucao_data = []
            for i in range(6):  # Últimos 6 meses
                month = timezone.now().date() - timedelta(days=30 * i)
                total_clientes_mes = Contrato.objects.filter(
                    contabilidade=contabilidade,
                    data_inicio__lte=month,
                    ativo=True
                ).count()
                evolucao_data.append({
                    'mes_ano': month.strftime('%Y-%m'),
                    'total_clientes': total_clientes_mes
                })
            
            # Inverter para ordem cronológica crescente
            evolucao_data.reverse()

            return Response(evolucao_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar evolução da carteira: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
