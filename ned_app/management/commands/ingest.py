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
    """
    Django management command to ingest data from canonical JSON files.

    This command reads JSON files for all models and creates or updates
    database records using serializers for validation and idempotent processing.
    """

    help = 'Ingests data from JSON files using a generic, configurable processor.'

    def handle(self, *args, **options):
        """
        Execute the ingestion command.

        Processes all configured JSON data files in sequence, creating or updating
        database records as needed.

        Args:
            *args: Positional arguments (unused).
            **options: Command options (unused).
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
        Process a JSON data file for a given model.

        Handles file reading, data validation, idempotent create/update operations,
        and result reporting.

        Args:
            model_class: The Django model class to process.
            serializer_class: The serializer class for validation and saving.
            data_file (str): The name of the JSON file to process.
            lookup_field (list): List of field names used to identify existing records.
        """
        model_name = model_class.__name__
        self.stdout.write(f'--- Processing {model_name} from {data_file} ---')

        data_filepath = build_json_data_file_path(data_file)
        created_count, updated_count, failed_count = 0, 0, 0

        if not os.path.exists(data_filepath):
            self.stdout.write(
                self.style.WARNING(f'File not found, skipping: {data_filepath}')
            )
            return

        try:
            with open(data_filepath, 'r') as file:
                data = json.load(file)
        except json.JSONDecodeError as ex:
            self.stderr.write(f'Error: Invalid JSON in {data_filepath}: {ex}')
            return

        for item in data:
            try:
                lookup_params = {field: item.get(field) for field in lookup_field}
                instance = None

                if all(lookup_params.values()):
                    try:
                        instance = model_class.objects.get(**lookup_params)
                    except model_class.DoesNotExist:
                        instance = None

                if instance:
                    serializer = serializer_class(instance, data=item)
                else:
                    serializer = serializer_class(data=item)

                serializer.is_valid(raise_exception=True)
                serializer.save()

                if instance:
                    updated_count += 1
                else:
                    created_count += 1

            except (ValidationError, Exception) as ex:
                failed_count += 1
                record_id = item.get('id') or item.get('component_id') or 'unknown'
                self.stderr.write(
                    f"Error processing {model_name} record '{record_id}': {ex}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'{model_name} processing complete: '
                f'{created_count} created, {updated_count} updated, {failed_count} failed.\n'
            )
        )
