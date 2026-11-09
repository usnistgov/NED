import json
import os
from decimal import Decimal

from django.core.management.base import BaseCommand

from ned_app.models import (
    Component,
    ComponentFragilityModelBridge,
    Facility,
    FragilityCurve,
    FragilityModel,
    Observation,
    ObservationFragilityModelBridge,
    Program,
    Reference,
    Specimen,
    Test,
)


class DecimalEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle Decimal objects.

    Converts Decimal instances to float for JSON serialization.
    """

    def default(self, obj):
        """
        Override default JSON encoding to handle Decimal objects.

        Args:
            obj: The object to encode.

        Returns:
            float: The float representation of a Decimal object.
            Any: The default encoding for non-Decimal objects.
        """
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class Command(BaseCommand):
    """
    Django management command to export all database data to canonical JSON files.

    This command exports data from all models (Reference, Component, Facility,
    Program, Specimen, Test, Observation, FragilityModel,
    ComponentFragilityModelBridge, ObservationFragilityModelBridge,
    FragilityCurve) to separate JSON files in the specified output directory.
    """

    help = 'Exports all data from the database to canonical JSON files'

    def add_arguments(self, parser):
        """
        Add command-line arguments for the export command.

        Args:
            parser: The argument parser to configure.
        """
        parser.add_argument(
            '--output_dir',
            type=str,
            help='Directory where exported JSON files will be saved',
            required=True,
        )

    def handle(self, *args, **options):
        """
        Execute the export command.

        Args:
            *args: Positional arguments (unused).
            **options: Command options including 'output_dir'.
        """
        output_dir = options['output_dir']

        os.makedirs(output_dir, exist_ok=True)

        self.export_reference_data(output_dir)
        self.export_component_data(output_dir)
        self.export_facility_data(output_dir)
        self.export_program_data(output_dir)
        self.export_specimen_data(output_dir)
        self.export_test_data(output_dir)
        self.export_observation_data(output_dir)
        self.export_fragility_model_data(output_dir)
        self.export_component_fragility_bridge_data(output_dir)
        self.export_observation_fragility_bridge_data(output_dir)
        self.export_fragility_curve_data(output_dir)

        self.stdout.write(self.style.SUCCESS('Data export completed successfully!'))

    def export_reference_data(self, output_dir):
        """
        Export Reference model data to JSON file.

        Excludes auto-populated denormalized fields (title, author, year) and
        includes only the source-of-truth fields.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting Reference data...')
        references = Reference.objects.all()

        data = []
        for ref in references:
            # reference_id is derived at ingest, not stored in the source JSON.
            ref_data = {
                'study_type': ref.study_type,
                'comp_type': ref.comp_type,
                'csl_data': ref.csl_data,
            }
            # Only emit reference_label when set, to keep unlabeled records clean.
            if ref.reference_label:
                ref_data['reference_label'] = ref.reference_label
            data.append(ref_data)

        file_path = os.path.join(output_dir, 'reference.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_component_data(self, output_dir):
        """
        Export Component model data to JSON file.

        Excludes auto-populated fields (major_group, group, element, subelement)
        and uses the natural key (component_id) instead of database primary key.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting Component data...')
        components = Component.objects.all()

        data = []
        for comp in components:
            comp_data = {
                'component_id': comp.component_id,
                'name': comp.name,
            }
            data.append(comp_data)

        file_path = os.path.join(output_dir, 'component.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_facility_data(self, output_dir):
        """
        Export Facility model data to JSON file.

        The label is the facility's identity and is written as stored.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting Facility data...')
        facilities = Facility.objects.all()

        data = []
        for fac in facilities:
            fac_data = {
                'label': fac.label,
                'name': fac.name,
                'location': fac.location,
                'notes': fac.notes,
            }
            data.append(fac_data)

        file_path = os.path.join(output_dir, 'facility.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_program_data(self, output_dir):
        """
        Export Program model data to JSON file.

        Excludes the derived program_id, which ingest rebuilds from the label
        or the reference.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting Program data...')
        programs = Program.objects.all()

        data = []
        for prog in programs:
            prog_data = {
                'label': prog.label,
                'name': prog.name,
                'notes': prog.notes,
                'reference': prog.reference_id,
            }
            data.append(prog_data)

        file_path = os.path.join(output_dir, 'program.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_specimen_data(self, output_dir):
        """
        Export Specimen model data to JSON file.

        Excludes the derived specimen_id, which ingest rebuilds from the
        program and the label. Foreign keys are written as stored strings.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting Specimen data...')
        specimens = Specimen.objects.all()

        data = []
        for sp in specimens:
            sp_data = {
                'program': sp.program_id,
                'facility': sp.facility_id,
                'reference': sp.reference_id,
                'label': sp.label,
                'name': sp.name,
                'contributor': sp.contributor,
                'component': sp.component_id,
                'comp_detail': sp.comp_detail,
                'material': sp.material,
                'size_class': sp.size_class,
                'governing_design_standard': sp.governing_design_standard,
                'design_objective': sp.design_objective,
                'comp_description': sp.comp_description,
                'notes': sp.notes,
            }
            data.append(sp_data)

        file_path = os.path.join(output_dir, 'specimen.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_test_data(self, output_dir):
        """
        Export Test model data to JSON file.

        Excludes the derived test_id, which ingest rebuilds from the specimen
        and the label.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting Test data...')
        tests = Test.objects.all()

        data = []
        for t in tests:
            t_data = {
                'specimen': t.specimen_id,
                'label': t.label,
                'test_order': t.test_order,
                'test_type': t.test_type,
                'loading_protocol': t.loading_protocol,
                'peak_test_amplitude': t.peak_test_amplitude,
                'prior_damage': t.prior_damage,
                'prior_damage_repaired': t.prior_damage_repaired,
                'notes': t.notes,
            }
            data.append(t_data)

        file_path = os.path.join(output_dir, 'test.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_observation_data(self, output_dir):
        """
        Export Observation model data to JSON file.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting Observation data...')
        experiments = Observation.objects.all()

        data = []
        for exp in experiments:
            exp_data = {
                'reference': exp.reference_id,
                'specimen': exp.specimen,
                'specimen_inspection_sequence': exp.specimen_inspection_sequence,
                'contributor': exp.contributor,
                'component': exp.component.component_id,
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
                'test': exp.test_id,
                'label': exp.label,
                'damage_location': exp.damage_location,
            }
            data.append(exp_data)

        file_path = os.path.join(output_dir, 'observation.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_fragility_model_data(self, output_dir):
        """
        Export FragilityModel model data to JSON file.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting FragilityModel data...')
        fragility_models = FragilityModel.objects.all()

        data = []
        for fm in fragility_models:
            fm_data = {
                'reference': fm.reference.reference_id,
                'model_id': fm.model_id,
                'p58_fragility': fm.p58_fragility,
                'comp_detail': fm.comp_detail,
                'material': fm.material,
                'size_class': fm.size_class,
                'comp_description': fm.comp_description,
                'contributor': fm.contributor,
                'source': fm.source,
                'edp_metric': fm.edp_metric,
                'edp_unit': fm.edp_unit,
            }
            data.append(fm_data)

        file_path = os.path.join(output_dir, 'fragility_model.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_component_fragility_bridge_data(self, output_dir):
        """
        Export ComponentFragilityModelBridge model data to JSON file.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting ComponentFragilityModelBridge data...')
        bridges = ComponentFragilityModelBridge.objects.all()

        data = []
        for bridge in bridges:
            bridge_data = {
                'component': bridge.component.component_id,
                'fragility_model': bridge.fragility_model_id,
            }
            data.append(bridge_data)

        file_path = os.path.join(output_dir, 'component_fragility_model_bridge.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_observation_fragility_bridge_data(self, output_dir):
        """
        Export ObservationFragilityModelBridge model data to JSON file.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting ObservationFragilityModelBridge data...')
        bridges = ObservationFragilityModelBridge.objects.all()

        data = []
        for bridge in bridges:
            bridge_data = {
                'observation': bridge.observation_id,
                'fragility_model': bridge.fragility_model_id,
            }
            data.append(bridge_data)

        file_path = os.path.join(
            output_dir, 'observation_fragility_model_bridge.json'
        )
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)

    def export_fragility_curve_data(self, output_dir):
        """
        Export FragilityCurve model data to JSON file.

        Args:
            output_dir (str): Directory where the JSON file will be saved.
        """
        self.stdout.write('Exporting FragilityCurve data...')
        fragility_curves = FragilityCurve.objects.all()

        data = []
        for curve in fragility_curves:
            curve_data = {
                'fragility_model': curve.fragility_model_id,
                'basis': curve.basis,
                'num_observations': curve.num_observations,
                'ds_rank': curve.ds_rank,
                'ds_description': curve.ds_description,
                'median': curve.median,
                'beta': curve.beta,
                'probability': curve.probability,
            }
            data.append(curve_data)

        file_path = os.path.join(output_dir, 'fragility_curve.json')
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True, cls=DecimalEncoder)
