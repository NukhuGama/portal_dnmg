"""Restore PK/FK constraints that may be absent from pre-migration databases.

Some early production databases were created from a legacy schema and later had
Django migrations marked as applied.  Those tables have the expected columns,
but PostgreSQL does not enforce all of Django's primary-key and foreign-key
relationships. This migration validates application data before adding each
missing constraint; it never deletes application rows.
"""

from django.db import migrations


def _quoted(schema_editor, value):
    return schema_editor.quote_name(value)


def _constraint_name(table_name, column_name, suffix):
    """Produce deterministic PostgreSQL-safe constraint names (max 63 chars)."""
    name = f'{table_name}_{column_name}_{suffix}'
    return name[:63]


def _repair_legacy_content_types(connection, cursor):
    """Restore unambiguous ContentType IDs and their auth_permission links."""
    constraints = connection.introspection.get_constraints(cursor, 'django_content_type')
    if any(metadata['primary_key'] for metadata in constraints.values()):
        return

    cursor.execute(
        'SELECT app_label, model FROM django_content_type '
        'GROUP BY app_label, model HAVING COUNT(*) > 1 LIMIT 10'
    )
    duplicate_natural_keys = cursor.fetchall()
    if duplicate_natural_keys:
        raise RuntimeError(
            'Cannot repair django_content_type because duplicate (app_label, model) records exist '
            f'(examples: {duplicate_natural_keys}).'
        )

    # A permission can be reassigned safely only if its standard Django
    # codename identifies exactly one content-type model. Check first so no
    # permission is changed on an ambiguous legacy database.
    cursor.execute(
        '''
        SELECT permission.ctid, permission.id, permission.codename
        FROM auth_permission AS permission
        LEFT JOIN django_content_type AS content_type
          ON permission.codename IN (
              'add_' || content_type.model,
              'change_' || content_type.model,
              'delete_' || content_type.model,
              'view_' || content_type.model
          )
        GROUP BY permission.ctid, permission.id, permission.codename
        HAVING COUNT(content_type.ctid) <> 1
        LIMIT 10
        '''
    )
    unmatched_permissions = cursor.fetchall()
    if unmatched_permissions:
        raise RuntimeError(
            'Cannot repair django_content_type because some auth_permission rows cannot be '
            'mapped unambiguously by codename (examples: '
            f'{unmatched_permissions}).'
        )

    # ContentType IDs are internal surrogate values. Existing foreign-key
    # metadata is absent, so renumber all content types before reconnecting
    # auth_permission to the correct row using each permission's codename.
    cursor.execute(
        '''
        WITH numbered AS (
            SELECT ctid,
                   ROW_NUMBER() OVER (ORDER BY app_label, model, id, ctid) AS new_id
            FROM django_content_type
        )
        UPDATE django_content_type AS target
        SET id = numbered.new_id
        FROM numbered
        WHERE target.ctid = numbered.ctid
        '''
    )
    cursor.execute(
        '''
        UPDATE auth_permission AS permission
        SET content_type_id = content_type.id
        FROM django_content_type AS content_type
        WHERE permission.codename IN (
            'add_' || content_type.model,
            'change_' || content_type.model,
            'delete_' || content_type.model,
            'view_' || content_type.model
        )
        '''
    )
    cursor.execute("SELECT pg_get_serial_sequence('django_content_type', 'id')")
    sequence_name = cursor.fetchone()[0]
    if sequence_name:
        cursor.execute('SELECT COUNT(*), MAX(id) FROM django_content_type')
        row_count, maximum_id = cursor.fetchone()
        cursor.execute(
            'SELECT setval(%s::regclass, %s, %s)',
            [sequence_name, maximum_id or 1, bool(row_count)],
        )
    cursor.execute(
        'ALTER TABLE django_content_type '
        'ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id)'
    )
    cursor.execute(
        'ALTER TABLE django_content_type '
        'ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq '
        'UNIQUE (app_label, model)'
    )


def _repair_legacy_audit_log_ids(connection, cursor):
    """Restore unique IDs for AuditLog, which has no inbound model relation."""
    constraints = connection.introspection.get_constraints(cursor, 'users_auditlog')
    if any(metadata['primary_key'] for metadata in constraints.values()):
        return

    cursor.execute('SELECT id FROM users_auditlog GROUP BY id HAVING COUNT(*) > 1 LIMIT 10')
    duplicates = cursor.fetchall()
    cursor.execute('SELECT 1 FROM users_auditlog WHERE id IS NULL LIMIT 1')
    has_null_ids = cursor.fetchone() is not None
    if not duplicates and not has_null_ids:
        return

    # AuditLog is append-only event history; its ID has no declared inbound
    # relation. Keep every event and assign a stable chronological ID instead
    # of deleting duplicate rows.
    cursor.execute(
        '''
        WITH numbered AS (
            SELECT ctid,
                   ROW_NUMBER() OVER (ORDER BY timestamp, id, ctid) AS new_id
            FROM users_auditlog
        )
        UPDATE users_auditlog AS target
        SET id = numbered.new_id
        FROM numbered
        WHERE target.ctid = numbered.ctid
        '''
    )
    cursor.execute("SELECT pg_get_serial_sequence('users_auditlog', 'id')")
    sequence_name = cursor.fetchone()[0]
    if sequence_name:
        cursor.execute('SELECT COUNT(*), MAX(id) FROM users_auditlog')
        row_count, maximum_id = cursor.fetchone()
        cursor.execute(
            'SELECT setval(%s::regclass, %s, %s)',
            [sequence_name, maximum_id or 1, bool(row_count)],
        )


