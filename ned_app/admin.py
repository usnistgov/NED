from django.contrib import admin
from django.template.loader import get_template
from django.utils.translation import gettext as _

from ned_app.models import (
    Component,
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
)


# Register your models here.
@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = (
        'reference_id',
        'title',
        'author',
        'year',
        'study_type',
        'comp_type',
    )


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('observation_id', 'test', 'label')


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('id', 'name', 'component_id')
    readonly_fields = (
        'component_id',
        'major_group',
        'group',
        'element',
        'subelement',
    )


@admin.register(FragilityCurve)
class FragilityCurveAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('fragility_model', 'ds_rank', 'ds_description')


@admin.register(FragilityModel)
class FragilityModelAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = (
        'fragility_model_id',
        'reference',
        'model_id',
        'contributor',
        'source',
    )


@admin.register(ObservationFragilityModelBridge)
class ObservationFragilityModelBridgeAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('observation', 'fragility_model')


@admin.register(ComponentFragilityModelBridge)
class ComponentFragilityModelBridgeAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('component', 'fragility_model')


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('label', 'name', 'location')


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('program_id', 'reference', 'name')
    readonly_fields = ('program_id',)


@admin.register(Specimen)
class SpecimenAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('specimen_id', 'program', 'facility', 'name')
    readonly_fields = ('specimen_id',)


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('test_id', 'specimen', 'test_order', 'test_type')
    readonly_fields = ('test_id',)
