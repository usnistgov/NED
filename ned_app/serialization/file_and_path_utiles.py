import os

PARENT_RESOURCES_DIR = 'resources'
DATA_DIR = os.path.join(PARENT_RESOURCES_DIR, 'data')


def build_path_from_cwd(relative_path: str) -> str:
    return os.path.join(os.getcwd(), relative_path)


def get_data_dir() -> str:
    return build_path_from_cwd(DATA_DIR)


def build_json_data_file_path(json_data_filename: str) -> str:
    return os.path.join(get_data_dir(), json_data_filename)
