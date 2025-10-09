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
        fields = [
            'id',
            'title',
            'author',
            'year',
            'study_type',
            'comp_type',
            'pdf_saved',
            'csl_data',
        ]

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


class ComponentSerializer(serializers.ModelSerializer):
    # Make sure the id is not sought by the serializer
    id = serializers.CharField(read_only=True)
    # Make component_id required and writeable
    component_id = serializers.CharField(required=True)

    class Meta:
        model = Component
        fields = [
            'id',
            'name',
            'component_id',
            'major_group',
            'group',
            'element',
            'subelement',
        ]


class FragilityModelSerializer(serializers.ModelSerializer):
    component = serializers.SlugRelatedField(
        slug_field='component_id', queryset=Component.objects.all()
    )

    class Meta:
        model = FragilityModel
        fields = [
            'id',
            'p58_fragility',
            'component',
            'comp_detail',
            'material',
            'size_class',
            'comp_description',
        ]


class ExperimentSerializer(serializers.ModelSerializer):
    reference = serializers.SlugRelatedField(
        slug_field='id', queryset=Reference.objects.all()
    )
    component = serializers.SlugRelatedField(
        slug_field='component_id', queryset=Component.objects.all()
    )

    class Meta:
        model = Experiment
        fields = [
            'id',
            'reference',
            'specimen',
            'specimen_inspection_sequence',
            'reviewer',
            'component',
            'comp_detail',
            'material',
            'size_class',
            'test_type',
            'loading_protocol',
            'peak_test_amplitude',
            'location',
            'governing_design_standard',
            'design_objective',
            'comp_description',
            'ds_description',
            'prior_damage',
            'prior_damage_repaired',
            'edp_metric',
            'edp_unit',
            'edp_value',
            'alt_edp_metric',
            'alt_edp_unit',
            'alt_edp_value',
            'ds_rank',
            'ds_class',
            'notes',
        ]


class ExperimentFragilityModelBridgeSerializer(serializers.ModelSerializer):
    experiment = serializers.SlugRelatedField(
        slug_field='id', queryset=Experiment.objects.all()
    )
    fragility_model = serializers.SlugRelatedField(
        slug_field='id', queryset=FragilityModel.objects.all()
    )

    class Meta:
        model = ExperimentFragilityModelBridge
        fields = [
            'id',
            'experiment',
            'fragility_model',
        ]


class FragilityCurveSerializer(serializers.ModelSerializer):
    fragility_model = serializers.SlugRelatedField(
        slug_field='id', queryset=FragilityModel.objects.all()
    )
    reference = serializers.SlugRelatedField(
        slug_field='id', queryset=Reference.objects.all()
    )

    class Meta:
        model = FragilityCurve
        fields = [
            'fragility_model',
            'reviewer',
            'source',
            'basis',
            'num_observations',
            'reference',
            'edp_metric',
            'edp_unit',
            'ds_rank',
            'ds_description',
            'median',
            'beta',
            'probability',
        ]