def _repair_legacy_weather_observation_ids(connection, cursor):
    """Restore unique IDs for observation rows without discarding telemetry."""
    constraints = connection.introspection.get_constraints(cursor, 'weather_weatherobservation')
    if any(metadata['primary_key'] for metadata in constraints.values()):
        return

    cursor.execute(
        'SELECT id FROM weather_weatherobservation GROUP BY id HAVING COUNT(*) > 1 LIMIT 10'
    )
    duplicates = cursor.fetchall()
    cursor.execute('SELECT 1 FROM weather_weatherobservation WHERE id IS NULL LIMIT 1')
    has_null_ids = cursor.fetchone() is not None
    if not duplicates and not has_null_ids:
        return

    # No installed model points to WeatherObservation. Its ID is a surrogate
    # key, so retain all source telemetry and assign stable chronological IDs.
    cursor.execute(
        '''
        WITH numbered AS (
            SELECT ctid,
                   ROW_NUMBER() OVER (
                       ORDER BY station_id, recorded_at, created_at, id, ctid
                   ) AS new_id
            FROM weather_weatherobservation
        )
        UPDATE weather_weatherobservation AS target
        SET id = numbered.new_id
        FROM numbered
        WHERE target.ctid = numbered.ctid
        '''
    )
    cursor.execute("SELECT pg_get_serial_sequence('weather_weatherobservation', 'id')")
    sequence_name = cursor.fetchone()[0]
    if sequence_name:
        cursor.execute('SELECT COUNT(*), MAX(id) FROM weather_weatherobservation')
        row_count, maximum_id = cursor.fetchone()
        cursor.execute(
            'SELECT setval(%s::regclass, %s, %s)',
            [sequence_name, maximum_id or 1, bool(row_count)],
        )


