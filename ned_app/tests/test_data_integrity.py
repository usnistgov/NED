import os
import tempfile
from unittest.mock import patch
from django.core.management import call_command
from django.test import TestCase, tag
from ned_app.models import (
    Reference,
    Component,
    FragilityModel,
    Experiment,
    ExperimentFragilityModelBridge,
    FragilityCurve,
)


@tag('integrity')
class DataIntegrityTests(TestCase):
    fixtures = ['initial_data.json']

    def setUp(self):
        self.temp_dir_path = tempfile.mkdtemp()

    def test_db_round_trip(self):
        # Capture initial state
        initial_references = list(Reference.objects.all())
        initial_components = list(Component.objects.all())
        initial_fragility_models = list(FragilityModel.objects.all())
        initial_experiments = list(Experiment.objects.all())
        initial_exp_frag_bridges = list(ExperimentFragilityModelBridge.objects.all())
        initial_fragility_curves = list(FragilityCurve.objects.all())

        # Execute export_data command
        call_command('export_data', output_dir=self.temp_dir_path)

        # Execute flush command
        call_command('flush', '--noinput')

        # Execute ingest command with mocked path
        def mock_build_json_data_file_path(filename):
            return os.path.join(self.temp_dir_path, filename)

        with patch(
            'ned_app.serialization.file_and_path_utiles.build_json_data_file_path',
            side_effect=mock_build_json_data_file_path,
        ):
            call_command('ingest')

        # Retrieve final state
        final_references = list(Reference.objects.all())
        final_components = list(Component.objects.all())
        final_fragility_models = list(FragilityModel.objects.all())
        final_experiments = list(Experiment.objects.all())
        final_exp_frag_bridges = list(ExperimentFragilityModelBridge.objects.all())
        final_fragility_curves = list(FragilityCurve.objects.all())

        # Assert record counts
        self.assertEqual(len(initial_references), len(final_references))
        self.assertEqual(len(initial_components), len(final_components))
        self.assertEqual(len(initial_fragility_models), len(final_fragility_models))
        self.assertEqual(len(initial_experiments), len(final_experiments))
        self.assertEqual(len(initial_exp_frag_bridges), len(final_exp_frag_bridges))
        self.assertEqual(len(initial_fragility_curves), len(final_fragility_curves))

        # Create lookup dictionaries for efficient comparison
        final_references_dict = {ref.id: ref for ref in final_references}
        final_components_dict = {comp.id: comp for comp in final_components}
        final_fragility_models_dict = {fm.id: fm for fm in final_fragility_models}
        final_experiments_dict = {exp.id: exp for exp in final_experiments}
        final_exp_frag_bridges_dict = {
            bridge.id: bridge for bridge in final_exp_frag_bridges
        }
        final_fragility_curves_dict = {
            curve.id: curve for curve in final_fragility_curves
        }

        # Assert field-by-field equality for References
        for initial_ref in initial_references:
            final_ref = final_references_dict[initial_ref.id]
            initial_dict = {
                k: v for k, v in initial_ref.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_ref.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

        # Assert field-by-field equality for Components
        for initial_comp in initial_components:
            final_comp = final_components_dict[initial_comp.id]
            initial_dict = {
                k: v for k, v in initial_comp.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_comp.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

        # Assert field-by-field equality for FragilityModels
        for initial_fm in initial_fragility_models:
            final_fm = final_fragility_models_dict[initial_fm.id]
            initial_dict = {
                k: v for k, v in initial_fm.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_fm.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

        # Assert field-by-field equality for Experiments
        for initial_exp in initial_experiments:
            final_exp = final_experiments_dict[initial_exp.id]
            initial_dict = {
                k: v for k, v in initial_exp.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_exp.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

        # Assert field-by-field equality for ExperimentFragilityModelBridges
        for initial_exp_frag_bridge in initial_exp_frag_bridges:
            final_exp_frag_bridge = final_exp_frag_bridges_dict[
                initial_exp_frag_bridge.id
            ]
            initial_dict = {
                k: v
                for k, v in initial_exp_frag_bridge.__dict__.items()
                if k != '_state'
            }
            final_dict = {
                k: v
                for k, v in final_exp_frag_bridge.__dict__.items()
                if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

        # Assert field-by-field equality for FragilityCurves
        for initial_curve in initial_fragility_curves:
            final_curve = final_fragility_curves_dict[initial_curve.id]
            initial_dict = {
                k: v for k, v in initial_curve.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_curve.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)
