import django.db.models.deletion
from django.db import migrations, models


def swap_primary_key(apps, schema_editor):
    """Swap primary key from employee_id to auto-increment id.
    Handles PostgreSQL and SQLite differently."""
    connection = schema_editor.connection
    cursor = connection.cursor()

    if connection.vendor == 'postgresql':
        # PostgreSQL: alter table in-place
        cursor.execute(
            "ALTER TABLE employees_salary DROP CONSTRAINT employees_salary_pkey;"
        )
        cursor.execute(
            "ALTER TABLE employees_salary ADD COLUMN id BIGSERIAL PRIMARY KEY;"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "employees_salary_employee_id_effective_date_uniq "
            "ON employees_salary (employee_id, effective_date);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS employees_salary_employee_id_idx "
            "ON employees_salary (employee_id);"
        )
    elif connection.vendor == 'sqlite':
        # SQLite: must recreate the table
        cursor.execute(
            "CREATE TABLE employees_salary_new ("
            "  id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,"
            "  employee_id BIGINT NOT NULL REFERENCES employees_employee(id),"
            "  base_amount DECIMAL NOT NULL,"
            "  effective_date DATE NOT NULL"
            ");"
        )
        cursor.execute(
            "INSERT INTO employees_salary_new "
            "(employee_id, base_amount, effective_date) "
            "SELECT employee_id, base_amount, effective_date "
            "FROM employees_salary;"
        )
        cursor.execute("DROP TABLE employees_salary;")
        cursor.execute(
            "ALTER TABLE employees_salary_new RENAME TO employees_salary;"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX "
            "employees_salary_employee_id_effective_date_uniq "
            "ON employees_salary (employee_id, effective_date);"
        )
        cursor.execute(
            "CREATE INDEX employees_salary_employee_id_idx "
            "ON employees_salary (employee_id);"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0017_productcreationlog_is_suspect_duplicate'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name='salary',
                    options={
                        'ordering': ['-effective_date'],
                        'verbose_name_plural': 'Salaries',
                    },
                ),
                migrations.AddField(
                    model_name='salary',
                    name='id',
                    field=models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                migrations.AlterField(
                    model_name='salary',
                    name='employee',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='salaries',
                        to='employees.employee',
                    ),
                ),
                migrations.AlterUniqueTogether(
                    name='salary',
                    unique_together={('employee', 'effective_date')},
                ),
            ],
            database_operations=[
                migrations.RunPython(swap_primary_key, migrations.RunPython.noop),
            ],
        ),
    ]
