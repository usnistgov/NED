from django.contrib import admin
from django.template.loader import get_template
from django.utils.translation import gettext as _

from ned_app.models import Reference, Component, Experiment, FragilityCurve, FragilityModel, ExperimentFragilityModelBridge, NistirMajorGroupElement, NistirGroupElement, NistirIndivElement, NistirSubElement

# Register your models here.
@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('id','title','author','year')

@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('id','reference','specimen')

@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('id','name','nistir_subelement')

@admin.register(NistirMajorGroupElement)
class NistIrMajorGroupElementAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('id','name')

@admin.register(NistirGroupElement)
class NistIrGroupElementAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('id','name')

@admin.register(NistirIndivElement)
class NistIrIndivElementAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('id','name')

@admin.register(NistirSubElement)
class NistirSubElementAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('id','name')

@admin.register(FragilityCurve)
class FragilityCurveAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('fragility_model','reviewer','reference')

@admin.register(FragilityModel)
class FragilityModelAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('id','component')

@admin.register(ExperimentFragilityModelBridge)
class ExperimentFragilityModelBridgeAdmin(admin.ModelAdmin):
    # how column data is displayed in the report for all entered data
    list_display = ('experiment','fragility_model')
