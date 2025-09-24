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
from apps.pessoas.models_quadro_societario import QuadroSocietario
from apps.contabil.models import LancamentoContabil
from apps.fiscal.models import NotaFiscal
from apps.funcionarios.models import Funcionario
from ..serializers import (
    ClienteListaSerializer, ClienteDetalhesSerializer, SocioMajoritarioSerializer
)

class ClientesViewSet(viewsets.ViewSet):
    """ViewSet para análise de clientes"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def lista(self, request):
        """
        Endpoint para listar clientes com dados contábeis por competência.
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            competencia = request.query_params.get('competencia', timezone.now().strftime('%Y-%m'))
            
            # Filtrar contratos ativos para a contabilidade
            contratos = Contrato.objects.filter(
                contabilidade=contabilidade,
                ativo=True
            ).select_related('content_type')

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

                serializer_data = {
                    'id': str(cliente.id),
                    'tipo': 'PJ' if isinstance(cliente, PessoaJuridica) else 'PF',
                    'nome': cliente.razao_social if isinstance(cliente, PessoaJuridica) else cliente.nome_completo,
                    'documento': cliente.cnpj if isinstance(cliente, PessoaJuridica) else cliente.cpf,
                    'status_cliente': status_cliente,
                    'data_inicio_contrato': contrato.data_inicio,
                    'data_termino_contrato': contrato.data_termino,
                    'valor_honorario': contrato.valor_honorario,
                    'competencia': competencia,
                    'total_lancamentos': total_lancamentos,
                    'total_notas_fiscais': total_notas,
                    'valor_total_lancamentos': valor_total_lancamentos,
                    'valor_total_notas': valor_total_notas,
                    'status': status_cliente
                }
                results.append(serializer_data)

            return Response(results, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar lista de clientes: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def detalhes(self, request):
        """
        Endpoint para visualização detalhada por cliente.
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            cliente_id = request.query_params.get('cliente_id')
            if not cliente_id:
                return Response(
                    {"error": "ID do cliente é obrigatório."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar o cliente via Contrato (estrutura correta)
            cliente = None
            contrato = None
            
            # Tentar como Pessoa Jurídica
            pj_content_type = ContentType.objects.get_for_model(PessoaJuridica)
            contrato_pj = Contrato.objects.filter(
                contabilidade=contabilidade,
                content_type=pj_content_type,
                object_id=cliente_id,
                ativo=True
            ).first()
            
            if contrato_pj:
                cliente = contrato_pj.cliente
                contrato = contrato_pj
            else:
                # Tentar como Pessoa Física
                pf_content_type = ContentType.objects.get_for_model(PessoaFisica)
                contrato_pf = Contrato.objects.filter(
                    contabilidade=contabilidade,
                    content_type=pf_content_type,
                    object_id=cliente_id,
                    ativo=True
                ).first()
                
                if contrato_pf:
                    cliente = contrato_pf.cliente
                    contrato = contrato_pf

            if not cliente or not contrato:
                return Response(
                    {"error": "Cliente não encontrado ou sem contrato ativo."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Buscar dados relacionados
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
                    'nome': cliente.razao_social if isinstance(cliente, PessoaJuridica) else cliente.nome_completo,
                    'documento': cliente.cnpj if isinstance(cliente, PessoaJuridica) else cliente.cpf,
                    'data_abertura': cliente.data_abertura_empresa if isinstance(cliente, PessoaJuridica) else None,
                    'endereco': cliente.endereco,
                    'email': cliente.email,
                    'telefone': cliente.telefone,
                },
                'contrato': {
                    'id': str(contrato.id),
                    'data_inicio': contrato.data_inicio,
                    'data_termino': contrato.data_termino,
                    'valor_honorario': contrato.valor_honorario,
                    'dia_vencimento': contrato.dia_vencimento,
                    'total_lancamentos': total_lancamentos,
                    'total_notas_fiscais': total_notas,
                    'total_funcionarios': total_funcionarios,
                    'ultimo_lancamento': ultimo_lancamento.data_lancamento if ultimo_lancamento else None,
                    'ultima_nota_fiscal': ultima_nota.data_emissao if ultima_nota else None
                }
            }

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar detalhes do cliente: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def socios(self, request):
        """
        Endpoint para listar sócios majoritários de clientes PJ.
        Aplica a Regra de Ouro.
        """
        try:
            contabilidade = request.user.contabilidade
            if not contabilidade:
                return Response(
                    {"error": "Usuário não associado a uma contabilidade."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Buscar todas as Pessoas Jurídicas associadas à contabilidade via Contrato
            pj_content_type = ContentType.objects.get_for_model(PessoaJuridica)
            contratos_pj = Contrato.objects.filter(
                contabilidade=contabilidade,
                content_type=pj_content_type,
                ativo=True
            )
            pessoas_juridicas = [contrato.cliente for contrato in contratos_pj if contrato.cliente]

            results = []
            for pj in pessoas_juridicas:
                # Buscar o sócio majoritário (se houver)
                socio_majoritario = QuadroSocietario.objects.filter(
                    pessoa_juridica=pj
                ).order_by('-participacao_percentual').first()

                socio_data = {
                    'cliente_id': str(pj.id),
                    'razao_social': pj.razao_social,
                    'cnpj': pj.cnpj,
                    'socio_nome': None,
                    'participacao_percentual': None,
                    'tipo_socio': None
                }

                if socio_majoritario:
                    socio_data['socio_nome'] = socio_majoritario.pessoa_fisica.nome_completo if socio_majoritario.pessoa_fisica else socio_majoritario.pessoa_juridica_socio.razao_social
                    socio_data['participacao_percentual'] = socio_majoritario.participacao_percentual
                    socio_data['tipo_socio'] = 'PF' if socio_majoritario.pessoa_fisica else 'PJ'
                
                results.append(socio_data)

            return Response(results, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erro ao buscar sócios: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
