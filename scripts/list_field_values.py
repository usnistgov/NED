#!/usr/bin/env python
"""List the values already used for each component's specimen fields.

Contributors filling in ``resources/import_templates/observation_template.csv``
should reuse an existing spelling where one fits, so the same detail is not
recorded three ways. This script writes those spellings, per component, to
``resources/import_templates/README.md``:

    * a fixed header saying the file is generated and is a snapshot;
    * one heading per component in ``component.json`` (id and name, sorted by
      id), listing the distinct non-blank values of ``VALUE_FIELDS`` found in
      ``specimen.json``, sorted case-insensitively.

The script owns the whole file: rerun it after the data changes, never edit
the output by hand. It writes no counts, so the file changes only when a value
does, and it is deterministic, so rerunning it on unchanged data gives the
same bytes. Nothing checks that the file is current: it is a starting point,
not a vocabulary.

It reads the JSON directly and needs no database or Django.

Usage (run from anywhere; paths are resolved relative to this file):

    python scripts/list_field_values.py
    python scripts/list_field_values.py --data_dir path/to/data --output out.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

NED = Path(__file__).resolve().parent.parent
DATA_DIR = NED / 'resources' / 'data'
OUTPUT = NED / 'resources' / 'import_templates' / 'README.md'

# The specimen fields whose values are listed, in the template's order.
VALUE_FIELDS = [
    'comp_detail',
    'material',
    'size_class',
    'design_objective',
    'governing_design_standard',
]

# Links are relative to the output's default location,
# resources/import_templates/.
HEADER = """\
# Existing specimen values by component

> **Generated file: do not edit.** `scripts/list_field_values.py` writes this
> file from `resources/data/specimen.json` and `component.json`. It is a
> snapshot of the data when the script last ran; rerun the script to refresh
> it.

When you fill in the observation template, check here for the spellings
already used for your component, and reuse one where it fits rather than
recording the same detail a new way. A new value is fine when none fits.
Values are listed as stored, sorted without regard to case, except that `<`
and `>` are escaped for Markdown (`&lt;` and `&gt;` in this file's source) and
a line break inside a value becomes a space.

See [Using the `import_observation` Command](../../README.md#using-the-import_observation-command)
for the template's columns, and the
[data dictionary](../../ui/assets/data_dictionary.md#specimen) for what each
field means.
"""


def load(path: Path) -> list[dict]:
    """Read one JSON data file."""
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def display(value: str) -> str:
    """A value as one Markdown line.

    ``<`` and ``>`` are escaped so values such as ``> 144 ft²`` aren't read as
    HTML or a block quote; a line break inside a value becomes a space so the
    value stays one bullet.
    """
    one_line = ' '.join(value.strip().splitlines())
    return one_line.replace('<', '&lt;').replace('>', '&gt;')


def collect(specimens: list[dict]) -> dict[str, dict[str, set[str]]]:
    """Map component_id -> field -> the set of displayed non-blank values."""
    values: dict[str, dict[str, set[str]]] = {}
    for specimen in specimens:
        fields = values.setdefault(specimen.get('component', ''), {})
        for field in VALUE_FIELDS:
            value = specimen.get(field) or ''
            if value.strip():
                fields.setdefault(field, set()).add(display(value))
    return values


def render(components: list[dict], specimens: list[dict]) -> str:
    """The whole output file."""
    values = collect(specimens)
    parts = [HEADER]
    for component in sorted(components, key=lambda c: c['component_id']):
        component_id = component['component_id']
        parts.append(f'\n## {component_id}: {display(component.get("name", ""))}\n')
        fields = values.get(component_id, {})
        if not fields:
            parts.append('\nNo values recorded yet.\n')
            continue
        for field in VALUE_FIELDS:
            if field not in fields:
                continue
            # casefold() groups spellings that differ only in case; the value
            # itself breaks ties, so the order never depends on input order.
            ordered = sorted(fields[field], key=lambda v: (v.casefold(), v))
            bullets = ''.join(f'- {value}\n' for value in ordered)
            parts.append(f'\n**`{field}`**\n\n{bullets}')
    return ''.join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        '--data_dir',
        type=Path,
        default=DATA_DIR,
        help='the JSON data directory (default: resources/data/)',
    )
    ap.add_argument(
        '--output',
        type=Path,
        default=OUTPUT,
        help='the file to write (default: resources/import_templates/README.md)',
    )
    args = ap.parse_args()

    try:
        components = load(args.data_dir / 'component.json')
        specimens = load(args.data_dir / 'specimen.json')
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f'error: cannot read the data in {args.data_dir}: {exc}')

    text = render(components, specimens)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print(f'Wrote {args.output} ({len(components)} components).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
