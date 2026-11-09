import filecmp
import json
import os
import tempfile
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, connection, transaction

from ned_app.management.commands.ingest import _flatten_detail
from ned_app.models import (
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
    derive_reference_id,
)
from ned_app.serialization.file_and_path_utiles import DATA_DIR
from ned_app.serialization.serializer import ReferenceSerializer
from ned_app.validators import validate_label

# Each level: its model, the id it is found by, and the id a new label gives.
LEVELS = {
    'facility': (Facility, 'label', lambda r, label: label),
    'program': (Program, 'program_id', lambda r, label: label or r.reference_id),
    'specimen': (
        Specimen,
        'specimen_id',
        lambda r, label: f'{r.program_id}|{label}',
    ),
    'test': (Test, 'test_id', lambda r, label: f'{r.specimen_id}|{label}'),
    'observation': (
        Observation,
        'observation_id',
        lambda r, label: f'{r.test_id}|{label}',
    ),
    'reference': (Reference, 'reference_id', None),
}

# Every foreign key onto a renamable id: parent -> (child, fk, child's derived
# id). A child with a derived id is re-saved and recursed into; a leaf (None)
# is updated in bulk.
CHILDREN = {
    Reference: [
        (Program, 'reference', 'program_id'),
        (Specimen, 'reference', None),
        (FragilityModel, 'reference', 'fragility_model_id'),
    ],
    Facility: [(Specimen, 'facility', None)],
    Program: [(Specimen, 'program', 'specimen_id')],
    Specimen: [(Test, 'specimen', 'test_id')],
    Test: [(Observation, 'test', 'observation_id')],
    Observation: [(ObservationFragilityModelBridge, 'observation', None)],
    FragilityModel: [
        (FragilityCurve, 'fragility_model', None),
        (ObservationFragilityModelBridge, 'fragility_model', None),
        (ComponentFragilityModelBridge, 'fragility_model', None),
    ],
}

# The options each level takes.
LEVEL_OPTIONS = {
    'facility': {'label', 'merge_into', 'force'},
    'reference': {'reference_label', 'csl_json'},
}
OTHER_LEVEL_OPTIONS = {'label'}

FIXTURE_STEPS = (
    'Regenerate the fixture from a fresh build, run the standard checks, and '
    'commit the data and the fixture together:\n'
    '    rm db.sqlite3 && python manage.py migrate && python manage.py ingest\n'
    '    PYTHONUTF8=1 python manage.py dumpdata ned_app --indent 2 '
    '--output ned_app/fixtures/initial_data.json\n'
    '(In PowerShell, set $env:PYTHONUTF8 = 1 first; see the README.)'
)


def cascade(model, old_id, new_id):
    """
    Repoint every child of a renamed record, depth first.

    Args:
        model: The renamed record's model.
        old_id (str): The id its children still hold.
        new_id (str): The id they should hold.

    Returns:
        int: The number of rows rewritten.
    """
    rewritten = 0
    for child_model, fk, id_field in CHILDREN.get(model, []):
        rows = child_model.objects.filter(**{f'{fk}_id': old_id})
        if id_field is None:
            # update() skips save(), so it is safe only on a level with no
            # derived id.
            rewritten += rows.update(**{f'{fk}_id': new_id})
            continue
        for child in list(rows):
            child_old = getattr(child, id_field)
            setattr(child, f'{fk}_id', new_id)
            child.save()
            rewritten += 1
            child_new = getattr(child, id_field)
            if child_new != child_old:
                rewritten += cascade(child_model, child_old, child_new)
    return rewritten


