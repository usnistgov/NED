import os
import json
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from ned_app.models import (
    Reference,
    Component,
    FragilityModel,
    Experiment,
    ExperimentFragilityModelBridge,
    FragilityCurve,
)
from ned_app.serialization.file_and_path_utiles import build_json_data_file_path
from ned_app.serialization.serializer import ReferenceSerializer, ComponentSerializer


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
            elif model_class == Component:
                self._process_components(data_file)

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
                serializer = ReferenceSerializer(data=item)
                if serializer.is_valid():
                    instance, created = serializer.save()
                    if created:
                        created_count += 1
                        self.stdout.write(
                            f"Reference ID '{instance.id}' successfully created"
                        )
                    else:
                        updated_count += 1
                        self.stdout.write(
                            f"Reference ID '{instance.id}' successfully updated"
                        )
                else:
                    raise ValidationError(serializer.errors)

            except ValidationError as ex:
                failed_count += 1
                record_id = item.get('id', 'unknown')
                self.stderr.write(
                    f"Error processing Reference ID '{record_id}': {ex}"
                )
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

    def _process_components(self, data_file):
        """Process Component model data with idempotency, validation, and error handling."""
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
                serializer = ComponentSerializer(data=item)
                if serializer.is_valid():
                    instance, created = serializer.save()
                    if created:
                        created_count += 1
                        self.stdout.write(
                            f"Component ID '{instance.id}' successfully created"
                        )
                    else:
                        updated_count += 1
                        self.stdout.write(
                            f"Component ID '{instance.id}' successfully updated"
                        )
                else:
                    raise ValidationError(serializer.errors)

            except ValidationError as ex:
                failed_count += 1
                record_id = item.get('id', 'unknown')
                self.stderr.write(
                    f"Error processing Component ID '{record_id}': {ex}"
                )
            except Exception as ex:
                failed_count += 1
                record_id = item.get('id', 'unknown')
                self.stderr.write(
                    f"Error processing Component ID '{record_id}': {ex}"
                )

        # Print summary report
        self.stdout.write(
            self.style.SUCCESS(
                f'\nComponent processing complete: '
                f'{created_count} created, {updated_count} updated, {failed_count} failed'
            )
        )
