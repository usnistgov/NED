import os
import json
from django.core.management.base import BaseCommand
from ned_app.models import (
    Reference,
    Component,
    FragilityModel,
    Experiment,
    ExperimentFragilityModelBridge,
    FragilityCurve,
)
from ned_app.serialization.file_and_path_utiles import build_json_data_file_path
from ned_app.serialization.serializer import ReferenceSerializer


class Command(BaseCommand):
    help = 'Ingests data from JSON files in a strict, hardcoded processing order'

    def handle(self, *args, **options):
        # Define the hardcoded processing order
        processing_order = [
            (Reference, 'reference.json'),
            (Component, 'component.json'),
            (FragilityModel, 'fragility_model.json'),
            (Experiment, 'experiment.json'),
            (ExperimentFragilityModelBridge, 'experiment_fragility_bridge.json'),
            (FragilityCurve, 'fragility_curve.json'),
        ]

        # Process each model and data file in order
        for model_class, data_file in processing_order:
            self.stdout.write(f'Processing {data_file}...')

            if model_class == Reference:
                self._process_references(data_file)

        # Print final success message
        self.stdout.write(
            self.style.SUCCESS('Ingestion command skeleton executed successfully.')
        )

    def _process_references(self, data_file):
        """Process Reference model data with idempotency, validation, and error handling."""
        data_filepath = build_json_data_file_path(data_file)

        # Initialize counters for summary reporting
        created_count = 0
        updated_count = 0
        failed_count = 0

        # Check if file exists
        if not os.path.exists(data_filepath):
            self.stdout.write(self.style.WARNING(f'File not found: {data_filepath}'))
            return

        # Load JSON data
        try:
            with open(data_filepath, 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            self.stderr.write(f'Error: File not found: {data_filepath}')
            return
        except json.JSONDecodeError as ex:
            self.stderr.write(f'Error: Invalid JSON in {data_filepath}: {ex}')
            return

        # Process each record
        for item in data:
            try:
                # Pre-serialization validation: Check for required id field
                if 'id' not in item:
                    raise ValueError('Reference item missing required "id" field')

                record_id = item['id']

                # Pre-serialization validation: Check for csl_data field
                if 'csl_data' not in item or item['csl_data'] is None:
                    raise ValueError(
                        f"Reference item missing required 'csl_data' field: {record_id}"
                    )

                # Validate using ReferenceSerializer
                serializer = ReferenceSerializer(data=item)
                serializer.is_valid(raise_exception=True)

                # Extract validated data and separate lookup key from defaults
                validated_data = serializer.validated_data
                lookup_id = validated_data.pop('id')

                # Idempotent operation: create or update using validated data
                reference, created = Reference.objects.update_or_create(
                    id=lookup_id, defaults=validated_data
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        f"Reference ID '{reference.id}' successfully created"
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        f"Reference ID '{reference.id}' successfully updated"
                    )

            except ValueError as ex:
                failed_count += 1
                self.stderr.write(f'Validation error: {ex}')
            except Exception as ex:
                failed_count += 1
                record_id = item.get('id', 'unknown')
                self.stderr.write(
                    f"Error processing Reference ID '{record_id}': {ex}"
                )

        # Print summary report
        self.stdout.write(
            self.style.SUCCESS(
                f'\nReference processing complete: '
                f'{created_count} created, {updated_count} updated, {failed_count} failed'
            )
        )
