import json
import os
import tempfile
from unittest.mock import patch
from django.core.management import call_command
from django.test import TransactionTestCase, tag
from ned_app.models import (
    Reference,
    Component,
    FragilityModel,
    Experiment,
    ExperimentFragilityModelBridge,
    FragilityCurve,
)


@tag('integrity')
class DataIntegrityTests(TransactionTestCase):
    fixtures = ['initial_data.json']

    def setUp(self):
        self.temp_dir_path = tempfile.mkdtemp()

    def test_db_round_trip(self):
        initial_references = list(Reference.objects.all())
        initial_components = list(Component.objects.all())
        initial_fragility_models = list(FragilityModel.objects.all())
        initial_experiments = list(Experiment.objects.all())
        initial_exp_frag_bridges = list(ExperimentFragilityModelBridge.objects.all())
        initial_fragility_curves = list(FragilityCurve.objects.all())

        call_command('export_data', output_dir=self.temp_dir_path)

        call_command('flush', '--noinput')

        def mock_build_json_data_file_path(filename):
            return os.path.join(self.temp_dir_path, filename)

        with patch(
            'ned_app.serialization.file_and_path_utiles.build_json_data_file_path',
            side_effect=mock_build_json_data_file_path,
        ):
            call_command('ingest')

        final_references = list(Reference.objects.all())
        final_components = list(Component.objects.all())
        final_fragility_models = list(FragilityModel.objects.all())
        final_experiments = list(Experiment.objects.all())
        final_exp_frag_bridges = list(ExperimentFragilityModelBridge.objects.all())
        final_fragility_curves = list(FragilityCurve.objects.all())

        self.assertEqual(len(initial_references), len(final_references))
        self.assertEqual(len(initial_components), len(final_components))
        self.assertEqual(len(initial_fragility_models), len(final_fragility_models))
        self.assertEqual(len(initial_experiments), len(final_experiments))
        self.assertEqual(len(initial_exp_frag_bridges), len(final_exp_frag_bridges))
        self.assertEqual(len(initial_fragility_curves), len(final_fragility_curves))

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

        for initial_ref in initial_references:
            final_ref = final_references_dict[initial_ref.id]
            initial_dict = {
                k: v for k, v in initial_ref.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_ref.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

        for initial_comp in initial_components:
            final_comp = final_components_dict[initial_comp.id]
            initial_dict = {
                k: v for k, v in initial_comp.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_comp.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

        for initial_fm in initial_fragility_models:
            final_fm = final_fragility_models_dict[initial_fm.id]
            initial_dict = {
                k: v for k, v in initial_fm.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_fm.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

        for initial_exp in initial_experiments:
            final_exp = final_experiments_dict[initial_exp.id]
            initial_dict = {
                k: v for k, v in initial_exp.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_exp.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

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

        for initial_curve in initial_fragility_curves:
            final_curve = final_fragility_curves_dict[initial_curve.id]
            initial_dict = {
                k: v for k, v in initial_curve.__dict__.items() if k != '_state'
            }
            final_dict = {
                k: v for k, v in final_curve.__dict__.items() if k != '_state'
            }
            self.assertEqual(initial_dict, final_dict)

    def test_json_to_db_to_json_round_trip_is_lossless(self):
        temp_export_dir = tempfile.mkdtemp()

        try:
            call_command('ingest')

            call_command('export_data', output_dir=temp_export_dir)

            canonical_data_dir = 'resources/data'

            # Map each JSON file to its sort key function
            # For tables with composite keys, use tuple sorting
            json_files = {
                'reference.json': lambda x: x['id'],
                'component.json': lambda x: x['component_id'],
                'fragility_model.json': lambda x: x['id'],
                'experiment.json': lambda x: x['id'],
                'experiment_fragility_model_bridge.json': lambda x: (
                    x['experiment'],
                    x['fragility_model'],
                ),
                'fragility_curve.json': lambda x: (
                    x['fragility_model'],
                    x['ds_rank'],
                ),
            }

            for json_file, sort_func in json_files.items():
                canonical_path = os.path.join(canonical_data_dir, json_file)
                with open(canonical_path, 'r') as f:
                    canonical_data = json.load(f)

                exported_path = os.path.join(temp_export_dir, json_file)
                with open(exported_path, 'r') as f:
                    exported_data = json.load(f)

                # Sort both datasets by their key(s) to ensure order-independent comparison
                canonical_data_sorted = sorted(canonical_data, key=sort_func)
                exported_data_sorted = sorted(exported_data, key=sort_func)

                self.assertEqual(
                    canonical_data_sorted,
                    exported_data_sorted,
                    f'Mismatch in {json_file}: canonical and exported data differ',
                )

        finally:
            import shutil

            shutil.rmtree(temp_export_dir)
