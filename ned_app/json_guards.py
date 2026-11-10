"""
JSON-level guards on a data directory (resources/data/ by default).

Derived ids are not stored in the JSON, and every child file stores its
parent's derived id, so these checks catch an id that can't be built, a
case-only duplicate and a dangling parent before ingest does.
"""

import json
import os

from django.core.exceptions import ValidationError

from ned_app.models import derive_reference_id
from ned_app.validators import validate_label

# How each file's derived id is rebuilt from a record, as ingest derives it
# for its lookup.
DERIVE_ID = {
    'reference': lambda r: derive_reference_id(
        r.get('reference_label', '') or '', r['csl_data']
    ),
    'facility': lambda r: r['label'],
    'program': lambda r: r.get('label') or r['reference'],
    'specimen': lambda r: f'{r["program"]}|{r["label"]}',
    'test': lambda r: f'{r["specimen"]}|{r["label"]}',
    'observation': lambda r: f'{r["test"]}|{r["label"]}',
}

# (file, foreign-key key, parent file, nullable)
PARENT_CHECKS = [
    ('program', 'reference', 'reference', False),
    ('specimen', 'program', 'program', False),
    ('specimen', 'facility', 'facility', False),
    ('specimen', 'reference', 'reference', True),
    ('specimen', 'component', 'component', False),
    ('test', 'specimen', 'specimen', False),
    ('observation', 'test', 'test', False),
    # Ingest's lookups are case-sensitive, so a bridge row must match an
    # observation_id exactly.
    ('observation_fragility_model_bridge', 'observation', 'observation', False),
]


def derived_id_problems(records, derive):
    """
    Check that every record's derived id can be derived and is unique.

    Uniqueness ignores case, as the Lower(...) constraints do.

    Args:
        records (list[dict]): Records from one JSON file.
        derive (callable): Builds a record's derived id.

    Returns:
        list[str]: One line per problem; empty when the records are clean.
    """
    seen = {}
    problems = []
    for index, record in enumerate(records):
        try:
            derived = derive(record)
        except (KeyError, IndexError, TypeError) as exc:
            problems.append(f'record {index}: id cannot be derived ({exc!r})')
            continue
        if derived.lower() in seen:
            problems.append(
                f'{derived}: duplicates {seen[derived.lower()]} (ignoring case)'
            )
        else:
            seen[derived.lower()] = derived
    return problems


def label_problems(records, allow_blank=False):
    """
    Check that every label passes validate_label.

    Args:
        records (list[dict]): Records from one JSON file.
        allow_blank (bool): Skip blank labels (a program's label is optional).

    Returns:
        list[str]: One line per problem; empty when the records are clean.
    """
    problems = []
    for index, record in enumerate(records):
        label = record.get('label', '')
        if allow_blank and not label:
            continue
        try:
            validate_label(label)
        except ValidationError as exc:
            problems.append(f'record {index}: label {label!r}: {exc.messages[0]}')
    return problems


def parent_problems(records, field, parent_ids, nullable=False):
    """
    Check that every record's parent string matches a parent id exactly.

    Foreign-key lookups are exact, so a parent that differs only in case does
    not resolve, even though uniqueness ignores case.

    Args:
        records (list[dict]): Records from one JSON file.
        field (str): The foreign-key key in each record.
        parent_ids (set[str]): Every id in the parent file.
        nullable (bool): Allow a null parent (an optional foreign key).

    Returns:
        list[str]: One line per problem; empty when the records are clean.
    """
    problems = []
    for index, record in enumerate(records):
        value = record.get(field)
        if value is None and nullable:
            continue
        if value not in parent_ids:
            problems.append(f'record {index}: {field} {value!r} does not resolve')
    return problems


def derivable_ids(records, derive):
    """
    Return the ids derivable from the records, skipping any that can't be.

    Args:
        records (list[dict]): Records from one JSON file.
        derive (callable): Builds a record's derived id.

    Returns:
        set[str]: The derived ids.
    """
    ids = set()
    for record in records:
        try:
            ids.add(derive(record))
        except (KeyError, IndexError, TypeError):
            continue
    return ids


def _load(path, name):
    file_path = os.path.join(path, f'{name}.json')
    # A missing file holds no records, as for ingest and the importers.
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        # Ignore the _comment key, as ingest does; a record that is only a
        # comment is a note (ingest would reject it).
        records = [
            {k: v for k, v in r.items() if k != '_comment'} for r in json.load(f)
        ]
    return [r for r in records if r]


def check_data_dir(path):
    """
    Run the derived-id, label and parent checks on a data directory.

    Covers the reference ids and the facility, program, specimen, test and
    observation files, and the observation bridge's observation ids.

    Args:
        path (str): The directory holding the JSON files.

    Returns:
        list[str]: One line per problem, prefixed with its file; empty when
            the directory is clean.
    """
    names = {check[0] for check in PARENT_CHECKS} | set(DERIVE_ID) | {'component'}
    records = {name: _load(path, name) for name in names}
    ids = {
        name: derivable_ids(records[name], derive)
        for name, derive in DERIVE_ID.items()
    }
    ids['component'] = {r['component_id'] for r in records['component']}

    problems = []
    for name, derive in DERIVE_ID.items():
        problems += [
            f'{name}.json: {p}' for p in derived_id_problems(records[name], derive)
        ]
    # Specimen, test and observation labels are required; a program's label
    # is optional.
    for name in ('facility', 'specimen', 'test', 'observation'):
        problems += [f'{name}.json: {p}' for p in label_problems(records[name])]
    problems += [
        f'program.json: {p}'
        for p in label_problems(records['program'], allow_blank=True)
    ]
    for name, field, parent, nullable in PARENT_CHECKS:
        problems += [
            f'{name}.json: {p}'
            for p in parent_problems(records[name], field, ids[parent], nullable)
        ]
    return problems
