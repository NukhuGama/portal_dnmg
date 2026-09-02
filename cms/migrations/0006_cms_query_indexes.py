from django.db import migrations, models


def verify_existing_values(apps, schema_editor):
    NewsArticle = apps.get_model('cms', 'NewsArticle')
    OfficialBulletin = apps.get_model('cms', 'OfficialBulletin')
    JobOpening = apps.get_model('cms', 'JobOpening')
    invalid = {
        'article status': NewsArticle.objects.exclude(status__in=['DRAFT', 'PUBLISHED', 'ARCHIVED']),
        'bulletin type': OfficialBulletin.objects.exclude(bulletin_type__in=[
            'DAILY_SYNOPTIC', 'MONTHLY_CLIMATE', 'MARINE', 'SEISMIC', 'SPECIAL',
        ]),
        'job employment type': JobOpening.objects.exclude(employment_type__in=[
            'FULL_TIME', 'PART_TIME', 'CONTRACT', 'INTERNSHIP', 'VOLUNTEER',
        ]),
        'job status': JobOpening.objects.exclude(status__in=['DRAFT', 'OPEN', 'CLOSED']),
    }
    failures = [
        f"{label}: {list(queryset.values_list('pk', flat=True)[:10])}"
        for label, queryset in invalid.items()
        if queryset.exists()
    ]
    if failures:
        raise RuntimeError(
            'Cannot apply CMS choice constraints; invalid rows: ' + '; '.join(failures)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0005_newsarticleinlineattachment'),
    ]

    operations = [
        migrations.RunPython(verify_existing_values, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='newsarticle',
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=['DRAFT', 'PUBLISHED', 'ARCHIVED']),
                name='cms_article_status_valid',
            ),
        ),
        migrations.AddIndex(
            model_name='newsarticle',
            index=models.Index(fields=['status', '-published_at', '-created_at'], name='cms_article_status_pub_idx'),
        ),
        migrations.AddIndex(
            model_name='officialbulletin',
            index=models.Index(fields=['bulletin_type', '-publication_date', '-created_at'], name='cms_bulletin_type_date_idx'),
        ),
        migrations.AddConstraint(
            model_name='officialbulletin',
            constraint=models.CheckConstraint(
                condition=models.Q(bulletin_type__in=[
                    'DAILY_SYNOPTIC', 'MONTHLY_CLIMATE', 'MARINE', 'SEISMIC', 'SPECIAL',
                ]),
                name='cms_bulletin_type_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='jobopening',
            constraint=models.CheckConstraint(
                condition=models.Q(employment_type__in=[
                    'FULL_TIME', 'PART_TIME', 'CONTRACT', 'INTERNSHIP', 'VOLUNTEER',
                ]),
                name='cms_job_type_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='jobopening',
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=['DRAFT', 'OPEN', 'CLOSED']),
                name='cms_job_status_valid',
            ),
        ),
        migrations.AddIndex(
            model_name='jobopening',
            index=models.Index(fields=['status', '-created_at'], name='cms_job_status_created_idx'),
        ),
    ]
