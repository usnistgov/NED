"""
One-time transformation command for the reference_id auto-generation feature.

Rewrites the legacy reference_id values in the canonical JSON files to the new
derived ids (``<reference_label>-<year>`` or
``<normalized_first_author_surname>-<year>``). The old->new maps are built from
the database FK graph (authoritative), so applying them to the JSON files is a
plain dictionary lookup rather than fragile string parsing of the composite
``<reference>|<model_id>`` fragility-model ids.

Intended workflow (run exactly once):
    1. Build a database from the CURRENT canonical data while Reference.save()
       still stores the legacy reference_id (i.e. before the derivation is wired
       into save()): ``flush`` + ``ingest``.
    2. Run this command: ``python manage.py migrate_reference_ids``.
    3. Wire the derivation into the model/serializer/ingest/export and re-ingest
       the rewritten canonical data to verify the round-trip.

This command is disposable; it is removed once the transformation is committed.
"""

import json
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from ned_app.models import Reference, FragilityModel, derive_reference_id
from ned_app.serialization.file_and_path_utiles import build_json_data_file_path


class Command(BaseCommand):
    help = (
        'One-time: rewrite legacy reference_id values in the canonical JSON '
        'files to the new derived ids, using old->new maps built from the DB.'
    )

    def handle(self, *args, **options):
        """Build old->new maps from the DB and rewrite the canonical JSON files."""
        # --- Build the reference-id map (old -> new) from the DB FK graph. ---
        ref_map = {}
        for ref in Reference.objects.all():
            ref_map[ref.reference_id] = derive_reference_id(
                ref.reference_label, ref.csl_data
            )

        new_ids = list(ref_map.values())
        duplicates = [rid for rid, n in Counter(new_ids).items() if n > 1]
        if duplicates:
            raise CommandError(
                f'Derived reference ids are not globally unique: {duplicates}. '
                'Resolve with reference_label values before migrating.'
            )

        # --- Build the fragility-model-id map (old -> new) from the DB. ---
        # fragility_model_id is '<reference_id>|<model_id>', so it shifts with
        # the reference id. Follow each model's FK to get its (old) reference id.
        fm_map = {}
        for fm in FragilityModel.objects.all():
            new_ref = ref_map[fm.reference_id]
            fm_map[fm.fragility_model_id] = f'{new_ref}|{fm.model_id}'

        # --- Rewrite each canonical file. ---
        self._rewrite('reference.json', self._drop_reference_id)
        self._rewrite('experiment.json', self._field_mapper('reference', ref_map))
        self._rewrite(
            'fragility_model.json', self._field_mapper('reference', ref_map)
        )
        for filename in (
            'component_fragility_model_bridge.json',
            'experiment_fragility_model_bridge.json',
            'fragility_curve.json',
        ):
            self._rewrite(filename, self._field_mapper('fragility_model', fm_map))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nRewrote reference ids across canonical files '
                f'({len(ref_map)} references, {len(fm_map)} fragility models).'
            )
        )

    @staticmethod
    def _drop_reference_id(record):
        """Remove the (now-derived) reference_id from a reference record."""
        record.pop('reference_id', None)
        return record

    @staticmethod
    def _field_mapper(field, mapping):
        """Return a record transformer that maps ``field`` through ``mapping``."""

        def transform(record):
            old = record[field]
            if old not in mapping:
                raise CommandError(
                    f"Value '{old}' in field '{field}' has no mapping; the "
                    'canonical data is out of sync with the database.'
                )
            record[field] = mapping[old]
            return record

        return transform

    def _rewrite(self, filename, transform):
        """Load a canonical JSON file, transform each record, and write it back."""
        path = build_json_data_file_path(filename)
        with open(path, 'r') as f:
            data = json.load(f)
        data = [transform(record) for record in data]
        with open(path, 'w') as f:
            json.dump(data, f, indent=4, sort_keys=True)
        self.stdout.write(f'  rewrote {filename} ({len(data)} records)')
