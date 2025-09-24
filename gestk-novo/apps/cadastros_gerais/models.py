import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

class CNAE(models.Model):
    """Cadastro Nacional de Atividades Econômicas"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(_('Código CNAE'), max_length=20, unique=True)
    descricao = models.TextField(_('Descrição'))
    ativo = models.BooleanField(_('Ativo'), default=True)
    
    class Meta:
        verbose_name = _('CNAE')
        verbose_name_plural = _('CNAEs')
        db_table = 'cadastros_gerais_cnae'
        ordering = ['codigo']
        indexes = [
            models.Index(fields=['codigo']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.descricao}"
