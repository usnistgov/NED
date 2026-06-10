import csv
import json
import os

from ned_app.serialization.file_and_path_utiles import build_json_data_file_path


_INT_FIELDS = {'ds_rank', 'num_observations'}
_FLOAT_FIELDS = {'edp_value', 'alt_edp_value', 'median', 'beta', 'probability'}


def load_json(filename):
    """
    Load the contents of a canonical JSON data file.

    Args:
        filename (str): JSON filename within resources/data/.

    Returns:
        list[dict]: Parsed records, or an empty list if the file does not exist.
    """
    filepath = build_json_data_file_path(filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(filename, data):
    """
    Write records to a canonical JSON data file.

    Args:
        filename (str): JSON filename within resources/data/.
        data (list[dict]): Records to serialize.
    """
    filepath = build_json_data_file_path(filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, sort_keys=True, ensure_ascii=True)
        f.write('\n')


def build_pk_set(records, pk_fields):
    """
    Build a set of existing primary-key tuples from loaded JSON records.

    Args:
        records (list[dict]): Existing JSON records.
        pk_fields (list[str]): Field names composing the primary key.

    Returns:
        set[tuple[str, ...]]: Set of primary key tuples.
    """
    pk_set = set()
    for rec in records:
        if '_comment' in rec:
            continue
        pk_tuple = tuple(str(rec.get(f, '') or '') for f in pk_fields)
        pk_set.add(pk_tuple)
    return pk_set


def build_fk_set(json_file, key):
    """
    Build a set of valid foreign key values from a JSON reference file.

    The special sentinel key '_fragility_model_id' derives the auto-generated
    fragility_model_id by combining the reference and model_id fields
    (e.g. 'REF-2020|fra001'), matching the value stored in dependent files.

    Args:
        json_file (str): JSON filename within resources/data/.
        key (str): Field name to extract, or '_fragility_model_id'.

    Returns:
        set[str]: Set of valid key values.
    """
    records = load_json(json_file)
    if key == '_fragility_model_id':
        result = set()
        for rec in records:
            if '_comment' in rec:
                continue
            ref = rec.get('reference', '')
            model_id = rec.get('model_id', '')
            result.add(f'{ref}|{model_id}' if ref else model_id)
        return result
    return {str(rec[key]) for rec in records if '_comment' not in rec and key in rec}


def read_csv(filepath):
    """
    Read all rows from a CSV file.

    Args:
        filepath (str): Path to the CSV file.

    Returns:
        list[dict]: Rows as dicts keyed by header column names.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
    """
    with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader)


def coerce_value(field, val):
    """
    Coerce a CSV string value to the appropriate Python type for JSON.

    Args:
        field (str): The field name.
        val (str): The raw string value from the CSV.

    Returns:
        int | float | str | None: The coerced value.
    """
    if val == '' or val is None:
        if field in _INT_FIELDS or field in _FLOAT_FIELDS:
            return None
        return val
    if field in _INT_FIELDS:
        try:
            return int(val)
        except ValueError:
            return val
    if field in _FLOAT_FIELDS:
        try:
            return float(val)
        except ValueError:
            return val
    return val


def fragility_model_id(reference, model_id):
    """
    Derive the auto-generated fragility_model_id string.

    Args:
        reference (str): The reference_id value, or empty string if none.
        model_id (str): The model_id value.

    Returns:
        str: The computed fragility_model_id.
    """
    return f'{reference}|{model_id}' if reference else model_id