def repair_legacy_database_constraints(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'postgresql':
        raise RuntimeError('Legacy constraint repair is supported only on PostgreSQL.')

    models = sorted(
        (
            model for model in apps.get_models(include_auto_created=True)
            if model._meta.managed and not model._meta.proxy
        ),
        key=lambda model: model._meta.db_table,
    )

    with connection.cursor() as cursor:
        table_names = set(connection.introspection.table_names(cursor))
        models = [model for model in models if model._meta.db_table in table_names]

        # django_migrations is maintained by Django but is not represented by
        # an installed model, so repair it explicitly before the model loop.
        if 'django_migrations' in table_names:
            constraints = connection.introspection.get_constraints(cursor, 'django_migrations')
            if not any(metadata['primary_key'] for metadata in constraints.values()):
                cursor.execute(
                    'SELECT app, name FROM django_migrations '
                    'GROUP BY app, name HAVING COUNT(*) > 1 LIMIT 10'
                )
                duplicate_records = cursor.fetchall()
                if duplicate_records:
                    raise RuntimeError(
                        'Cannot repair django_migrations because duplicate migration records exist '
                        f'(examples: {duplicate_records}).'
                    )
                cursor.execute(
                    'SELECT id FROM django_migrations GROUP BY id HAVING COUNT(*) > 1 LIMIT 10'
                )
                duplicates = [row[0] for row in cursor.fetchall()]
                cursor.execute('SELECT 1 FROM django_migrations WHERE id IS NULL LIMIT 1')
                has_null_ids = cursor.fetchone() is not None
                if duplicates or has_null_ids:
                    # `id` is only Django's internal surrogate key here; no
                    # application table references it. Renumbering preserves
                    # every (app, name, applied) migration-history record.
                    cursor.execute(
                        '''
                        WITH numbered AS (
                            SELECT ctid,
                                   ROW_NUMBER() OVER (ORDER BY app, name, id NULLS LAST, ctid) AS new_id
                            FROM django_migrations
                        )
                        UPDATE django_migrations AS target
                        SET id = numbered.new_id
                        FROM numbered
                        WHERE target.ctid = numbered.ctid
                        '''
                    )
                cursor.execute("SELECT pg_get_serial_sequence('django_migrations', 'id')")
                sequence_name = cursor.fetchone()[0]
                if sequence_name:
                    cursor.execute('SELECT COUNT(*), MAX(id) FROM django_migrations')
                    row_count, maximum_id = cursor.fetchone()
                    cursor.execute(
                        'SELECT setval(%s::regclass, %s, %s)',
                        [sequence_name, maximum_id or 1, bool(row_count)],
                    )
                cursor.execute(
                    'ALTER TABLE django_migrations '
                    'ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id)'
                )

        if {'django_content_type', 'auth_permission'} <= table_names:
            _repair_legacy_content_types(connection, cursor)

        if 'users_auditlog' in table_names:
            _repair_legacy_audit_log_ids(connection, cursor)

        if 'weather_weatherobservation' in table_names:
            _repair_legacy_weather_observation_ids(connection, cursor)

        # Referenced columns must be unique before PostgreSQL can accept FKs.
        for model in models:
            table_name = model._meta.db_table
            pk_column = model._meta.pk.column
            quoted_table = _quoted(schema_editor, table_name)
            quoted_column = _quoted(schema_editor, pk_column)

            constraints = connection.introspection.get_constraints(cursor, table_name)
            if any(metadata['primary_key'] for metadata in constraints.values()):
                continue

            cursor.execute(
                f'SELECT {quoted_column} FROM {quoted_table} '
                f'WHERE {quoted_column} IS NULL LIMIT 10'
            )
            null_values = [row[0] for row in cursor.fetchall()]
            if null_values:
                raise RuntimeError(
                    f'Cannot add primary key to {table_name}.{pk_column}: NULL values found '
                    f'(examples: {null_values}).'
                )

            cursor.execute(
                f'SELECT {quoted_column} FROM {quoted_table} '
                f'GROUP BY {quoted_column} HAVING COUNT(*) > 1 LIMIT 10'
            )
            duplicates = [row[0] for row in cursor.fetchall()]
            if duplicates:
                raise RuntimeError(
                    f'Cannot add primary key to {table_name}.{pk_column}: duplicate values found '
                    f'(examples: {duplicates}).'
                )

            constraint_name = _constraint_name(table_name, pk_column, 'pkey')
            cursor.execute(
                f'ALTER TABLE {quoted_table} ADD CONSTRAINT {_quoted(schema_editor, constraint_name)} '
                f'PRIMARY KEY ({quoted_column})'
            )

        # Add every FK declared by the current Django migration state.  The
        # orphan check gives an actionable error before PostgreSQL changes the
        # schema.  Django enforces on_delete behavior in its deletion collector,
        # so PostgreSQL's standard NO ACTION is appropriate here.
        for model in models:
            table_name = model._meta.db_table
            quoted_table = _quoted(schema_editor, table_name)
            constraints = connection.introspection.get_constraints(cursor, table_name)

            for field in model._meta.fields:
                if not field.many_to_one and not field.one_to_one:
                    continue

                remote_model = field.remote_field.model
                remote_table = remote_model._meta.db_table
                if remote_table not in table_names:
                    raise RuntimeError(
                        f'Cannot add {table_name}.{field.column} foreign key: '
                        f'referenced table {remote_table} does not exist.'
                    )
                if any(
                    metadata['foreign_key'] == (remote_table, field.target_field.column)
                    and metadata['columns'] == [field.column]
                    for metadata in constraints.values()
                ):
                    continue

                quoted_column = _quoted(schema_editor, field.column)
                quoted_remote_table = _quoted(schema_editor, remote_table)
                quoted_remote_column = _quoted(schema_editor, field.target_field.column)
                cursor.execute(
                    f'SELECT source.{quoted_column} FROM {quoted_table} AS source '
                    f'LEFT JOIN {quoted_remote_table} AS target '
                    f'ON target.{quoted_remote_column} = source.{quoted_column} '
                    f'WHERE source.{quoted_column} IS NOT NULL '
                    f'AND target.{quoted_remote_column} IS NULL LIMIT 10'
                )
                orphan_values = [row[0] for row in cursor.fetchall()]
                if orphan_values:
                    raise RuntimeError(
                        f'Cannot add foreign key {table_name}.{field.column} -> '
                        f'{remote_table}.{field.target_field.column}: orphan values found '
                        f'(examples: {orphan_values}).'
                    )

                constraint_name = _constraint_name(table_name, field.column, 'fk')
                cursor.execute(
                    f'ALTER TABLE {quoted_table} '
                    f'ADD CONSTRAINT {_quoted(schema_editor, constraint_name)} '
                    f'FOREIGN KEY ({quoted_column}) '
                    f'REFERENCES {quoted_remote_table} ({quoted_remote_column}) '
                    'DEFERRABLE INITIALLY DEFERRED'
                )


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('cms', '0008_alter_officialbulletin_bulletin_type'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('hr', '0007_merge_legacy_primary_key_repairs'),
        ('sessions', '0001_initial'),
        ('users', '0004_early_warning_permissions'),
        ('weather', '0007_forecast_unique_constraint'),
    ]

    operations = [
        migrations.RunPython(repair_legacy_database_constraints, migrations.RunPython.noop),
    ]
