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
from ned_app.serialization.serializer import (
    ReferenceSerializer,
    ComponentSerializer,
    FragilityModelSerializer,
    ExperimentSerializer,
    ExperimentFragilityModelBridgeSerializer,
    FragilityCurveSerializer,
)


class Command(BaseCommand):
    help = 'Ingests data from JSON files using a generic, configurable processor.'

    def handle(self, *args, **options):
        """
        Main entry point for the command. Defines the ingestion configuration
        and iterates through it, calling the generic processor.
        """
        processing_config = [
            {
                'model': Reference,
                'serializer': ReferenceSerializer,
                'file': 'reference.json',
                'lookup_field': ['id'],
            },
            {
                'model': Component,
                'serializer': ComponentSerializer,
                'file': 'component.json',
                'lookup_field': ['component_id'],
            },
            {
                'model': FragilityModel,
                'serializer': FragilityModelSerializer,
                'file': 'fragility_model.json',
                'lookup_field': ['id'],
            },
            {
                'model': Experiment,
                'serializer': ExperimentSerializer,
                'file': 'experiment.json',
                'lookup_field': ['id'],
            },
            {
                'model': ExperimentFragilityModelBridge,
                'serializer': ExperimentFragilityModelBridgeSerializer,
                'file': 'experiment_fragility_model_bridge.json',
                'lookup_field': ['experiment', 'fragility_model'],
            },
            {
                'model': FragilityCurve,
                'serializer': FragilityCurveSerializer,
                'file': 'fragility_curve.json',
                'lookup_field': ['fragility_model', 'ds_rank'],
            },
        ]

        for config in processing_config:
            self._process_data_file(
                model_class=config['model'],
                serializer_class=config['serializer'],
                data_file=config['file'],
                lookup_field=config['lookup_field'],
            )

        self.stdout.write(
            self.style.SUCCESS('\nAll data ingestion tasks completed successfully.')
        )

    def _process_data_file(
        self, model_class, serializer_class, data_file, lookup_field
    ):
        """
        A generic function to process a JSON data file for a given model.
        It handles file reading, data validation, serialization, and reporting.
        """
        model_name = model_class.__name__
        self.stdout.write(f'--- Processing {model_name} from {data_file} ---')

        data_filepath = build_json_data_file_path(data_file)
        created_count, updated_count, failed_count = 0, 0, 0

        # Check for file existence
        if not os.path.exists(data_filepath):
            self.stdout.write(
                self.style.WARNING(f'File not found, skipping: {data_filepath}')
            )
            return

        # Load and parse JSON data
        try:
            with open(data_filepath, 'r') as file:
                data = json.load(file)
        except json.JSONDecodeError as ex:
            self.stderr.write(f'Error: Invalid JSON in {data_filepath}: {ex}')
            return

        # Process each record in the data file
        for item in data:
            try:
                # Build a dictionary of lookup parameters from the config
                # e.g., {'experiment': 'exp-001', 'fragility_model': 'fm-001'}
                lookup_params = {field: item.get(field) for field in lookup_field}
                instance = None

                # Proceed only if all key values were found in the data
                if all(lookup_params.values()):
                    try:
                        instance = model_class.objects.get(**lookup_params)
                    except model_class.DoesNotExist:
                        instance = None

                if instance:
                    serializer = serializer_class(instance, data=item)
                else:
                    serializer = serializer_class(data=item)

                # Use raise_exception=True to simplify error handling
                serializer.is_valid(raise_exception=True)
                serializer.save()

                if instance:
                    updated_count += 1
                else:
                    created_count += 1

            except (ValidationError, Exception) as ex:
                failed_count += 1
                # Attempt to get a meaningful identifier for the failing record for logging
                record_id = item.get('id') or item.get('component_id') or 'unknown'
                self.stderr.write(
                    f"Error processing {model_name} record '{record_id}': {ex}"
                )
                # raise ex

        # Print summary report for the current model
        self.stdout.write(
            self.style.SUCCESS(
                f'{model_name} processing complete: '
                f'{created_count} created, {updated_count} updated, {failed_count} failed.\n'
            )
        )
