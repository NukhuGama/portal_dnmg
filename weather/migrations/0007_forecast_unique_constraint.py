from django.db import migrations, models
from django.db.models import Count


def replace_legacy_forecast_unique_constraint(apps, schema_editor):
    """Support databases where the original unique_together was never created.

    Fresh installations have Django's unnamed legacy unique constraint, while
    older production tables may have no such constraint.  In both cases, leave
    one explicit, stable constraint name for the current model state.
    """
    WeatherForecast = apps.get_model('weather', 'WeatherForecast')
    duplicates = list(
        WeatherForecast.objects.values('municipality', 'forecast_date')
        .annotate(total=Count('pk'))
        .filter(total__gt=1)[:10]
    )
    if duplicates:
        raise RuntimeError(
            'Cannot add the weather forecast uniqueness rule because duplicate '
            f'municipality/date rows exist: {duplicates}. Correct or merge them, then rerun migrate.'
        )

    table_name = WeatherForecast._meta.db_table
    quote_name = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT constraint_name, array_agg(column_name ORDER BY position)
            FROM (
                SELECT c.conname AS constraint_name,
                       a.attname AS column_name,
                       key_columns.ordinality AS position
                FROM pg_constraint c
                JOIN unnest(c.conkey) WITH ORDINALITY AS key_columns(attnum, ordinality)
                    ON TRUE
                JOIN pg_attribute a
                    ON a.attrelid = c.conrelid AND a.attnum = key_columns.attnum
                WHERE c.conrelid = %s::regclass AND c.contype = 'u'
            ) unique_columns
            GROUP BY constraint_name
            """,
            [table_name],
        )
        legacy_constraints = [
            name for name, columns in cursor.fetchall()
            if columns == ['municipality', 'forecast_date']
        ]

    for constraint_name in legacy_constraints:
        schema_editor.execute(
            f'ALTER TABLE {quote_name(table_name)} '
            f'DROP CONSTRAINT {quote_name(constraint_name)}'
        )

    schema_editor.execute(
        f'ALTER TABLE {quote_name(table_name)} '
        'ADD CONSTRAINT weather_forecast_municipality_date_unique '
        'UNIQUE (municipality, forecast_date)'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('weather', '0006_weather_schema_integrity'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    replace_legacy_forecast_unique_constraint,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AlterUniqueTogether(
                    name='weatherforecast',
                    unique_together=set(),
                ),
                migrations.AddConstraint(
                    model_name='weatherforecast',
                    constraint=models.UniqueConstraint(
                        fields=('municipality', 'forecast_date'),
                        name='weather_forecast_municipality_date_unique',
                    ),
                ),
            ],
        ),
    ]
