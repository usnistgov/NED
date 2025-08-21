import os
import json
import csv
from typing import List

from ned_app.serialization.file_and_path_utiles import build_json_data_file_path
from ned_app.serialization.custom_exceptions import (
    DataFileLoadError,
    DataFileDeserializationError,
)
from ned_app.serialization.serializer import (
    ReferenceSerializer,
    ComponentSerializer,
    FragilityModelSerializer,
    ExperimentFragilityModelBridgeSerializer,
    FragilityCurveSerializer,
    NistirMajorGroupElementSerializer,
    ExperimentSerializer,
)
from ned_app.models import (
    Reference,
    Component,
    FragilityModel,
    ExperimentFragilityModelBridge,
    NistirMajorGroupElement,
    Experiment,
    FragilityCurve,
)

REFERENCES_DATA_FILENAME = 'reference.json'
COMPONENTS_DATA_FILENAME = 'component.json'
NISTIR_DATA_FILENAME = 'nistir.json'
FRAGILITY_MODEL_DATA_FILENAME = 'fragility_model.json'
EXPERIMENT_DATA_FILENAME = 'experiment.json'
EXPERIMENT_FRAGILITY_BRIDGE_DATA_FILENAME = 'experiment_fragility_bridge.json'
FRAGILITY_CURVE_DATA_FILENAME = 'fragility_curve.json'

PROCESS_REFERENCES = True
PROCESS_COMPONENTS = True
PROCESS_NISTIRS = True
PROCESS_FRAGILITY_MODELS = True
PROCESS_EXPERIMENTS = True
PROCESS_EXPERIMENT_FRAGILITY_PAIRS = True
PROCESS_FRAGILITY_CURVES = True

"""
Import data from a specified data file, converting it for JSON,
readying it for import
"""


def load_data(data_filename: str):
    # import and digest all References data (should any exist)
    data_filepath = build_json_data_file_path(data_filename)
    if os.path.exists(data_filepath):
        data_file_content = None
        try:
            with open(data_filepath, 'r') as file:
                data_file_content = json.load(file)
        except FileNotFoundError as ex:
            err_msg = f"A '{ex.__class__.__name__}' exception was trapped while trying to load the data file: {data_filepath}. Message: {ex}"
            raise DataFileLoadError(err_msg)
        except json.JSONDecodeError as ex:
            err_msg = f"A '{ex.__class__.__name__}' exception was trapped while trying to parse the following data file content: {data_filepath}. Message: {ex}"
            raise DataFileLoadError(err_msg)

        return data_file_content


