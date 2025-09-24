# Generated manually for ETL 21 - Quadro Societário

from django.db import migrations, models
import django.db.models.deletion
import django.contrib.contenttypes.models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('pessoas', '0004_alter_contrato_unique_together'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuadroSocietario',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('object_id', models.UUIDField(help_text='ID do sócio')),
                ('participacao_percentual', models.DecimalField(blank=True, decimal_places=2, help_text='Percentual de participação do sócio', max_digits=5, null=True)),
                ('quantidade_quotas', models.IntegerField(blank=True, help_text='Quantidade de quotas do sócio', null=True)),
                ('capital_social', models.DecimalField(blank=True, decimal_places=2, help_text='Capital social da empresa', max_digits=15, null=True)),
                ('id_legado_socio', models.CharField(blank=True, db_index=True, help_text='ID do sócio no sistema legado', max_length=50, null=True)),
                ('id_legado_empresa', models.CharField(blank=True, db_index=True, help_text='ID da empresa no sistema legado', max_length=50, null=True)),
                ('data_criacao', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('data_atualizacao', models.DateTimeField(auto_now=True)),
                ('ativo', models.BooleanField(db_index=True, default=True)),
                ('content_type', models.ForeignKey(help_text='Tipo do sócio (PessoaFisica ou PessoaJuridica)', on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('empresa', models.ForeignKey(help_text='Empresa do quadro societário', on_delete=django.db.models.deletion.CASCADE, related_name='quadro_societario', to='pessoas.pessoajuridica')),
            ],
            options={
                'verbose_name': 'Quadro Societário',
                'verbose_name_plural': 'Quadros Societários',
                'indexes': [
                    models.Index(fields=['empresa', 'ativo'], name='pessoas_quadrosocietario_empresa_ativo_idx'),
                    models.Index(fields=['content_type', 'object_id'], name='pessoas_quadrosocietario_content_type_object_id_idx'),
                    models.Index(fields=['id_legado_empresa', 'id_legado_socio'], name='pessoas_quadrosocietario_id_legado_idx'),
                    models.Index(fields=['data_criacao'], name='pessoas_quadrosocietario_data_criacao_idx'),
                ],
                'unique_together': {('empresa', 'content_type', 'object_id')},
            },
        ),
        migrations.CreateModel(
            name='CapitalSocial',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('valor_capital', models.DecimalField(decimal_places=2, help_text='Valor do capital social', max_digits=15)),
                ('data_referencia', models.DateField(db_index=True, help_text='Data de referência do capital social')),
                ('fonte', models.CharField(default='QUADRO_SOCIETARIO', help_text='Fonte dos dados (QUADRO_SOCIETARIO, CONTRATO, etc.)', max_length=50)),
                ('data_criacao', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('data_atualizacao', models.DateTimeField(auto_now=True)),
                ('empresa', models.ForeignKey(help_text='Empresa do capital social', on_delete=django.db.models.deletion.CASCADE, related_name='capital_social_historico', to='pessoas.pessoajuridica')),
            ],
            options={
                'verbose_name': 'Capital Social',
                'verbose_name_plural': 'Capitais Sociais',
                'indexes': [
                    models.Index(fields=['empresa', 'data_referencia'], name='pessoas_capitalsocial_empresa_data_idx'),
                    models.Index(fields=['data_referencia'], name='pessoas_capitalsocial_data_referencia_idx'),
                    models.Index(fields=['fonte'], name='pessoas_capitalsocial_fonte_idx'),
                ],
                'unique_together': {('empresa', 'data_referencia', 'fonte')},
                'ordering': ['-data_referencia'],
            },
        ),
    ]
