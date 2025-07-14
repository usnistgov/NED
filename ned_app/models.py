from django.db import models
from django.utils.translation import gettext as _

"""
A good explanation of "blank = True/False" and "null = True/False"

null=True sets NULL (versus NOT NULL) on the column in your DB. Blank values for Django field types such as DateTimeField or ForeignKey will be stored as NULL in the DB.

blank determines whether the field will be required in forms. This includes the admin and your custom forms. If blank=True then the field will not be required, whereas if it's False the field cannot be blank.

The combo of the two is so frequent because typically if you're going to allow a field to be blank in your form, you're going to also need your database to allow NULL values for that field. The exception is CharFields and TextFields, which in Django are never saved as NULL. Blank values are stored in the DB as an empty string ('')
"""


# Create your models here.
class Reference(models.Model):

    class studytypeChoices(models.TextChoices):
        EXPERIMENT = 'Experiment'
        RECON = 'Historical Event'
        ANALYTICAL = 'Analytical Study'
        LIT_REVIEW = 'Lit Review'
        OTHER = 'Other'

    id = models.CharField(_("id"), primary_key=True, max_length=255)
    name = models.CharField(_("name"), max_length=255, blank = True, null = True)
    author = models.CharField(_("author"), max_length=255, blank = True, null = True)
    year = models.IntegerField(_("year"))
    study_type = models.CharField(_("study type"), max_length=50, choices=studytypeChoices.choices, default=studytypeChoices.OTHER)
    comp_type = models.CharField(_("component type"), max_length=255, blank = True, null = True)
    doi = models.URLField(_("doi"), max_length=200, blank = True, null = True)
    citation = models.CharField(_("citation"), max_length=255, blank = True, null = True)
    publication_type = models.CharField(_("publication type"), max_length=50, blank = True, null = True)
    pdf_saved = models.BooleanField(_("pdf saved"), default=False)

    class Meta:
        verbose_name = "Reference"
        verbose_name_plural = "References"

    def __str__(self):
        return self.name

class Experiment(models.Model):

    class testtypeChoices(models.TextChoices):
        DYNA_1D = 'Dynamic, uniaxial'
        DYNA_2D = 'Dynamic, bi-directional'
        DYNA_3D = 'Dynamic, 3D'
        MONO_C = 'Monotonic, compression'
        MONO_T = 'Monotonic, tension'
        MONO_M = 'Monotonic, bending'
        QUASI_1D = 'Quasi-static Cyclic, uniaxial'
        QUASI_2D = 'Quasi-static Cyclic, bi-directional'

    class edpmetricChoices(models.TextChoices):
        SDR = 'Story Drift Ratio'
        SDR_2D = 'Story Drift Ratio, bi-directional'
        PFA_H = 'Peak Floor Acceleration, horizontal'
        PFA_TABLE_H = 'Peak Table Acceleration, horizontal'
        PFA_V = 'Peak Floor Acceleration, vertical'
        PFV = 'Peak Floor Velocity'
        ROT_JOINT = 'Joint Rotation'
        FORCE_T = 'Force, tension'
        FORCE_C = 'Force, compression'
        FORCE_M = 'Force, bending'
        FORCE_V = 'Force, lateral'
        CUSTOM = 'Custom'

    class edpunitChoices(models.TextChoices):
        G = 'g'
        RATIO = 'Ratio'
        RAD = 'Radians'
        KIP = 'Kips'
        K_IN = 'k-in'
        MPS = 'Meters Per Second'
        CUSTOM = 'Custom'

    class dsclassChoices(models.TextChoices):
        NO_DAMAGE = 'No damage'
        INCONSEQUENTIAL = 'Inconsequential'
        CONSEQUENTIAL = 'Consequential'
        UNKNOWN = 'Unknown'

    id = models.CharField(_("id"), primary_key=True, max_length=255)
    reference = models.ForeignKey("Reference", on_delete=models.PROTECT)
    specimen = models.CharField(_("specimen"), max_length=255, blank = True, null = True)
    specimen_inspection_sequence = models.CharField(_("specimen inspection sequence"), max_length=255, blank = True, null = True)
    reviewer = models.CharField(_("reviewer"), max_length=50, blank = True, null = True)
    component = models.ForeignKey("Component", on_delete=models.PROTECT, default = "ABC")
    comp_detail = models.CharField(_("component detail tag"), max_length=100, blank = True, null = True)
    material = models.CharField(_("material classification tag"), max_length=100, blank = True, null = True)
    size_class = models.CharField(_("size classification tag"), max_length=100, blank = True, null = True)
    test_type = models.CharField(_("test type"), max_length=50, choices=testtypeChoices.choices)
    loading_protocol = models.CharField(_("loading protocol"), max_length=255, blank = True, null = True)
    peak_test_amplitude = models.CharField(_("peak test amplitute"), max_length=255, blank = True, null = True)
    location = models.CharField(_("location"), max_length=255, blank = True, null = True)
    governing_design_standard = models.CharField(_("governing design standard"), max_length=255, blank = True, null = True)
    design_objective = models.CharField(_("design objective"), max_length=255, blank = True, null = True)
    comp_description = models.TextField(_("component description"), blank = True, null = True)
    ds_description = models.TextField(_("damage state description"), blank = True, null = True)
    prior_damage = models.CharField(_("prior damage"), max_length=255, blank = True, null = True)
    prior_damage_repaired = models.BooleanField(_("is prior damage repaired"), blank = True, null = True)
    edp_metric = models.CharField(_("edp metric"), max_length=50, choices=edpmetricChoices.choices, blank = True, null = True)
    edp_unit = models.CharField(_("edp unit"), max_length=50, choices=edpunitChoices.choices, blank = True, null = True)
    edp_value = models.DecimalField(_("edp value"), max_digits=12, decimal_places=6, blank = True, null = True)
    alt_edp_metric = models.CharField(_("alternative edp metric"), max_length=50, choices=edpmetricChoices.choices, blank = True, null = True)
    alt_edp_unit = models.CharField(_("alternative edp unit"), max_length=50, choices=edpunitChoices.choices, blank = True, null = True)
    alt_edp_value = models.DecimalField(_("alternative edp value"), max_digits=12, decimal_places=6, blank = True, null = True)
    ds_rank = models.IntegerField(_("damage state rank"), blank = True, null = True)
    ds_class = models.CharField(_("damage state class"), max_length=50, choices=dsclassChoices.choices, blank = True, null = True)
    notes = models.TextField(_("notes"), blank = True, null = True)

    class Meta:
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"

    def __str__(self):
        return self.id

