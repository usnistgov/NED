import csv
import json
import os
from django.core.management.base import BaseCommand
from django.core.exceptions import FieldDoesNotExist, FieldError
from django.apps import apps
from django.db.models import JSONField, ManyToOneRel, ManyToManyField


class Command(BaseCommand):
    help = 'Query any database table and export results to CSV'

    def add_arguments(self, parser):
        """
        Register command-line arguments.

        Args:
            parser: The argument parser to configure.
        """
        parser.add_argument(
            '--list-models',
            action='store_true',
            help='List all available models in ned_app',
        )
        parser.add_argument(
            '--model',
            type=str,
            required=False,
            help='Model name (e.g., Experiment, Reference, Component)',
        )
        parser.add_argument(
            '--output_file',
            type=str,
            required=False,
            help='Output CSV file path',
        )
        parser.add_argument(
            '--fields',
            type=str,
            default=None,
            help='Comma-separated fields to export (default: all fields)',
        )
        parser.add_argument(
            '--filter',
            type=str,
            default=None,
            help='Filter query as key=value pairs, comma-separated (e.g., reviewer=John,material=Steel)',
        )

    def get_available_models(self):
        """
        Return the names of all models defined in ned_app.

        Returns:
            list[str]: Sorted model class names.
        """
        app_config = apps.get_app_config('ned_app')
        return sorted([model.__name__ for model in app_config.get_models()])

    def handle(self, *args, **options):
        """
        Export a model's rows to CSV, optionally filtered and field-limited.

        Foreign key columns are emitted as their natural key (the value stored
        on the row via the FK's to_field), matching the identifiers used by
        export_data and the import commands. The output file is only opened
        once matching rows are confirmed, so a no-match query never truncates
        an existing file.

        Args:
            *args: Positional arguments (unused).
            **options: Command options (model, output_file, fields, filter,
                list_models).
        """
        if options['list_models']:
            models = self.get_available_models()
            self.stdout.write(self.style.SUCCESS('Available models in ned_app:'))
            for model in models:
                self.stdout.write(f'  - {model}')
            return

        model_name = options['model']
        output_file = options['output_file']

        if not model_name or not output_file:
            self.stderr.write(
                'Error: --model and --output_file are required (use --list-models to see available models)'
            )
            return

        try:
            model = apps.get_model('ned_app', model_name)
        except LookupError:
            self.stderr.write(f'Model {model_name} not found in ned_app')
            self.stderr.write('Use --list-models to see available models')
            return

        # Validate requested field names up front so a typo fails loudly
        # rather than producing a silently-empty column.
        fields = None
        if options['fields']:
            fields = [f.strip() for f in options['fields'].split(',')]
            for field_name in fields:
                try:
                    model._meta.get_field(field_name)
                except FieldDoesNotExist:
                    self.stderr.write(
                        f"Field '{field_name}' does not exist on model '{model_name}'."
                    )
                    return

        # Build queryset with filters
        queryset = model.objects.all()
        if options['filter']:
            filters = {}
            for pair in options['filter'].split(','):
                if '=' not in pair:
                    self.stderr.write(
                        f"Invalid filter '{pair.strip()}'. Expected key=value format."
                    )
                    return
                key, value = pair.split('=', 1)
                filters[key.strip()] = value.strip()
            try:
                queryset = model.objects.filter(**filters)
            except FieldError as ex:
                self.stderr.write(f'Invalid filter: {ex}')
                return

        # Check for results BEFORE opening the file, so a no-match query does
        # not truncate a pre-existing file at the output path.
        if not queryset.exists():
            self.stdout.write('No data found matching criteria')
            return

        # Get field names dynamically
        if fields:
            field_names = fields
        else:
            field_names = [
                f.name
                for f in model._meta.get_fields()
                if not isinstance(f, ManyToOneRel)
                and not isinstance(f, ManyToManyField)
            ]

        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=field_names)
            writer.writeheader()

            for obj in queryset:
                row = {}
                for field_name in field_names:
                    # attname yields the value stored on the row: for a normal
                    # field that is the field value; for a ForeignKey it is the
                    # to_field natural key (e.g. reference_id, component_id).
                    try:
                        field_obj = model._meta.get_field(field_name)
                        value = getattr(obj, field_obj.attname)
                        if isinstance(field_obj, JSONField) and value is not None:
                            value = json.dumps(value)
                        row[field_name] = value
                    except (FieldDoesNotExist, AttributeError):
                        row[field_name] = ''
                writer.writerow(row)

        self.stdout.write(
            self.style.SUCCESS(f'Exported {queryset.count()} rows to {output_file}')
        )
