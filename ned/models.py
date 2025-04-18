from django.db import models
from django.utils.translation import gettext as _

# Create your models here.
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
    reference = models.ForeignKey(
        "Reference",
        on_delete=models.PROTECT,
        )
    specimen = models.CharField(_("specimen"), max_length=255, blank=True)
    specimen_inspection_sequence = models.CharField(_("specimen inspection sequence"), max_length=255, blank=True)
    reviewer = models.CharField(_("reviewer"), max_length=50)
    nistir = models.ForeignKey(
        "Nistir",
        on_delete=models.PROTECT,
        )
    p58_fragility = models.CharField(_("FEMA P-58 fragility id"), max_length=50, blank=True)
    # fragility_id = models.CharField(_("Fragility Identifier Foriegn Key"), max_length=50, blank=True)
    # fragility_group = models.ManyToManyField(
    #     "Fragility_group",
    #     )
    comp_type = models.CharField(_("component type"), max_length=255)
    sub_type = models.CharField(_("component sub-type"), max_length=255, blank=True)
    detailing = models.CharField(_("connection detail"), max_length=255, blank=True)
    material = models.CharField(_("material classification"), max_length=255, blank=True)
    size_class = models.CharField(_("size classification"), max_length=255, blank=True)
    test_type = models.CharField(_("test type"),
        max_length=50,
        choices=testtypeChoices.choices,
        )
    loading_protocol = models.CharField(_("loading protocol"), max_length=255, blank=True)
    peak_test_amplitude = models.CharField(_("peak test amplitute"), max_length=255, blank=True)
    location = models.CharField(_("location"), max_length=255, blank=True)
    governing_design_standard = models.CharField(_("governing design standard"), max_length=255, blank=True)
    design_objective = models.CharField(_("design objective"), max_length=255, blank=True)
    comp_description = models.TextField(_("component description"))
    ds_description = models.TextField(_("damage state description"))
    prior_damage = models.CharField(_("prior damage"), max_length=255, blank=True)
    prior_damage_repaired = models.BooleanField(_("is prior damage repaired"), null=True)
    edp_metric = models.CharField(_("edp metric"),
        max_length=50,
        choices=edpmetricChoices.choices,
        )
    edp_unit = models.CharField(_("edp unit"),
        max_length=50,
        choices=edpunitChoices.choices,
        )
    edp_value = models.DecimalField(_("edp value"), max_digits=12, decimal_places=6)
    alt_edp_metric = models.CharField(_("alternative edp metric"),
        max_length=50,
        choices=edpmetricChoices.choices,
        )
    alt_edp_unit = models.CharField(_("alternative edp unit"),
        max_length=50,
        choices=edpunitChoices.choices,
        )
    alt_edp_value = models.DecimalField(_("alternative edp value"), max_digits=12, decimal_places=6, null=True)
    ds_rank = models.IntegerField(_("damage state rank"), null=True)
    ds_class = models.CharField(_("damage state class"),
        max_length=50,
        choices=dsclassChoices.choices,
        default=dsclassChoices.UNKNOWN,
        )
    notes = models.TextField(_("notes"), blank=True)

    def __str__(self):
        return self.name

class Fragility(models.Model):

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

    id = models.CharField(_("id"), primary_key=True, max_length=255)
    fragility_group = models.ForeignKey(
        "Fragility_group",
        on_delete=models.PROTECT,
        )
    reviewer = models.CharField(_("reviewer"), max_length=255)
    source = models.CharField(_("source"), max_length=255)
    basis = models.CharField(_("basis"), 
        choices=basisChoices.choices,
        max_length=50, 
        blank=True,
        )
    num_observations = models.IntegerField(_("number of observations"), null=True, blank=True)
    reference = models.ForeignKey(
        "Reference",
        on_delete=models.PROTECT,
        )
    p58_fragility = models.CharField(_("FEMA P-58 fragility id"), max_length=50, blank=True)
    nistir = models.ForeignKey(
        "Nistir",
        on_delete=models.PROTECT,
        )
    comp_type = models.CharField(_("component type"), max_length=255)
    sub_type = models.CharField(_("component sub-type"), max_length=255, blank=True)
    detailing = models.CharField(_("connection detail"), max_length=255, blank=True)
    material = models.CharField(_("material classification"), max_length=255, blank=True)
    size_class = models.CharField(_("size classification"), max_length=255, blank=True)
    comp_description = models.TextField(_("component description"))
    edp_metric = models.CharField(_("edp metric"), 
        choices=edpmetricChoices.choices,
        max_length=255,
        )
    edp_unit = models.CharField(_("edp unit"), 
        choices=edpunitChoices.choices,
        max_length=255,
        )
    ds_rank = models.IntegerField(_("damage state rank"))
    ds_description = models.TextField(_("damage state description"))
    median = models.DecimalField(_("median"), max_digits=9, decimal_places=3, null=True)
    beta = models.DecimalField(_("beta"), max_digits=3, decimal_places=2, null=True)
    probability = models.DecimalField(_("probability"), max_digits=3, decimal_places=2, null=True)

    def __str__(self):
        return self.name

class Fragility_group(models.Model):

    id = models.CharField(_("id"), primary_key=True, max_length=255)
    
    def __str__(self):
        return self.name
    
class Experiment_fragility_group(models.Model):

    id = models.CharField(_("id"), primary_key=True, max_length=255)
    experiment = models.ForeignKey(
        "Experiment",
        on_delete=models.PROTECT,
        )
    fragility_group = models.ForeignKey(
        "Fragility_group",
        on_delete=models.PROTECT,
        )
    
    def __str__(self):
        return self.name
    
class Nistir(models.Model):

    class majorgroupChoices(models.TextChoices):
        A = 'Substructure'
        B = 'Shell'
        C = 'Interiors'
        D = 'Services'
        E = 'Equipment & Furnishings'
        F = 'Special Construction & Demolition'

    id = models.CharField(_("id"), primary_key=True,max_length=5)
    sub_element = models.CharField(_("sub-element name"), max_length=255)
    element_id = models.CharField(_("element id"), max_length=5)
    element = models.CharField(_("element name"), max_length=255)
    group_id = models.CharField(_("group id"), max_length=3)
    group = models.CharField(_("group name"), max_length=50)
    major_group_id = models.CharField(_("major group id"), max_length=1)
    major_group = models.CharField(_("major group name"),
        max_length=50,
        choices=majorgroupChoices.choices,
        )

    def __str__(self):
        return self.id

class Reference(models.Model):

    class studytypeChoices(models.TextChoices):
        EXPERIMENT = 'Experiment'
        RECON = 'Historical Event'
        ANALYTICAL = 'Analytical Study'
        LIT_REVIEW = 'Lit Review'
        OTHER = 'Other'

    id = models.CharField(_("id"), primary_key=True, max_length=255)
    name = models.CharField(_("name"), max_length=255)
    author = models.CharField(_("author"), max_length=255)
    year = models.IntegerField(_("year"))
    study_type = models.CharField(_("study type"),
        max_length=50,
        choices=studytypeChoices.choices,
        default=studytypeChoices.OTHER,
        )
    comp_type = models.CharField(_("component type"), max_length=255, blank=True)
    doi = models.URLField(_("doi"), max_length=200, null=True)
    citation = models.CharField(_("citation"), max_length=255, blank=True)
    publication_type = models.CharField(_("publication type"), max_length=50, blank=True)
    pdf_saved = models.BooleanField(_("pdf saved"), default=False)

    def __str__(self):
        return self.name