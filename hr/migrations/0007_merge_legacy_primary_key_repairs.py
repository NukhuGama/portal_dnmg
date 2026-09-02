"""Merge the normal HR migration line with the idempotent legacy PK repairs."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0006_relationship_integrity'),
        ('hr', '0002_repair_hr_employee_primary_key'),
    ]

    operations = []
