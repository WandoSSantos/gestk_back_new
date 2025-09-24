"""
Serializers para autenticação JWT customizada
"""

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from apps.core.models import Usuario


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer customizado para incluir informações da contabilidade no token JWT
    """
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Adicionar claims customizados
        token['username'] = user.username
        token['email'] = user.email
        token['tipo_usuario'] = user.tipo_usuario
        token['modulos_acessiveis'] = user.modulos_acessiveis
        token['pode_executar_etl'] = user.pode_executar_etl
        token['pode_administrar_usuarios'] = user.pode_administrar_usuarios
        token['pode_ver_dados_sensiveis'] = user.pode_ver_dados_sensiveis
        
        # Informações da contabilidade (tenant)
        if user.contabilidade:
            token['contabilidade_id'] = str(user.contabilidade.id)
            token['contabilidade_cnpj'] = user.contabilidade.cnpj
            token['contabilidade_razao_social'] = user.contabilidade.razao_social
        else:
            token['contabilidade_id'] = None
            token['contabilidade_cnpj'] = None
            token['contabilidade_razao_social'] = None
        
        return token


class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer para usuários com informações da contabilidade
    """
    
    contabilidade_razao_social = serializers.CharField(
        source='contabilidade.razao_social',
        read_only=True
    )
    
    contabilidade_cnpj = serializers.CharField(
        source='contabilidade.cnpj',
        read_only=True
    )
    
    # Campo customizado para IP com validação adequada
    ip_ultimo_acesso = serializers.IPAddressField(
        protocol='both',
        allow_blank=True,
        required=False
    )
    
    class Meta:
        model = Usuario
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'tipo_usuario',
            'modulos_acessiveis',
            'pode_executar_etl',
            'pode_administrar_usuarios',
            'pode_ver_dados_sensiveis',
            'ativo',
            'contabilidade_id',
            'contabilidade_razao_social',
            'contabilidade_cnpj',
            'data_ultima_atividade',
            'ip_ultimo_acesso',
            'mfa_enabled',
        ]
        read_only_fields = [
            'id',
            'data_ultima_atividade',
        ]


class LoginSerializer(serializers.Serializer):
    """
    Serializer para login
    """
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            # Verificar se o usuário existe e está ativo
            try:
                user = Usuario.objects.get(username=username)
                if not user.is_active:
                    raise serializers.ValidationError('Usuário inativo.')
                if not user.check_password(password):
                    raise serializers.ValidationError('Credenciais inválidas.')
            except Usuario.DoesNotExist:
                raise serializers.ValidationError('Credenciais inválidas.')
            
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Username e password são obrigatórios.')
        
        return attrs
