import os
import tempfile
from unittest.mock import patch
from django.core.management import call_command
from django.test import TestCase, tag
from ned_app.models import Reference, Component


@tag('integrity')
class DataIntegrityTests(TestCase):
    fixtures = ['initial_data.json']

    def setUp(self):
        self.temp_dir_path = tempfile.mkdtemp()

    def test_db_round_trip(self):
        # Capture initial state
        initial_references = list(Reference.objects.all())
        initial_components = list(Component.objects.all())

        # Execute export_data command
        call_command('export_data', output_dir=self.temp_dir_path)

        # Execute flush command
        call_command('flush', '--noinput')

        # Execute ingest command with mocked path
        def mock_build_json_data_file_path(filename):
            return os.path.join(self.temp_dir_path, filename)

        with patch('ned_app.serialization.file_and_path_utiles.build_json_data_file_path', side_effect=mock_build_json_data_file_path):
            call_command('ingest')

        # Retrieve final state
        final_references = list(Reference.objects.all())
        final_components = list(Component.objects.all())

        # Assert record counts
        self.assertEqual(len(initial_references), len(final_references))
        self.assertEqual(len(initial_components), len(final_components))

        # Create lookup dictionaries for efficient comparison
        final_references_dict = {ref.id: ref for ref in final_references}
        final_components_dict = {comp.id: comp for comp in final_components}

        # Assert field-by-field equality for References
        for initial_ref in initial_references:
            final_ref = final_references_dict[initial_ref.id]
            initial_dict = {k: v for k, v in initial_ref.__dict__.items() if k != '_state'}
            final_dict = {k: v for k, v in final_ref.__dict__.items() if k != '_state'}
            self.assertEqual(initial_dict, final_dict)

        # Assert field-by-field equality for Components
        for initial_comp in initial_components:
            final_comp = final_components_dict[initial_comp.id]
            initial_dict = {k: v for k, v in initial_comp.__dict__.items() if k != '_state'}
            final_dict = {k: v for k, v in final_comp.__dict__.items() if k != '_state'}
            self.assertEqual(initial_dict, final_dict)