def import_avail_data() -> None:
    if PROCESS_REFERENCES:
        # process References data
        print('processing JSON Reference data...')
        loaded_data = load_data(REFERENCES_DATA_FILENAME)
        if loaded_data:
            for item in loaded_data:
                # Check for required id field first
                if 'id' not in item:
                    err_msg = 'Reference item missing required "id" field'
                    raise DataFileDeserializationError(err_msg)

                # Expect input JSON files to have a csl_data key with CSL-JSON dictionary
                if 'csl_data' not in item or item['csl_data'] is None:
                    err_msg = f"Reference item missing required 'csl_data' field: {item.get('id', 'unknown')}"
                    raise DataFileDeserializationError(err_msg)

                references_serializer = ReferenceSerializer(data=item)
                if references_serializer.is_valid():
                    reference: Reference = (
                        references_serializer.save()
                    )  # creates and saves
                    print(f"Reference ID '{reference.id}' successfully ingested")
                else:
                    err_msg = f'There was a least one validation error on references data file deserialization: {references_serializer.errors}'
                    raise DataFileDeserializationError(err_msg)
    else:
        print('processing references bypassed')

    if PROCESS_NISTIRS:
        # process NISTIR data
        print('processing JSON NISTR data...')
        loaded_data = load_data(NISTIR_DATA_FILENAME)
        if loaded_data:
            for item in loaded_data:
                nistir_serializer = NistirMajorGroupElementSerializer(data=item)
                if nistir_serializer.is_valid():
                    nistir_major_group: NistirMajorGroupElement = (
                        nistir_serializer.save()
                    )  # creates and saves
                    print(
                        f"NISTIR Major Group Element ID '{nistir_major_group.id}' successfully ingested"
                    )
                else:
                    err_msg = f'There was a least one validation error on NISTIRs data file deserialization: {nistir_serializer.errors}'
                    raise DataFileDeserializationError(err_msg)
    else:
        print('processing NISTIRS bypassed')

    if PROCESS_COMPONENTS:
        # process Components data
        print('processing JSON Component data...')
        loaded_data = load_data(COMPONENTS_DATA_FILENAME)
        if loaded_data:
            for item in loaded_data:
                components_serializer = ComponentSerializer(data=item)
                if components_serializer.is_valid():
                    component: Component = (
                        components_serializer.save()
                    )  # creates and saves
                    print(f"Component ID '{component.id} successfully ingested")
                else:
                    err_msg = f'There was a least one validation error on components data file deserialization: {components_serializer.errors}'
                    raise DataFileDeserializationError(err_msg)
    else:
        print('processing components bypassed')

    if PROCESS_FRAGILITY_MODELS:
        # process Fragility Models data
        print('processing JSON Fragility Model data...')
        loaded_data = load_data(FRAGILITY_MODEL_DATA_FILENAME)
        if loaded_data:
            for item in loaded_data:
                fragility_models_serializer = FragilityModelSerializer(data=item)
                if fragility_models_serializer.is_valid():
                    fragility_model: FragilityModel = (
                        fragility_models_serializer.save()
                    )  # creates and saves
                    print(
                        f"Fragility Model ID '{fragility_model.id} successfully ingested"
                    )
                else:
                    err_msg = f'There was a least one validation error on fragiilty models data file deserialization: {fragility_models_serializer.errors}'
                    raise DataFileDeserializationError(err_msg)
    else:
        print('processing fragility models bypassed')

    if PROCESS_EXPERIMENTS:
        # process Experiment data
        print('processing JSON Experiment data...')
        loaded_data = load_data(EXPERIMENT_DATA_FILENAME)
        if loaded_data:
            for item in loaded_data:
                experiments_serializer = ExperimentSerializer(data=item)
                if experiments_serializer.is_valid():
                    experiment: Experiment = (
                        experiments_serializer.save()
                    )  # creates and saves
                    print(f"Experiment ID '{experiment.id} successfully ingested")
                else:
                    err_msg = f'There was a least one validation error on experiments data file deserialization: {experiments_serializer.errors}'
                    raise DataFileDeserializationError(err_msg)
    else:
        print('processing experiments bypassed')

    if PROCESS_EXPERIMENT_FRAGILITY_PAIRS:
        # process Experiment/Fragility Model paired data
        print('processing JSON Experiment/Fragility bridge data...')
        loaded_data = load_data(EXPERIMENT_FRAGILITY_BRIDGE_DATA_FILENAME)
        if loaded_data:
            for item in loaded_data:
                experiment_fragility_serializer = (
                    ExperimentFragilityModelBridgeSerializer(data=item)
                )
                if experiment_fragility_serializer.is_valid():
                    bridge: ExperimentFragilityModelBridge = (
                        experiment_fragility_serializer.save()
                    )  # creates and saves
                    print(
                        f"Experiment / Fragility Bridge ID '{bridge.id} successfully ingested"
                    )
                else:
                    err_msg = f'There was a least one validation error on experiment/fragility bridge data file deserialization: {experiment_fragility_serializer.errors}'
                    raise DataFileDeserializationError(err_msg)
    else:
        print('processing experiment-fragility pairs bypassed')

    if PROCESS_FRAGILITY_CURVES:
        # process Fragility Curve data
        print('processing JSON Fragility Curve data...')
        loaded_data = load_data(FRAGILITY_CURVE_DATA_FILENAME)
        if loaded_data:
            for item in loaded_data:
                fragility_curve_serializer = FragilityCurveSerializer(data=item)
                if fragility_curve_serializer.is_valid():
                    curve: FragilityCurve = (
                        fragility_curve_serializer.save()
                    )  # creates and saves
                    print(f"Fragility Curve ID '{curve.id} successfully ingested")
                else:
                    err_msg = f'There was a least one validation error on fragility curve data file deserialization: {fragility_curve_serializer.errors}'
                    raise DataFileDeserializationError(err_msg)
    else:
        print('processing fragility curve data bypassed')
