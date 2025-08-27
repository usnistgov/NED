import json
import os
import jsonschema
from django.conf import settings
from rest_framework import serializers
from ned_app.models import (
    Reference,
    Component,
    FragilityModel,
    Experiment,
    ExperimentFragilityModelBridge,
    FragilityCurve,
)


class ReferenceSerializer(serializers.ModelSerializer):
    csl_data = serializers.JSONField()
    # Make auto-populated fields optional since they'll be set by the model's save() method
    title = serializers.CharField(required=False, allow_blank=True)
    author = serializers.CharField(required=False, allow_blank=True)
    year = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Reference
        fields = '__all__'
        # exclude = ('field_abc',)  # useful if there are any exclusions to consider

    def validate_csl_data(self, value):
        """Validate csl_data against CSL-JSON schema and required fields."""
        if not value:
            raise serializers.ValidationError('csl_data is required')

        # Check for required keys and non-empty values
        if 'title' not in value or not value['title']:
            raise serializers.ValidationError(
                "csl_data must contain a non-empty 'title' field"
            )

        if 'author' not in value or not value['author']:
            raise serializers.ValidationError(
                "csl_data must contain a non-empty 'author' field"
            )

        # Check for valid issued year
        if 'issued' not in value:
            raise serializers.ValidationError(
                "csl_data must contain an 'issued' field"
            )

        issued = value['issued']
        if 'date-parts' not in issued:
            raise serializers.ValidationError(
                "csl_data 'issued' field must contain 'date-parts'"
            )

        date_parts = issued['date-parts']
        if not date_parts or len(date_parts) == 0 or len(date_parts[0]) == 0:
            raise serializers.ValidationError(
                "csl_data 'issued' field must contain valid date-parts with at least a year"
            )

        year = date_parts[0][0]
        if not isinstance(year, int) or year <= 0:
            raise serializers.ValidationError(
                "csl_data 'issued' field must contain a valid year"
            )

        # Load CSL schema for validation
        schema_path = os.path.join(
            settings.BASE_DIR, 'ned_app', 'schemas', 'csl-data.json'
        )
        try:
            with open(schema_path, 'r') as f:
                csl_schema = json.load(f)
        except FileNotFoundError:
            raise serializers.ValidationError(
                f'CSL schema not found at {schema_path}'
            )

        try:
            jsonschema.validate([value], csl_schema)
        except jsonschema.ValidationError as e:
            raise serializers.ValidationError(f'CSL data validation failed: {e}')

        return value

    # create the Reference record in the database via the framework
    def create(self, json_data) -> Reference:
        # 'json_data' is simply seen as a kwargs input...
        reference: Reference = Reference.objects.create(**json_data)

        return reference


class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = ['id', 'name']


class FragilityModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = FragilityModel
        fields = '__all__'

    # create the Fragility Model record in the database via the framework
    def create(self, json_data) -> FragilityModel:
        # 'json_data' is simply seen as a kwargs input...
        fragility_model: FragilityModel = FragilityModel.objects.create(**json_data)

        return fragility_model


class ExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experiment
        fields = '__all__'

    # create the Experiment record in the database via the framework
    def create(self, json_data) -> Experiment:
        # 'json_data' is simply seen as a kwargs input...
        experiment: Experiment = Experiment.objects.create(**json_data)

        return experiment


class ExperimentFragilityModelBridgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentFragilityModelBridge
        fields = '__all__'

    def create(self, json_data) -> ExperimentFragilityModelBridge:
        # 'json_data' is simply seen as a kwargs input...
        bridge: ExperimentFragilityModelBridge = (
            ExperimentFragilityModelBridge.objects.create(**json_data)
        )

        return bridge


class FragilityCurveSerializer(serializers.ModelSerializer):
    class Meta:
        model = FragilityCurve
        fields = '__all__'

    def create(self, json_data) -> FragilityCurve:
        # 'json_data' is simply seen as a kwargs input...
        curve: FragilityCurve = FragilityCurve.objects.create(**json_data)

        return curve
