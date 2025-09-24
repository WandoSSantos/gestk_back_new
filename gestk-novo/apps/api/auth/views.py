"""
Views do módulo de Autenticação
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction

from apps.core.models import Usuario, Contabilidade
from apps.api.shared.serializers import SuccessSerializer, ErrorSerializer


class AuthViewSet(ViewSet):
    """
    ViewSet para autenticação e gerenciamento de usuários
    """
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """
        Endpoint de login com JWT
        """
        try:
            username = request.data.get('username')
            password = request.data.get('password')
            
            if not username or not password:
                return Response({
                    'error': 'Username e password são obrigatórios'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Autenticar usuário
            user = authenticate(username=username, password=password)
            
            if not user:
                return Response({
                    'error': 'Credenciais inválidas'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Verificar se o usuário tem contabilidade associada
            try:
                usuario_gestk = Usuario.objects.get(user=user)
                contabilidade = usuario_gestk.contabilidade
            except Usuario.DoesNotExist:
                return Response({
                    'error': 'Usuário não encontrado no sistema GESTK'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Gerar tokens JWT
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            # Adicionar informações da contabilidade ao token
            access_token['contabilidade_id'] = str(contabilidade.id)
            access_token['contabilidade_nome'] = contabilidade.nome_fantasia
            
            return Response({
                'access': str(access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                'contabilidade': {
                    'id': str(contabilidade.id),
                    'nome_fantasia': contabilidade.nome_fantasia,
                    'razao_social': contabilidade.razao_social,
                    'cnpj': contabilidade.cnpj,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erro interno do servidor: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """
        Endpoint de logout (invalida o refresh token)
        """
        try:
            refresh_token = request.data.get('refresh')
            
            if not refresh_token:
                return Response({
                    'error': 'Refresh token é obrigatório'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Invalidar o refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response({
                'message': 'Logout realizado com sucesso'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erro interno do servidor: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def refresh(self, request):
        """
        Endpoint para renovar o access token
        """
        try:
            refresh_token = request.data.get('refresh')
            
            if not refresh_token:
                return Response({
                    'error': 'Refresh token é obrigatório'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Renovar o access token
            refresh = RefreshToken(refresh_token)
            access_token = refresh.access_token
            
            # Adicionar informações da contabilidade ao token
            try:
                usuario_gestk = Usuario.objects.get(user=request.user)
                contabilidade = usuario_gestk.contabilidade
                access_token['contabilidade_id'] = str(contabilidade.id)
                access_token['contabilidade_nome'] = contabilidade.nome_fantasia
            except Usuario.DoesNotExist:
                pass
            
            return Response({
                'access': str(access_token)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erro interno do servidor: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """
        Endpoint para obter informações do usuário logado
        """
        try:
            # Obter informações do usuário
            user = request.user
            
            # Obter informações da contabilidade
            try:
                usuario_gestk = Usuario.objects.get(user=user)
                contabilidade = usuario_gestk.contabilidade
                
                contabilidade_info = {
                    'id': str(contabilidade.id),
                    'nome_fantasia': contabilidade.nome_fantasia,
                    'razao_social': contabilidade.razao_social,
                    'cnpj': contabilidade.cnpj,
                }
            except Usuario.DoesNotExist:
                contabilidade_info = None
            
            return Response({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_active': user.is_active,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                    'date_joined': user.date_joined,
                    'last_login': user.last_login,
                },
                'contabilidade': contabilidade_info
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erro interno do servidor: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UsuarioViewSet(ViewSet):
    """
    ViewSet para gerenciamento de usuários (apenas para superusuários)
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Retorna apenas usuários da contabilidade do usuário logado
        """
        try:
            usuario_gestk = Usuario.objects.get(user=self.request.user)
            return Usuario.objects.filter(contabilidade=usuario_gestk.contabilidade)
        except Usuario.DoesNotExist:
            return Usuario.objects.none()
    
    @action(detail=False, methods=['get'])
    def lista(self, request):
        """
        Lista usuários da contabilidade
        """
        try:
            usuarios = self.get_queryset()
            
            usuarios_data = []
            for usuario in usuarios:
                usuarios_data.append({
                    'id': str(usuario.id),
                    'nome_usuario': usuario.nome_usuario,
                    'email': usuario.email,
                    'ativo': usuario.ativo,
                    'data_criacao': usuario.data_criacao,
                    'ultimo_acesso': usuario.ultimo_acesso,
                })
            
            return Response({
                'usuarios': usuarios_data,
                'total': len(usuarios_data)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Erro interno do servidor: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def detalhes(self, request, pk=None):
        """
        Detalhes de um usuário específico
        """
        try:
            usuario = self.get_queryset().get(id=pk)
            
            return Response({
                'id': str(usuario.id),
                'nome_usuario': usuario.nome_usuario,
                'email': usuario.email,
                'ativo': usuario.ativo,
                'data_criacao': usuario.data_criacao,
                'ultimo_acesso': usuario.ultimo_acesso,
                'contabilidade': {
                    'id': str(usuario.contabilidade.id),
                    'nome_fantasia': usuario.contabilidade.nome_fantasia,
                }
            }, status=status.HTTP_200_OK)
            
        except Usuario.DoesNotExist:
            return Response({
                'error': 'Usuário não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Erro interno do servidor: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
