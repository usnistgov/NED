"""
Unit tests for the rename_identity management command.
"""

import json
import os
import shutil
import tempfile
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TransactionTestCase

from ned_app.json_guards import check_data_dir
from ned_app.management.commands.rename_identity import CHILDREN
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


def _csl(family, year, **extra):
    return {
        'type': 'article-journal',
        'title': f'{family} report',
        'author': [{'family': family, 'given': 'A.'}],
        'issued': {'date-parts': [[year]]},
        **extra,
    }


class RenameIdentityCommandTests(TransactionTestCase):
    """
    Test cases for rename_identity, on a small synthetic graph.

    Smith-2020 has an unlabelled program (S1, T1, observation 01), a labelled
    program Walls (S2) and a fragility model with a curve and both bridges.
    S3, in Doe-2021's program, overrides its reference with Smith-2020. Lab2
    is an unused facility with blank fields.
    """

    def setUp(self):
        component = Component.objects.create(component_id='A.10.1.1', name='Wall')
        smith = Reference.objects.create(csl_data=_csl('Smith', 2020))
        doe = Reference.objects.create(csl_data=_csl('Doe', 2021))
        lab = Facility.objects.create(label='Lab', name='Test Lab')
        Facility.objects.create(label='Lab2')
        smith_program = Program.objects.create(reference=smith)
        walls = Program.objects.create(label='Walls', reference=smith)
        doe_program = Program.objects.create(reference=doe)

        def specimen(program, label, reference=None):
            return Specimen.objects.create(
                program=program,
                facility=lab,
                reference=reference,
                label=label,
                component=component,
                comp_description='Wall panel',
            )

        s1 = specimen(smith_program, 'S1')
        specimen(walls, 'S2')
        specimen(doe_program, 'S3', reference=smith)
        test = Test.objects.create(
            specimen=s1, label='T1', test_type='Dynamic, uniaxial'
        )
        observation = Observation.objects.create(
            test=test,
            label='01',
            ds_description='Cracking',
            edp_metric='Story Drift Ratio',
            edp_unit='Ratio',
            edp_value='0.01',
            ds_class='Consequential',
        )
        fm = FragilityModel.objects.create(
            reference=smith,
            model_id='fm1',
            comp_description='Wall panel',
            edp_metric='Story Drift Ratio',
            edp_unit='Ratio',
        )
        FragilityCurve.objects.create(
            fragility_model=fm,
            ds_rank=1,
            ds_description='Cracking',
            median='0.01',
            beta='0.4',
            probability='1.0',
        )
        ComponentFragilityModelBridge.objects.create(
            component=component, fragility_model=fm
        )
        ObservationFragilityModelBridge.objects.create(
            observation=observation, fragility_model=fm
        )

        self.work_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.work_dir, 'data')
        call_command('export_data', output_dir=self.data_dir, stdout=StringIO())
        self.original = self._data_files()

    def tearDown(self):
        shutil.rmtree(self.work_dir)

    def _write_csl(self, csl_data):
        path = os.path.join(self.work_dir, 'csl.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(csl_data, f)
        return path

    def _rename(self, *args, **options):
        stdout = StringIO()
        call_command(
            'rename_identity',
            *args,
            data_dir=self.data_dir,
            stdout=stdout,
            **options,
        )
        return stdout.getvalue()

    def _data_files(self, data_dir=None):
        data_dir = data_dir or self.data_dir
        files = {}
        for name in sorted(os.listdir(data_dir)):
            with open(os.path.join(data_dir, name), 'rb') as f:
                files[name] = f.read()
        return files

    def _export(self):
        with tempfile.TemporaryDirectory() as export_dir:
            call_command('export_data', output_dir=export_dir, stdout=StringIO())
            return self._data_files(export_dir)

    def _resync(self):
        # After a test adds rows, bring the data dir back in step.
        call_command('export_data', output_dir=self.data_dir, stdout=StringIO())
        self.original = self._data_files()

    def _assert_round_trips(self):
        """The data dir holds the database, passes the guards and rebuilds."""
        self.assertEqual(self._export(), self._data_files())
        self.assertEqual(check_data_dir(self.data_dir), [])
        call_command('flush', '--noinput')
        with patch(
            'ned_app.management.commands.ingest.build_json_data_file_path',
            side_effect=lambda name: os.path.join(self.data_dir, name),
        ):
            call_command('ingest', stdout=StringIO())
        self.assertEqual(self._export(), self._data_files())

    def _assert_unchanged(self):
        self.assertEqual(self._data_files(), self.original)
        self.assertEqual(self._export(), self.original)

    def _ids(self, model, field):
        return sorted(model.objects.values_list(field, flat=True))

    # ------------------------------------------------------------------
    # Relabels
    # ------------------------------------------------------------------
    def test_relabel_facility(self):
        output = self._rename('facility', 'Lab', label='UCSD_Lab')
        self.assertIn("Renamed facility 'Lab' to 'UCSD_Lab'", output)
        self.assertEqual(self._ids(Facility, 'label'), ['Lab2', 'UCSD_Lab'])
        self.assertEqual(
            set(Specimen.objects.values_list('facility_id', flat=True)),
            {'UCSD_Lab'},
        )
        self._assert_round_trips()

    def test_relabel_program(self):
        self._rename('program', 'Walls', label='Cladding')
        self.assertEqual(
            self._ids(Specimen, 'specimen_id'),
            ['Cladding|S2', 'Doe-2021|S3', 'Smith-2020|S1'],
        )
        self._assert_round_trips()

    def test_relabel_specimen(self):
        self._rename('specimen', 'Smith-2020|S1', label='Wall_1')
        self.assertEqual(self._ids(Test, 'test_id'), ['Smith-2020|Wall_1|T1'])
        self.assertEqual(
            self._ids(Observation, 'observation_id'), ['Smith-2020|Wall_1|T1|01']
        )
        self.assertEqual(
            self._ids(ObservationFragilityModelBridge, 'observation_id'),
            ['Smith-2020|Wall_1|T1|01'],
        )
        self._assert_round_trips()

    def test_relabel_test(self):
        self._rename('test', 'Smith-2020|S1|T1', label='Run2')
        self.assertEqual(
            self._ids(ObservationFragilityModelBridge, 'observation_id'),
            ['Smith-2020|S1|Run2|01'],
        )
        self._assert_round_trips()

    def test_relabel_observation(self):
        self._rename('observation', 'Smith-2020|S1|T1|01', label='02')
        self.assertEqual(
            self._ids(ObservationFragilityModelBridge, 'observation_id'),
            ['Smith-2020|S1|T1|02'],
        )
        self._assert_round_trips()

    def test_case_only_rename_rewrites_children(self):
        self._rename('specimen', 'Smith-2020|S1', label='s1')
        self.assertEqual(
            self._ids(Observation, 'observation_id'), ['Smith-2020|s1|T1|01']
        )
        self._assert_round_trips()

    def test_set_and_clear_a_program_label(self):
        self._rename('program', 'Smith-2020', label='Frames')
        self.assertEqual(
            self._ids(Observation, 'observation_id'), ['Frames|S1|T1|01']
        )
        self._assert_round_trips()
        # Walls can now take the reference id.
        self._rename('program', 'Walls', label='')
        self.assertEqual(
            self._ids(Program, 'program_id'), ['Doe-2021', 'Frames', 'Smith-2020']
        )
        self.assertEqual(
            self._ids(Specimen, 'specimen_id'),
            ['Doe-2021|S3', 'Frames|S1', 'Smith-2020|S2'],
        )
        self._assert_round_trips()

    # ------------------------------------------------------------------
    # References
    # ------------------------------------------------------------------
    def test_reference_label_change_cascades(self):
        self._rename('reference', 'Smith-2020', reference_label='Smith_Walls')
        new = 'Smith_Walls-2020'
        self.assertEqual(self._ids(Reference, 'reference_id'), ['Doe-2021', new])
        # The labelled program keeps its id but follows the reference.
        self.assertEqual(
            sorted(Program.objects.values_list('program_id', 'reference_id')),
            [('Doe-2021', 'Doe-2021'), (new, new), ('Walls', new)],
        )
        self.assertEqual(
            sorted(Specimen.objects.values_list('specimen_id', 'reference_id')),
            [('Doe-2021|S3', new), (f'{new}|S1', None), ('Walls|S2', None)],
        )
        self.assertEqual(self._ids(Test, 'test_id'), [f'{new}|S1|T1'])
        self.assertEqual(
            self._ids(Observation, 'observation_id'), [f'{new}|S1|T1|01']
        )
        fm_id = f'{new}|fm1'
        self.assertEqual(self._ids(FragilityModel, 'fragility_model_id'), [fm_id])
        self.assertEqual(self._ids(FragilityCurve, 'fragility_model_id'), [fm_id])
        self.assertEqual(
            self._ids(ComponentFragilityModelBridge, 'fragility_model_id'), [fm_id]
        )
        self.assertEqual(
            list(
                ObservationFragilityModelBridge.objects.values_list(
                    'observation_id', 'fragility_model_id'
                )
            ),
            [(f'{new}|S1|T1|01', fm_id)],
        )
        self._assert_round_trips()

    def test_csl_json_change_rederives_the_id_and_strips_the_csl_id(self):
        csl_path = self._write_csl(_csl('Smith', 2022, id='Smith-2020'))
        self._rename('reference', 'Smith-2020', csl_json=csl_path)
        ref = Reference.objects.get(reference_id='Smith-2022')
        self.assertNotIn('id', ref.csl_data)
        self.assertEqual(ref.year, 2022)
        self.assertEqual(
            self._ids(FragilityModel, 'fragility_model_id'), ['Smith-2022|fm1']
        )
        self.assertEqual(
            self._ids(Observation, 'observation_id'), ['Smith-2022|S1|T1|01']
        )
        self._assert_round_trips()

    # ------------------------------------------------------------------
    # Refusals
    # ------------------------------------------------------------------
    def test_unknown_id_names_case_only_matches(self):
        with self.assertRaisesMessage(CommandError, "'Smith-2020|S1'"):
            self._rename('specimen', 'smith-2020|s1', label='S9')

    def test_clashing_rename_is_refused_and_writes_nothing(self):
        Specimen.objects.create(
            program_id='Walls',
            facility_id='Lab',
            label='S4',
            component_id='A.10.1.1',
            comp_description='Wall panel',
        )
        self._resync()
        cases = [
            (('facility', 'Lab'), {'label': 'Lab2'}),
            (('facility', 'Lab'), {'label': 'LAB2'}),
            # A program label must not take a reference id, in any case.
            (('program', 'Walls'), {'label': 'doe-2021'}),
            # Smith-2020 already has an unlabelled program.
            (('program', 'Walls'), {'label': ''}),
            (('specimen', 'Walls|S2'), {'label': 'S4'}),
            (('specimen', 'Walls|S2'), {'label': 's4'}),
        ]
        for args, options in cases:
            with self.subTest(args=args, options=options):
                with self.assertRaisesMessage(CommandError, 'clashes with'):
                    self._rename(*args, **options)
                self._assert_unchanged()

    def test_reference_clashes_are_refused_and_write_nothing(self):
        # Another reference's id, and a labelled program's.
        Program.objects.create(label='Smith_Walls-2020', reference_id='Doe-2021')
        self._resync()
        csl_path = self._write_csl(_csl('smith', 2020))
        for args, options in [
            (('reference', 'Doe-2021'), {'csl_json': csl_path}),
            (('reference', 'Smith-2020'), {'reference_label': 'Smith_Walls'}),
        ]:
            with self.subTest(args=args, options=options):
                with self.assertRaisesMessage(CommandError, 'clashes with'):
                    self._rename(*args, **options)
                self._assert_unchanged()

    def test_program_label_cannot_take_a_reference_id(self):
        # Roe-2019 has no program, so only the reference check can refuse it.
        Reference.objects.create(csl_data=_csl('Roe', 2019))
        self._resync()
        with self.assertRaisesMessage(CommandError, "Reference 'Roe-2019'"):
            self._rename('program', 'Walls', label='roe-2019')
        self._assert_unchanged()

    def test_case_only_reference_rename(self):
        # The reference's own unlabelled program moves with it, so no clash.
        self._rename('reference', 'Smith-2020', reference_label='smith')
        self.assertEqual(
            self._ids(Reference, 'reference_id'), ['Doe-2021', 'smith-2020']
        )
        self.assertEqual(
            self._ids(Observation, 'observation_id'), ['smith-2020|S1|T1|01']
        )
        self.assertEqual(
            self._ids(FragilityModel, 'fragility_model_id'), ['smith-2020|fm1']
        )
        self._assert_round_trips()

    def test_invalid_labels_are_refused(self):
        with self.assertRaisesMessage(CommandError, 'Invalid label'):
            self._rename('specimen', 'Smith-2020|S1', label='S 1')
        with self.assertRaisesMessage(CommandError, 'reference_label'):
            self._rename('reference', 'Smith-2020', reference_label='Smith-Walls')
        self._assert_unchanged()

    def test_wrong_options_are_refused(self):
        for args, options in [
            (('facility', 'Lab'), {'label': 'X', 'merge_into': 'Lab2'}),
            (('facility', 'Lab'), {'label': 'X', 'force': True}),
            (('specimen', 'Smith-2020|S1'), {'reference_label': 'X'}),
            (('reference', 'Smith-2020'), {}),
        ]:
            with (
                self.subTest(args=args, options=options),
                self.assertRaises(CommandError),
            ):
                self._rename(*args, **options)

    def test_database_out_of_step_with_the_json_is_refused(self):
        path = os.path.join(self.data_dir, 'facility.json')
        with open(path, 'r') as f:
            records = json.load(f)
        records[0]['name'] = 'Edited by hand'
        with open(path, 'w') as f:
            json.dump(records, f, indent=4, sort_keys=True)
        with self.assertRaisesMessage(CommandError, 'facility.json'):
            self._rename('specimen', 'Smith-2020|S1', label='Wall_1')
        self.assertEqual(self._ids(Test, 'test_id'), ['Smith-2020|S1|T1'])

    def test_no_op_writes_nothing(self):
        # Put the data dir out of step: a no-op neither checks nor exports.
        path = os.path.join(self.data_dir, 'facility.json')
        with open(path, 'a') as f:
            f.write('\n')
        edited = self._data_files()
        self.assertIn(
            'Nothing to change',
            self._rename('specimen', 'Smith-2020|S1', label='S1'),
        )
        self.assertIn(
            'Nothing to change',
            self._rename('reference', 'Smith-2020', reference_label=''),
        )
        self.assertEqual(self._data_files(), edited)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------
    def test_failure_part_way_rolls_back(self):
        with (
            patch.object(Test, 'save', side_effect=RuntimeError('boom')),
            self.assertRaisesMessage(RuntimeError, 'boom'),
        ):
            self._rename('specimen', 'Smith-2020|S1', label='Wall_1')
        self._assert_unchanged()

    def test_constraint_check_catches_an_omitted_relation(self):
        with (
            patch.dict(CHILDREN, {Observation: []}),
            self.assertRaisesMessage(
                CommandError, 'ned_app_observationfragilitymodelbridge'
            ),
        ):
            self._rename('observation', 'Smith-2020|S1|T1|01', label='02')
        self._assert_unchanged()

    # ------------------------------------------------------------------
    # Facility merges
    # ------------------------------------------------------------------
    def test_merge_facility(self):
        output = self._rename('facility', 'Lab2', merge_into='Lab')
        self.assertIn("Merged facility 'Lab2' into 'Lab'", output)
        self.assertEqual(self._ids(Facility, 'label'), ['Lab'])
        self._assert_round_trips()

    def test_merge_refuses_to_discard_fields_unless_forced(self):
        with self.assertRaisesMessage(CommandError, "name: 'Test Lab'"):
            self._rename('facility', 'Lab', merge_into='Lab2')
        self._assert_unchanged()
        output = self._rename('facility', 'Lab', merge_into='Lab2', force=True)
        self.assertIn("name: 'Test Lab'", output)
        self.assertEqual(self._ids(Facility, 'label'), ['Lab2'])
        self.assertEqual(
            set(Specimen.objects.values_list('facility_id', flat=True)), {'Lab2'}
        )
        self._assert_round_trips()

    def test_merge_refuses_itself_and_a_missing_target(self):
        with self.assertRaisesMessage(CommandError, 'into itself'):
            self._rename('facility', 'Lab', merge_into='Lab')
        with self.assertRaisesMessage(CommandError, "did you mean 'Lab'"):
            self._rename('facility', 'Lab2', merge_into='lab')
        self._assert_unchanged()


class RelationTableTests(SimpleTestCase):
    def test_every_foreign_key_onto_a_renamed_model_is_listed(self):
        # A missing entry would leave that table's rows pointing at old ids.
        foreign_keys = {
            (field.related_model, model, field.name)
            for model in apps.get_app_config('ned_app').get_models()
            for field in model._meta.get_fields()
            if field.many_to_one
            and field.concrete
            and field.related_model in CHILDREN
        }
        listed = {
            (parent, child, fk)
            for parent, children in CHILDREN.items()
            for child, fk, _ in children
        }
        self.assertEqual(foreign_keys, listed)
