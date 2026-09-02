import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0003_bulletin_detail_and_content_media'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsArticleInlineImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='news/content/', verbose_name='Inline Image')),
                ('caption', models.CharField(blank=True, max_length=255, verbose_name='Image Caption')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inline_images', to='cms.newsarticle', verbose_name='Article')),
            ],
            options={
                'verbose_name': 'Inline Article Image',
                'verbose_name_plural': 'Inline Article Images',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
