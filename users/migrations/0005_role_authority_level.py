from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):
    dependencies = [('users', '0004_early_warning_permissions')]

    operations = [
        migrations.AddField(
            model_name='role',
            name='authority_level',
            field=models.PositiveSmallIntegerField(
                choices=[(0, _('Standard')), (1, _('Staff')), (2, _('Administrator')), (3, _('Super Administrator'))],
                default=0,
                help_text=_('Controls which accounts and roles this role may manage. The name alone never grants authority.'),
                verbose_name=_('Authority Level'),
            ),
        ),
    ]
