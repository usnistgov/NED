import os
import json
from decimal import Decimal
from django.core.management.base import BaseCommand
from ned_app.models import (
    Reference,
    Component,
    Experiment,
    FragilityModel,
    ExperimentFragilityModelBridge,
    FragilityCurve,
)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Decimal objects."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class Command(BaseCommand):
    help = 'Exports all data from the database to canonical JSON files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output_dir',
            type=str,
            help='Directory where exported JSON files will be saved',
            required=True,
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Export data for each model
        self.export_reference_data(output_dir)
        self.export_component_data(output_dir)
        self.export_experiment_data(output_dir)
        self.export_fragility_model_data(output_dir)
        self.export_experiment_fragility_bridge_data(output_dir)
        self.export_fragility_curve_data(output_dir)

        self.stdout.write(self.style.SUCCESS('Data export completed successfully!'))

    def export_reference_data(self, output_dir):
        """Export Reference model data, excluding auto-populated fields."""
        self.stdout.write('Exporting Reference data...')
        references = Reference.objects.all()

        # Include only source-of-truth fields, excluding denormalized fields
        data = []
        for ref in references:
            # Exclude denormalized fields (title, author, year)
            ref_data = {
                'id': ref.id,
                'study_type': ref.study_type,
                'comp_type': ref.comp_type,
                'pdf_saved': ref.pdf_saved,
                'csl_data': ref.csl_data,
            }
            data.append(ref_data)

        # Write to JSON file with indentation and sorted keys
        file_path = os.path.join(output_dir, 'reference.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_component_data(self, output_dir):
        """Export Component model data, excluding auto-populated fields."""
        self.stdout.write('Exporting Component data...')
        components = Component.objects.all()

        # Include only source-of-truth fields
        data = []
        for comp in components:
            # Exclude auto-populated fields (major_group, group, element, subelement)
            # Use natural key (component_id) instead of database primary key (id)
            comp_data = {
                'component_id': comp.component_id,
                'name': comp.name,
            }
            data.append(comp_data)

        # Write to JSON file with indentation and sorted keys
        file_path = os.path.join(output_dir, 'component.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_experiment_data(self, output_dir):
        """Export Experiment model data."""
        self.stdout.write('Exporting Experiment data...')
        experiments = Experiment.objects.all()

        data = []
        for exp in experiments:
            # For consistency with test expectations
            exp_data = {
                'id': exp.id,
                'reference': exp.reference_id,
                'specimen': exp.specimen,
                'specimen_inspection_sequence': exp.specimen_inspection_sequence,
                'reviewer': exp.reviewer,
                'component': exp.component.component_id,  # Use component_id not id for experiments
                'comp_detail': exp.comp_detail,
                'material': exp.material,
                'size_class': exp.size_class,
                'test_type': exp.test_type,
                'loading_protocol': exp.loading_protocol,
                'peak_test_amplitude': exp.peak_test_amplitude,
                'location': exp.location,
                'governing_design_standard': exp.governing_design_standard,
                'design_objective': exp.design_objective,
                'comp_description': exp.comp_description,
                'ds_description': exp.ds_description,
                'prior_damage': exp.prior_damage,
                'prior_damage_repaired': exp.prior_damage_repaired,
                'edp_metric': exp.edp_metric,
                'edp_unit': exp.edp_unit,
                'edp_value': exp.edp_value,
                'alt_edp_metric': exp.alt_edp_metric,
                'alt_edp_unit': exp.alt_edp_unit,
                'alt_edp_value': exp.alt_edp_value,
                'ds_rank': exp.ds_rank,
                'ds_class': exp.ds_class,
                'notes': exp.notes,
            }
            data.append(exp_data)

        # Write to JSON file with indentation and sorted keys
        file_path = os.path.join(output_dir, 'experiment.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_fragility_model_data(self, output_dir):
        """Export FragilityModel model data."""
        self.stdout.write('Exporting FragilityModel data...')
        fragility_models = FragilityModel.objects.all()

        data = []
        for fm in fragility_models:
            # Use component.component_id as required by the test
            fm_data = {
                'id': fm.id,
                'p58_fragility': fm.p58_fragility,
                'component': fm.component.component_id,  # Use component_id as required by the test
                'comp_detail': fm.comp_detail,
                'material': fm.material,
                'size_class': fm.size_class,
                'comp_description': fm.comp_description,
            }
            data.append(fm_data)

        # Write to JSON file with indentation and sorted keys
        file_path = os.path.join(output_dir, 'fragility_model.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_experiment_fragility_bridge_data(self, output_dir):
        """Export ExperimentFragilityModelBridge model data."""
        self.stdout.write('Exporting ExperimentFragilityModelBridge data...')
        bridges = ExperimentFragilityModelBridge.objects.all()

        data = []
        for bridge in bridges:
            bridge_data = {
                'experiment': bridge.experiment_id,
                'fragility_model': bridge.fragility_model_id,
            }
            data.append(bridge_data)

        # Write to JSON file with indentation and sorted keys
        file_path = os.path.join(
            output_dir, 'experiment_fragility_model_bridge.json'
        )
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_fragility_curve_data(self, output_dir):
        """Export FragilityCurve model data."""
        self.stdout.write('Exporting FragilityCurve data...')
        fragility_curves = FragilityCurve.objects.all()

        data = []
        for curve in fragility_curves:
            curve_data = {
                'fragility_model': curve.fragility_model_id,
                'reviewer': curve.reviewer,
                'source': curve.source,
                'basis': curve.basis,
                'num_observations': curve.num_observations,
                'reference': curve.reference_id,
                'edp_metric': curve.edp_metric,
                'edp_unit': curve.edp_unit,
                'ds_rank': curve.ds_rank,
                'ds_description': curve.ds_description,
                'median': curve.median,
                'beta': curve.beta,
                'probability': curve.probability,
            }
            data.append(curve_data)

        # Write to JSON file with indentation and sorted keys
        file_path = os.path.join(output_dir, 'fragility_curve.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)
