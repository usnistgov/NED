import csv
import json
import os
import shutil
import tempfile

from ned_app.serialization.file_and_path_utiles import build_json_data_file_path


_INT_FIELDS = {'ds_rank', 'num_observations'}
_FLOAT_FIELDS = {'edp_value', 'alt_edp_value', 'median', 'beta', 'probability'}
_BOOL_FIELDS = {'pdf_saved'}


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


def _dump_json(filepath, data):
    """
    Serialize records to a single JSON file in canonical format.

    Args:
        filepath (str): Absolute path to write.
        data (list[dict]): Records to serialize.
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, sort_keys=True, ensure_ascii=True)
        f.write('\n')


def write_json(filename, data):
    """
    Write records to a canonical JSON data file, crash-safely.

    Args:
        filename (str): JSON filename within resources/data/.
        data (list[dict]): Records to serialize.
    """
    write_json_files({filename: data})


def write_json_files(file_data_map):
    """
    Write several canonical JSON files as an all-or-nothing batch.

    Each target file that already exists is backed up first. If any write —
    or an interruption such as Ctrl+C — fails partway through, every target
    is rolled back to its original state (existing files restored, newly
    created files removed) before the error propagates. This prevents a crash
    mid-import from leaving the canonical files in a mutually inconsistent
    state (e.g. fragility models written but their curves missing). Backups
    are discarded once all writes succeed.

    Args:
        file_data_map (dict[str, list]): Maps each JSON filename (within
            resources/data/) to the full record list to write.
    """
    paths = {name: build_json_data_file_path(name) for name in file_data_map}

    with tempfile.TemporaryDirectory() as backup_dir:
        backups = {}
        for name, path in paths.items():
            if os.path.exists(path):
                backup_path = os.path.join(backup_dir, name)
                shutil.copy2(path, backup_path)
                backups[name] = backup_path

        try:
            for name, data in file_data_map.items():
                _dump_json(paths[name], data)
        except BaseException:
            for name, path in paths.items():
                if name in backups:
                    shutil.copy2(backups[name], path)
                elif os.path.exists(path):
                    os.remove(path)
            raise


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


def read_csv(filepath):
    """
    Read all rows from a CSV file.

    Args:
        filepath (str): Path to the CSV file.

    Returns:
        tuple[list[str], list[dict]]: The header column names and the rows as
        dicts keyed by those column names.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
    """
    with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def find_unknown_columns(actual_columns, expected_columns):
    """
    Return CSV header columns that are not recognized for the target model.

    Used to warn about typos in column headers (e.g. 'edp_val' for
    'edp_value'). A misspelled *optional* column would otherwise be silently
    dropped, leaving the real field null with no error raised downstream.

    Args:
        actual_columns (Iterable[str]): Column names from the CSV header.
        expected_columns (Iterable[str]): Column names the model accepts.

    Returns:
        list[str]: Sorted unrecognized column names (blanks excluded).
    """
    unknown = set(actual_columns) - set(expected_columns)
    unknown.discard('')
    unknown.discard(None)
    return sorted(unknown)


def coerce_value(field, val):
    """
    Coerce a CSV string value to the appropriate Python type for JSON.

    Unparsable numeric/boolean values are returned unchanged; producing valid
    JSON is the goal here, and any type errors surface when the data is ingested.

    Args:
        field (str): The field name.
        val (str): The raw string value from the CSV.

    Returns:
        int | float | bool | str | None: The coerced value.
    """
    if val == '' or val is None:
        if field in _INT_FIELDS or field in _FLOAT_FIELDS:
            return None
        return val
    if field in _BOOL_FIELDS:
        lowered = val.strip().lower() if isinstance(val, str) else val
        if lowered == 'true':
            return True
        if lowered == 'false':
            return False
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
