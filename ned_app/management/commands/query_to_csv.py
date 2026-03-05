import csv
import os
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db.models import ManyToOneRel, ManyToManyField


class Command(BaseCommand):
    help = 'Query any database table and export results to CSV'

    def add_arguments(self, parser):
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
        """Return list of all available models in ned_app"""
        app_config = apps.get_app_config('ned_app')
        return sorted([model.__name__ for model in app_config.get_models()])
        
    def handle(self, *args, **options):
        # Handle --list-models flag
        if options['list_models']:
            models = self.get_available_models()
            self.stdout.write(self.style.SUCCESS('Available models in ned_app:'))
            for model in models:
                self.stdout.write(f'  • {model}')
            return

        model_name = options['model']
        output_file = options['output_file']

        # Validate required arguments
        if not model_name or not output_file:
            self.stderr.write('Error: --model and --output_file are required (use --list-models to see available models)')
            return

        fields = options['fields'].split(',') if options['fields'] else None

        # Get the model class
        try:
            model = apps.get_model('ned_app', model_name)
        except LookupError:
            self.stderr.write(f'Model {model_name} not found in ned_app')
            self.stderr.write('Use --list-models to see available models')
            return

        # Build queryset with filters
        queryset = model.objects.all()
        if options['filter']:
            filters = {}
            for pair in options['filter'].split(','):
                key, value = pair.split('=')
                filters[key.strip()] = value.strip()
            queryset = queryset.filter(**filters)

        # Create output directory
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

        # Export to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            if not queryset.exists():
                self.stdout.write('No data found matching criteria')
                return

            # Get field names dynamically
            if fields:
                field_names = fields
            else:
                field_names = [
                    f.name for f in model._meta.get_fields()
                    if not isinstance(f, ManyToOneRel) and not isinstance(f, ManyToManyField)
                ]

            writer = csv.DictWriter(f, fieldnames=field_names)
            writer.writeheader()

            for obj in queryset:
                row = {}
                for field_name in field_names:
                   # Get the field definition to check if it's a ForeignKey
                   try:
                       field_obj = model._meta.get_field(field_name)
                   except Exception:
                       row[field_name] = ''
                       continue
                   
                   # Get the field value from the object
                   field_value = getattr(obj, field_name, None)
                   
                   # If it's a ForeignKey, get the primary key of the related object
                   if hasattr(field_obj, 'related_model') and field_obj.related_model is not None and field_value is not None:
                       row[field_name] = getattr(field_value, field_obj.related_model._meta.pk.name)
                   else:
                       row[field_name] = field_value
                writer.writerow(row)

        self.stdout.write(
            self.style.SUCCESS(
                f'Exported {queryset.count()} rows to {output_file}'
            )
        )