class FragilityModel(models.Model):

    id = models.CharField(_("id"), primary_key=True, max_length=255)
    p58_fragility = models.CharField(_("FEMA P-58 fragility id"), max_length=50, blank=True)
    component = models.ForeignKey("Component", on_delete=models.PROTECT)
    comp_detail = models.CharField(_("component detail tag"), max_length=100, blank = True) # NOTE: had to add 'blank = True'
    material = models.CharField(_("material classification tag"), max_length=100, blank=True)
    size_class = models.CharField(_("size classification tag"), max_length=100, blank=True)
    comp_description = models.TextField(_("component description"))

    class Meta:
        verbose_name = "Fragility Model"
        verbose_name_plural = "Fragility Models"
    
    def __str__(self):
        return self.id
    
class ExperimentFragilityModelBridge(models.Model):

    # NOTE: leaving out the following field ensures Django will create an Autofield
    # as a primary key, which autoincrements on each record entry.  This route was chosen
    # because it eliminates the need to maintain a unique record ID when injesting data from
    # external JSON files.  The reason we can get away with this (vs any other records creation
    # in other tables) is because there are no other foreign key dependencies that rely on this
    # auto generated ID.

    # id = models.IntegerField(_("id"), primary_key=True)
    experiment = models.ForeignKey("Experiment", on_delete=models.PROTECT)
    fragility_model = models.ForeignKey("FragilityModel", on_delete=models.PROTECT)

    class Meta:
        verbose_name = "Experiment - Fragility Pair"
        verbose_name_plural = "Experiment - Fragility Pairs"
    
    def __str__(self):
        return f"{self.experiment}_{self.fragility_model}"
    