class Command(BaseCommand):
    """
    Django management command to change a label, a citation or a facility.

    Saves the record, rewrites every descendant's foreign keys and derived ids
    in one transaction, then exports the data directory.
    """

    help = (
        'Relabel a facility, program, specimen, test or observation, change a '
        "reference's label or citation, or merge two facilities. Every "
        'descendant follows, and the result is exported to the data directory.'
    )

    def add_arguments(self, parser):
        parser.add_argument('level', choices=list(LEVELS))
        parser.add_argument(
            'identifier',
            help="The record's exact id (quote ids containing '|').",
        )
        parser.add_argument(
            '--label',
            help="The new label ('' clears a program's label).",
        )
        parser.add_argument(
            '--merge_into',
            help='Facility only: the label of the facility to merge into.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='With --merge_into: discard differing name, location or notes.',
        )
        parser.add_argument(
            '--reference_label',
            help="Reference only: the new reference_label ('' clears it).",
        )
        parser.add_argument(
            '--csl_json',
            help='Reference only: a file holding the new CSL-JSON object.',
        )
        parser.add_argument(
            '--data_dir',
            default=DATA_DIR,
            help='The JSON data directory (default: resources/data/).',
        )

    def handle(self, *args, **options):
        level = options['level']
        self._check_options(level, options)
        model, id_field, derive = LEVELS[level]
        record = self._find(model, id_field, options['identifier'])

        if options['merge_into'] is not None:
            self._merge(
                record, options['merge_into'], options['force'], options['data_dir']
            )
            self._export(options['data_dir'])
            return

        old_id = getattr(record, id_field)
        label = options['label']
        if level == 'reference':
            serializer, new_id, changed = self._prepare_reference(record, options)
            apply_change = serializer.save
        else:
            if label or level != 'program':
                self._validate_label(label)
            new_id = derive(record, label)
            changed = label != record.label

            def apply_change():
                record.label = label
                record.save()

        if not changed:
            self.stdout.write('Nothing to change.')
            return
        self._check_clashes(level, record, old_id, new_id, label)
        self._check_in_step(options['data_dir'])

        try:
            with transaction.atomic():
                apply_change()
                new_id = getattr(record, id_field)
                # Children are rewritten even for a case-only rename, since
                # foreign keys and ingest's lookups match case.
                rewritten = cascade(model, old_id, new_id) if new_id != old_id else 0
                connection.check_constraints()
        except IntegrityError as exc:
            raise CommandError(f'Rolled back; nothing was written: {exc}') from exc

        if new_id == old_id:
            self.stdout.write(f'Updated {level} {old_id!r}; its id is unchanged.')
        else:
            self.stdout.write(
                f'Renamed {level} {old_id!r} to {new_id!r}; '
                f'{rewritten} dependent row(s) rewritten.'
            )
        self._export(options['data_dir'])

    def _check_options(self, level, options):
        """Refuse options the level doesn't take, and missing required ones."""
        given = {
            name
            for name in (
                'label',
                'merge_into',
                'force',
                'reference_label',
                'csl_json',
            )
            if options[name] not in (None, False)
        }
        unexpected = given - LEVEL_OPTIONS.get(level, OTHER_LEVEL_OPTIONS)
        if unexpected:
            names = ', '.join(f'--{name}' for name in sorted(unexpected))
            raise CommandError(f'{level} does not take {names}.')
        if level == 'facility':
            if ('label' in given) == ('merge_into' in given):
                raise CommandError(
                    'facility needs --label or --merge_into, not both.'
                )
            if 'force' in given and 'merge_into' not in given:
                raise CommandError('--force goes with --merge_into.')
        elif level == 'reference':
            if not given:
                raise CommandError(
                    'reference needs --reference_label, --csl_json or both.'
                )
        elif 'label' not in given:
            raise CommandError(f'{level} needs --label.')

    def _find(self, model, id_field, identifier):
        """Return the record with this exact id; name any case-only matches."""
        try:
            return model.objects.get(**{id_field: identifier})
        except model.DoesNotExist:
            near = model.objects.filter(**{f'{id_field}__iexact': identifier})
            hint = ', '.join(repr(getattr(r, id_field)) for r in near)
            raise CommandError(
                f'No {model.__name__.lower()} has the id {identifier!r}'
                + (f' (ids match case; did you mean {hint}?)' if hint else '.')
            ) from None

    def _validate_label(self, label):
        # save() doesn't run validators, so check here.
        try:
            validate_label(label)
        except ValidationError as exc:
            raise CommandError(
                f'Invalid label {label!r}: {exc.messages[0]}'
            ) from exc

    def _prepare_reference(self, ref, options):
        """
        Validate a reference change through ReferenceSerializer.

        Returns:
            tuple: The bound serializer, the new reference id, and whether
                anything changes.
        """
        data = {}
        if options['reference_label'] is not None:
            data['reference_label'] = options['reference_label']
        if options['csl_json']:
            try:
                with open(options['csl_json'], 'r', encoding='utf-8') as f:
                    data['csl_data'] = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                raise CommandError(f'Cannot read --csl_json: {exc}') from exc
            if not isinstance(data['csl_data'], dict):
                raise CommandError('--csl_json must hold one CSL-JSON object.')

        # The serializer runs the label validator and the CSL checks, and
        # strips the CSL 'id'.
        serializer = ReferenceSerializer(ref, data=data, partial=True)
        if not serializer.is_valid():
            lines = '\n'.join(
                f'    - {line}' for line in _flatten_detail(serializer.errors)
            )
            raise CommandError(f'Invalid reference change:\n{lines}')
        label = serializer.validated_data.get('reference_label', ref.reference_label)
        csl_data = serializer.validated_data.get('csl_data', ref.csl_data)
        changed = label != ref.reference_label or csl_data != ref.csl_data
        return serializer, derive_reference_id(label, csl_data), changed

    def _check_clashes(self, level, record, old_id, new_id, label):
        """Refuse a new id that another record holds, ignoring case."""
        model, id_field, _ = LEVELS[level]
        clashes = [
            f'{model.__name__} {other!r}'
            for other in model.objects
            .filter(**{f'{id_field}__iexact': new_id})
            .exclude(pk=record.pk)
            .values_list(id_field, flat=True)
        ]
        if level == 'reference':
            # Unlabelled programs take the reference id; this reference's own
            # move with it.
            programs = Program.objects.filter(program_id__iexact=new_id).exclude(
                reference_id=old_id, label=''
            )
            clashes += [f'Program {p.program_id!r}' for p in programs]
        elif level == 'program' and label:
            # A program label must not take a reference's id.
            refs = Reference.objects.filter(reference_id__iexact=new_id)
            clashes += [f'Reference {r.reference_id!r}' for r in refs]
        if clashes:
            raise CommandError(
                f'The new id {new_id!r} clashes with {", ".join(clashes)} (ids '
                'are unique regardless of case). Nothing was written.'
            )

    def _check_in_step(self, data_dir):
        """Refuse unless an export of the database matches data_dir byte for byte."""
        with tempfile.TemporaryDirectory() as export_dir:
            call_command('export_data', output_dir=export_dir, stdout=StringIO())
            differing = [
                name
                for name in sorted(os.listdir(export_dir))
                if not os.path.exists(os.path.join(data_dir, name))
                or not filecmp.cmp(
                    os.path.join(export_dir, name),
                    os.path.join(data_dir, name),
                    shallow=False,
                )
            ]
        if differing:
            raise CommandError(
                f'The database does not match {data_dir} (differs: '
                f'{", ".join(differing)}), so the export would undo those '
                'changes. Build a fresh database from the current JSON first:\n'
                '    rm db.sqlite3 && python manage.py migrate && python manage.py ingest'
            )

    def _merge(self, source, target_label, force, data_dir):
        """Repoint a facility's specimens to another facility, then delete it."""
        target = self._find(Facility, 'label', target_label)
        if target.pk == source.pk:
            raise CommandError('A facility cannot be merged into itself.')
        discarded = [
            f'    {field}: {getattr(source, field)!r} (keeping {getattr(target, field)!r})'
            for field in ('name', 'location', 'notes')
            if getattr(source, field)
            and getattr(source, field) != getattr(target, field)
        ]
        if discarded and not force:
            raise CommandError(
                f'Merging {source.label!r} into {target.label!r} would discard:\n'
                + '\n'.join(discarded)
                + '\nRe-run with --force to discard them. Nothing was written.'
            )
        self._check_in_step(data_dir)
        if discarded:
            self.stdout.write('Discarding:\n' + '\n'.join(discarded))

        try:
            with transaction.atomic():
                rewritten = cascade(Facility, source.label, target.label)
                source.delete()
                connection.check_constraints()
        except IntegrityError as exc:
            raise CommandError(f'Rolled back; nothing was written: {exc}') from exc
        self.stdout.write(
            f'Merged facility {source.label!r} into {target.label!r}; '
            f'{rewritten} specimen(s) repointed.'
        )

    def _export(self, data_dir):
        # Only after the transaction has committed, so a rollback never
        # reaches the JSON.
        call_command('export_data', output_dir=data_dir, stdout=StringIO())
        self.stdout.write(f'Exported to {data_dir}.\n{FIXTURE_STEPS}')
