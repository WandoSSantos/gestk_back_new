"""
Views para autenticação JWT com Custom User
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Usuario
from .serializers import CustomTokenObtainPairSerializer, UsuarioSerializer, LoginSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    View customizada para obter tokens JWT com informações da contabilidade
    """
    serializer_class = CustomTokenObtainPairSerializer


class AuthViewSet(ModelViewSet):
    """
    ViewSet para operações de autenticação
    """
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrar usuários pela contabilidade do usuário logado"""
        if self.request.user.contabilidade:
            return Usuario.objects.filter(contabilidade=self.request.user.contabilidade)
        return Usuario.objects.none()
    
    def get_current_user(self, request):
        """Retorna informações do usuário atual"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    def logout(self, request):
        """Logout com blacklist do token"""
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logout realizado com sucesso."})
        except Exception as e:
            return Response(
                {"error": "Token inválido."}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class UsuarioViewSet(ModelViewSet):
    """
    ViewSet para gerenciar usuários
    """
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrar usuários pela contabilidade do usuário logado"""
        if self.request.user.contabilidade:
            return Usuario.objects.filter(contabilidade=self.request.user.contabilidade)
        return Usuario.objects.none()


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Endpoint de login customizado
    """
    serializer = LoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Gerar tokens
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        
        # Adicionar claims customizados
        access['username'] = user.username
        access['email'] = user.email
        access['tipo_usuario'] = user.tipo_usuario
        access['modulos_acessiveis'] = user.modulos_acessiveis
        access['pode_executar_etl'] = user.pode_executar_etl
        access['pode_administrar_usuarios'] = user.pode_administrar_usuarios
        access['pode_ver_dados_sensiveis'] = user.pode_ver_dados_sensiveis
        
        if user.contabilidade:
            access['contabilidade_id'] = str(user.contabilidade.id)
            access['contabilidade_cnpj'] = user.contabilidade.cnpj
            access['contabilidade_razao_social'] = user.contabilidade.razao_social
        else:
            access['contabilidade_id'] = None
            access['contabilidade_cnpj'] = None
            access['contabilidade_razao_social'] = None
        
        return Response({
            'access': str(access),
            'refresh': str(refresh),
            'user': UsuarioSerializer(user).data
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    Endpoint para obter informações do usuário atual
    """
    serializer = UsuarioSerializer(request.user)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Endpoint de logout com blacklist do token
    """
    try:
        refresh_token = request.data.get("refresh")
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({"message": "Logout realizado com sucesso."})
    except Exception as e:
        return Response(
            {"error": "Token inválido."}, 
            status=status.HTTP_400_BAD_REQUEST
        )