class FragilityCurve(models.Model):

    class basisChoices(models.TextChoices):
        EXPERIMENT = 'Experiment'
        RECON = 'Historical Event'
        ANALYTICAL = 'Analytical Study'
        LIT_REVIEW = 'Lit Review'
        OTHER = 'Other'

    class edpmetricChoices(models.TextChoices):
        SDR = 'Story Drift Ratio'
        SDR_2D = 'Story Drift Ratio, bi-directional'
        PFA_H = 'Peak Floor Acceleration, horizontal'
        PFA_V = 'Peak Floor Acceleration, vertical'
        PFV = 'Peak Floor Velocity'
        ROT_JOINT = 'Joint Rotation'
        FORCE_T = 'Force, tension'
        FORCE_C = 'Force, compression'
        FORCE_M = 'Force, bending'
        FORCE_V = 'Force, lateral'
        CUSTOM = 'Custom'

    class edpunitChoices(models.TextChoices):
        G = 'g'
        RATIO = 'Ratio'
        RAD = 'Radians'
        KIP = 'Kips'
        K_IN = 'k-in'
        MPS = 'Meters Per Second'
        CUSTOM = 'Custom'

    # NOTE: leaving out the following field ensures Django will create an Autofield
    # as a primary key, which autoincrements on each record entry.  This route was chosen
    # because it eliminates the need to maintain a unique record ID when injesting data from
    # external JSON files.  The reason we can get away with this (vs any other records creation
    # in other tables) is because there are no other foreign key dependencies that rely on this
    # auto generated ID.
    
    # id = models.CharField(_("id"), primary_key=True, max_length=255)
    fragility_model = models.ForeignKey("FragilityModel", on_delete=models.PROTECT)
    reviewer = models.CharField(_("reviewer"), max_length=255, null=True, blank=True)
    source = models.CharField(_("source"), max_length=255, null=True, blank=True)
    basis = models.CharField(_("basis"), choices=basisChoices.choices, max_length=50, blank=True)
    num_observations = models.IntegerField(_("number of observations"), null=True, blank=True)
    reference = models.ForeignKey("Reference", on_delete=models.PROTECT)
    edp_metric = models.CharField(_("edp metric"), choices=edpmetricChoices.choices, max_length=255, null=True, blank=True)
    edp_unit = models.CharField(_("edp unit"), choices=edpunitChoices.choices, max_length=255, null=True, blank=True)
    ds_rank = models.IntegerField(_("damage state rank"), null=True, blank=True)
    ds_description = models.TextField(_("damage state description"), null=True, blank=True)
    median = models.DecimalField(_("median"), max_digits=9, decimal_places=3, null=True, blank=True)
    beta = models.DecimalField(_("beta"), max_digits=10, decimal_places=3, null=True, blank=True)
    probability = models.DecimalField(_("probability"), max_digits=3, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Fragility Curve"
        verbose_name_plural = "Fragility Curves"

    def __str__(self):
        return self.name

class Component(models.Model):

    id = models.CharField(_("id"), primary_key=True,max_length=10) # NOTE: had to bump this up from 5
    name = models.CharField(_("component type name"), max_length=255)
    nistir_subelement = models.ForeignKey("NistirSubElement", on_delete=models.PROTECT, verbose_name="NISTIR Sub Element")

    class Meta:
        verbose_name = "Component"
        verbose_name_plural = "Components"

    def __str__(self):
        return self.id

class NistirMajorGroupElement(models.Model):

    id = models.CharField(primary_key=True, max_length=255, verbose_name="ID")
    name = models.CharField(_("name"), max_length=1024)

    class Meta:
        verbose_name = "NISTIR Major Group Element"
        verbose_name_plural = "NISTIR Major Group Elements"
    
    def __str__(self):
        return self.name
    
class NistirGroupElement(models.Model):

    id = models.CharField(primary_key=True, max_length=255, verbose_name="ID")
    name = models.CharField(_("name"), max_length=1024)
    # NOTE: "blank = True" is required for the serializer.is_valid() method to NOT throw a data validation exception.  Note this does not suggest
    # the field in the database will be configured as nullable - unless otherwise specified, the foreign-key remains non nullable when migrations are performed
    major_group_element = models.ForeignKey(NistirMajorGroupElement, on_delete = models.CASCADE, verbose_name="NISTIR Major Group", related_name = "group_elements", blank = True)

    class Meta:
        verbose_name = "NISTIR Group Element"
        verbose_name_plural = "NISTIR Group Elements"
    
    def __str__(self):
        return self.name
    
class NistirIndivElement(models.Model):

    id = models.CharField(primary_key=True, max_length=255, verbose_name="ID")
    name = models.CharField(_("name"), max_length=1024)
    # NOTE: "blank = True" is required for the serializer.is_valid() method to NOT throw a data validation exception.  Note this does not suggest
    # the field in the database will be configured as nullable - unless otherwise specified, the foreign-key remains non nullable when migrations are performed
    group_element = models.ForeignKey(NistirGroupElement, on_delete = models.CASCADE, verbose_name="NISTIR Group", related_name="indiv_elements", blank = True)

    class Meta:
        verbose_name = "NISTIR Individual Element"
        verbose_name_plural = "NISTIR Individual Elements"
    
    def __str__(self):
        return self.name
    
class NistirSubElement(models.Model):

    id = models.CharField(primary_key=True, max_length=255, verbose_name="ID")
    name = models.CharField(_("name"), max_length=1024)
    # NOTE: "blank = True" is required for the serializer.is_valid() method to NOT throw a data validation exception.  Note this does not suggest
    # the field in the database will be configured as nullable - unless otherwise specified, the foreign-key remains non nullable when migrations are performed
    indiv_element = models.ForeignKey(NistirIndivElement, on_delete = models.CASCADE, verbose_name="NISTIR Indiv. Element", related_name="sub_elements", blank = True)

    class Meta:
        verbose_name = "NISTIR Sub Element"
        verbose_name_plural = "NISTIR Sub Elements"
    
    def __str__(self):
        return self.name