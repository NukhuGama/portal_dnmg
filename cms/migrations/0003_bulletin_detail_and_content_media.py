from django.db import migrations, models
import django.db.models.deletion
import django.utils.text


def populate_bulletin_slugs(apps, schema_editor):
    OfficialBulletin = apps.get_model('cms', 'OfficialBulletin')
    for bulletin in OfficialBulletin.objects.order_by('pk'):
        base_slug = django.utils.text.slugify(bulletin.title) or f'bulletin-{bulletin.pk}'
        slug = base_slug
        number = 2
        while OfficialBulletin.objects.filter(slug=slug).exclude(pk=bulletin.pk).exists():
            slug = f'{base_slug}-{number}'
            number += 1
        bulletin.slug = slug
        bulletin.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0002_jobopening'),
    ]

    operations = [
        migrations.AddField(
            model_name='officialbulletin',
            name='slug',
            field=models.SlugField(blank=True, max_length=280, null=True, unique=True, verbose_name='Slug'),
        ),
        migrations.RunPython(populate_bulletin_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='officialbulletin',
            name='slug',
            field=models.SlugField(blank=True, max_length=280, unique=True, verbose_name='Slug'),
        ),
        migrations.CreateModel(
            name='JobOpeningAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='careers/documents/', verbose_name='Supporting File')),
                ('title', models.CharField(blank=True, max_length=255, verbose_name='File Title')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('job_opening', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='cms.jobopening', verbose_name='Job Opening')),
            ],
            options={
                'verbose_name': 'Job Opening Attachment',
                'verbose_name_plural': 'Job Opening Attachments',
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.CreateModel(
            name='NewsArticleAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='news/documents/', verbose_name='Supporting File')),
                ('title', models.CharField(blank=True, max_length=255, verbose_name='File Title')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='cms.newsarticle', verbose_name='Article')),
            ],
            options={
                'verbose_name': 'News Article Attachment',
                'verbose_name_plural': 'News Article Attachments',
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.CreateModel(
            name='NewsArticleImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='news/images/', verbose_name='Image')),
                ('caption', models.CharField(blank=True, max_length=255, verbose_name='Caption / Label')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='cms.newsarticle', verbose_name='Article')),
            ],
            options={
                'verbose_name': 'News Article Image',
                'verbose_name_plural': 'News Article Images',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
