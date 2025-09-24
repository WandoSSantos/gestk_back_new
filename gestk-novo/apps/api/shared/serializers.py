"""
Serializers Base para API REST

Serializers que implementam multitenancy e validações específicas
"""

from rest_framework import serializers
from django.core.exceptions import ValidationError
from apps.core.models import Contabilidade
import logging

logger = logging.getLogger(__name__)


class BaseSerializer(serializers.ModelSerializer):
    """
    Serializer base que implementa multitenancy
    """
    
    contabilidade_nome = serializers.CharField(source='contabilidade.nome_fantasia', read_only=True)
    
    class Meta:
        abstract = True
    
    def validate_contabilidade(self, value):
        """
        Valida se a contabilidade pertence ao usuário
        """
        if not value:
            raise ValidationError("Contabilidade é obrigatória")
        
        # Verificar se a contabilidade pertence ao usuário
        if hasattr(self.context.get('request'), 'user'):
            user = self.context['request'].user
            if hasattr(user, 'contabilidade') and user.contabilidade != value:
                raise ValidationError("Contabilidade não pertence ao usuário")
        
        return value
    
    def create(self, validated_data):
        """
        Define automaticamente a contabilidade ao criar
        """
        request = self.context.get('request')
        if request and hasattr(request, 'contabilidade'):
            validated_data['contabilidade'] = request.contabilidade
        
        return super().create(validated_data)


class ReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer somente leitura para dashboards
    """
    
    contabilidade_nome = serializers.CharField(source='contabilidade.nome_fantasia', read_only=True)
    
    class Meta:
        abstract = True


class DashboardSerializer(ReadOnlySerializer):
    """
    Serializer base para dashboards com campos calculados
    """
    
    class Meta:
        abstract = True
    
    def to_representation(self, instance):
        """
        Adiciona campos calculados para dashboards
        """
        data = super().to_representation(instance)
        
        # Adicionar campos calculados se necessário
        if hasattr(instance, 'calcular_metricas'):
            data.update(instance.calcular_metricas())
        
        return data


class ContabilidadeSerializer(serializers.ModelSerializer):
    """
    Serializer para Contabilidade
    """
    
    class Meta:
        model = Contabilidade
        fields = [
            'id', 'razao_social', 'nome_fantasia', 'cnpj', 
            'ativo', 'data_criacao', 'data_atualizacao'
        ]
        read_only_fields = ['id', 'data_criacao', 'data_atualizacao']


class ErrorSerializer(serializers.Serializer):
    """
    Serializer para respostas de erro padronizadas
    """
    
    error = serializers.CharField()
    message = serializers.CharField(required=False)
    details = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField(read_only=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'timestamp' not in self.initial_data:
            from django.utils import timezone
            self.initial_data['timestamp'] = timezone.now()


class SuccessSerializer(serializers.Serializer):
    """
    Serializer para respostas de sucesso padronizadas
    """
    
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField(read_only=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'timestamp' not in self.initial_data:
            from django.utils import timezone
            self.initial_data['timestamp'] = timezone.now()
