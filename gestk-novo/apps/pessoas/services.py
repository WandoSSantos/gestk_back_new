from .models import PessoaFisica, PessoaJuridica, Contrato
from core.models import Contabilidade
from django.contrib.contenttypes.models import ContentType
import re

def get_or_create_parceiro(documento: str, nome: str):
    """
    Busca um parceiro pelo documento (CPF/CNPJ) em todo o sistema.
    Se não encontrar, cria um novo.
    Retorna a instância do parceiro e um booleano indicando se foi criado.
    """
    doc_limpo = re.sub(r'\D', '', (documento or ''))
    parceiro = None
    created = False

    if not doc_limpo:
        raise ValueError("Documento (CPF/CNPJ) não pode ser vazio.")

    if len(doc_limpo) == 11:
        # Pessoa Física
        parceiro, created = PessoaFisica.objects.get_or_create(
            cpf=doc_limpo,
            defaults={'nome_completo': nome}
        )
    elif len(doc_limpo) == 14:
        # Pessoa Jurídica
        parceiro, created = PessoaJuridica.objects.get_or_create(
            cnpj=doc_limpo,
            defaults={'razao_social': nome, 'nome_fantasia': nome}
        )
    else:
        raise ValueError(f"Documento '{documento}' é inválido.")

    return parceiro, created

def associar_cliente_a_contabilidade(cliente, contabilidade: Contabilidade, id_legado_contrato: str = None):
    """
    Cria um Contrato para formalizar a relação entre um cliente (PF ou PJ) e uma Contabilidade.
    A função é idempotente: se o contrato já existe, ele apenas o retorna.
    """
    content_type = ContentType.objects.get_for_model(cliente)
    
    contrato, created = Contrato.objects.get_or_create(
        content_type=content_type,
        object_id=cliente.id,
        contabilidade=contabilidade,
        defaults={'id_legado': id_legado_contrato}
    )
    return contrato, created
