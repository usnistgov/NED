from django.db import models
from django.utils.translation import gettext as _

# Create your models here.
class Reference(models.Model):
    """
    A model representing a reference to a research publication.

    Attributes:
        title (str): The title of paper or manuscript (auto-populated from csl_data).
        author (str): The name(s) of the author(s) (auto-populated from csl_data).
        year (int): The year the study was published (auto-populated from csl_data).
        study_type (str): A classification of the type of study conducted.
        comp_type (str): The type of component(s) invenstigated in study.
        pdf_saved (bool): Is a pdf saved in the archive repository.
        csl_data (dict): Reference data in CSL-JSON format.
    """

    class studytypeChoices(models.TextChoices):
        EXPERIMENT = 'Experiment'
        RECON = 'Historical Event'
        ANALYTICAL = 'Analytical Study'
        LIT_REVIEW = 'Lit Review'
        OTHER = 'Other'

    id = models.CharField(_("id"), primary_key=True, max_length=255)
    title = models.CharField(_("title"), default='', max_length=255, blank = False, editable=False, help_text="The title of paper or manuscript.")
    author = models.CharField(_("author"), max_length=255, blank = False, editable=False, help_text="The name(s) of the author(s).")
    year = models.IntegerField(_("year"), blank = False, null = False, editable=False, help_text="The year the study was published.")
    study_type = models.CharField(_("study type"), max_length=50, choices=studytypeChoices.choices, default=studytypeChoices.OTHER, help_text="A classification of the type of study conducted.")
    comp_type = models.CharField(_("component type"), max_length=255, blank = True, help_text="The type of component(s) invenstigated in study.")
    pdf_saved = models.BooleanField(_("pdf saved"), default=False, help_text="Is a pdf saved in the archive repository.")
    csl_data = models.JSONField(_("csl data"), null=True, blank=True, help_text="Reference data in CSL-JSON format.")

    class Meta:
        verbose_name = "Reference"
        verbose_name_plural = "References"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Override save to automatically populate fields from csl_data."""
        if self.csl_data:
            # Populate title field from csl_data title
            if 'title' in self.csl_data:
                self.title = self.csl_data['title']

            # Populate year field from csl_data issued date-parts
            if 'issued' in self.csl_data and 'date-parts' in self.csl_data['issued']:
                date_parts = self.csl_data['issued']['date-parts']
                if date_parts and len(date_parts) > 0 and len(date_parts[0]) > 0:
                    self.year = date_parts[0][0]

            # Populate author field with formatted string from csl_data authors
            if 'author' in self.csl_data:
                authors = self.csl_data['author']
                if authors:
                    family_names = []
                    for author in authors:
                        if 'family' in author:
                            family_names.append(author['family'])
                        elif 'literal' in author:
                            # For literal names, try to extract family name (last word)
                            literal_parts = author['literal'].split()
                            if literal_parts:
                                family_names.append(literal_parts[-1])

                    if family_names:
                        if len(family_names) == 1:
                            self.author = family_names[0]
                        elif len(family_names) == 2:
                            self.author = f"{family_names[0]} and {family_names[1]}"
                        else:  # 3 or more authors
                            self.author = f"{family_names[0]} et al."

        super().save(*args, **kwargs)

class Experiment(models.Model):
    """
    A model representing a person.

    Attributes:
        reference (id): ID of the published reference documenting this experimental observation.
        specimen (str): ID or name of the specimen as recorded in the reference.
        specimen_inspection_sequence (str): The ith test of this specimen.
        reviewer (str): Individual or institution repsonsible for documenting this particular fragility in the database.
        component (id): Identifier of the component type.
        comp_detail (str): Classification or short description of the component attachement detailing.
        material (str): Classification or short description of the component material (if applicable).
        size_class (str): Classification or short description of the general size of this paticular components compared to others of the same type (if applicable).
        test_type (str): The type of test generally describing the condition under which the specimen was loaded.
        loading_protocol (str): Name, ID, or general description of the ground motion or loading protocol used in the test.
        peak_test_amplitude (str): The maximum amplitude to which this test was performed.
        location (str): The location where the specimen was conducted.
        governing_design_standard (str): Name of the standard governing the design of the specimen, if applicable.
        design_objective (str): General description of the performance level to which the specimen was designed, e.g., code compliant, common construciton practice, low-damage-design, or meeting a certain damage objective under a specific loading condition.
        comp_description (str): Genearl description of the type of component.
        ds_description (str): Description of the damage being observed.
        prior_damage (str): Description of any prior damage that was noted during a previous test of this specimen. Should also describe if and how the specimen was repaired prior to this test. Empty if no prior damage was noted.
        prior_damage_repaired (str): TRUE if prior damage was noted and repaired prior to this test. FALSE if prior damage was noted and not repiared. Or, a general description of the previous damage that was repaired.
        edp_metric (str): Measure of the engineering demand parameter (EDP), e.g, peak story drift ratio.
        edp_unit (str): Unit of the engineering demand parameter.
        edp_value (float): Value of the engineering demand parameter recorded for this observation.
        alt_edp_metric (str): Secondary EDP metric.
        alt_edp_unit (str): Secondary EDP unit.
        alt_edp_value (float): Secondary EDP value. 
        ds_rank (int): Integer rank ordering this observed damage with other damage observed in the same specimen.
        ds_class (str): General identification of damage as consequential or not.
        notes (str): Additional notes providing context for damage observations.
    """

    class testtypeChoices(models.TextChoices):
        DYNA_1D = 'Dynamic, uniaxial'
        DYNA_2D = 'Dynamic, bi-directional'
        DYNA_2D_vert = 'Dynamic, horizontal and vertical'
        DYNA_3D = 'Dynamic, 3D'
        MONO_C = 'Monotonic, compression'
        MONO_T = 'Monotonic, tension'
        MONO_M = 'Monotonic, bending'
        MONO_L = 'Monotonic, lateral'
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
    reference = models.ForeignKey("Reference", on_delete=models.PROTECT, help_text="ID of the published reference documenting this experimental observation.")
    specimen = models.CharField(_("specimen"), max_length=255, blank = True, help_text="ID or name of the specimen as recorded in the reference.")
    specimen_inspection_sequence = models.CharField(_("specimen inspection sequence"), max_length=255, blank = True, help_text="The ith test of this specimen.")
    reviewer = models.CharField(_("reviewer"), max_length=50, blank = True, help_text="Individual or institution repsonsible for documenting this particular fragility in the database.")
    component = models.ForeignKey("Component", on_delete=models.PROTECT, help_text="Identifier of the component type")
    comp_detail = models.CharField(_("component detail tag"), max_length=100, blank = True, help_text="Classification or short description of the component attachement detailing.")
    material = models.CharField(_("material classification tag"), max_length=100, blank = True, help_text="Classification or short description of the component material (if applicable).")
    size_class = models.CharField(_("size classification tag"), max_length=100, blank = True, help_text="Classification or short description of the general size of this paticular components compared to others of the same type (if applicable).")
    test_type = models.CharField(_("test type"), max_length=50, choices=testtypeChoices.choices, help_text="The type of test generally describing the condition under which the specimen was loaded.")
    loading_protocol = models.TextField(_("loading protocol"), blank = True, help_text="Name, ID, or general description of the ground motion or loading protocol used in the test.")
    peak_test_amplitude = models.CharField(_("peak test amplitute"), max_length=255, blank = True, help_text="The maximum amplitude to which this test was performed.")
    location = models.CharField(_("location"), max_length=255, blank = True, help_text="The location where the specimen was conducted.")
    governing_design_standard = models.CharField(_("governing design standard"), max_length=255, blank = True, help_text="Name of the standard governing the design of the specimen, if applicable.")
    design_objective = models.TextField(_("design objective"), blank = True, help_text="General description of the performance level to which the specimen was designed, e.g., code compliant, common construciton practice, low-damage-design, or meeting a certain damage objective under a specific loading condition.")
    comp_description = models.TextField(_("component description"), blank = False, help_text="Genearl description of the type of component.")
    ds_description = models.TextField(_("damage state description"), blank = False, help_text="Description of the damage being observed.")
    prior_damage = models.TextField(_("prior damage"), blank = True, help_text="Description of any prior damage that was noted during a previous test of this specimen. Should also describe if and how the specimen was repaired prior to this test. Empty if no prior damage was noted.")
    prior_damage_repaired = models.TextField(_("is prior damage repaired"), max_length=255, blank = True, help_text="TRUE if prior damage was noted and repaired prior to this test. FALSE if prior damage was noted and not repiared. Or, a general description of the previous damage that was repaired.")
    edp_metric = models.CharField(_("edp metric"), max_length=50, choices=edpmetricChoices.choices, blank = False, help_text="Measure of the engineering demand parameter (EDP), e.g, peak story drift ratio.")
    edp_unit = models.CharField(_("edp unit"), max_length=50, choices=edpunitChoices.choices, blank = False, help_text="Unit of the engineering demand parameter.")
    edp_value = models.DecimalField(_("edp value"), max_digits=12, decimal_places=6, blank = False, null = True, help_text="Value of the engineering demand parameter recorded for this observation.")
    alt_edp_metric = models.CharField(_("alternative edp metric"), max_length=50, choices=edpmetricChoices.choices, blank = True, help_text="Secondary EDP metric.")
    alt_edp_unit = models.CharField(_("alternative edp unit"), max_length=50, choices=edpunitChoices.choices, blank = True, help_text="Secondary EDP unit.")
    alt_edp_value = models.DecimalField(_("alternative edp value"), max_digits=12, decimal_places=6, blank = True, null = True, help_text="Secondary EDP value. ")
    ds_rank = models.IntegerField(_("damage state rank"), blank = True, null = True, help_text="Integer rank ordering this observed damage with other damage observed in the same specimen.")
    ds_class = models.CharField(_("damage state class"), max_length=50, choices=dsclassChoices.choices, blank = False, help_text="General identification of damage as consequential or not.")
    notes = models.TextField(_("notes"), blank=True, help_text="Additional notes providing context for damage observations.")

    class Meta:
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"

    def __str__(self):
        return self.id

class FragilityModel(models.Model):
    """
    A model representing a person.

    Attributes:
        p58_fragility (str): P-58 fragility id associated with this fragility model, if applicable.
        component (id): Identifier of the component type.
        comp_detail (str): Classification or short description of the component attachement detailing.
        material (str): Classification or short description of the component material (if applicable).
        size_class (str): Classification or short description of the general size of this paticular components compared to others of the same type (if applicable).
        comp_description (str): Genearl description of the type of component.
    """

    id = models.CharField(_("id"), primary_key=True, max_length=255)
    p58_fragility = models.CharField(_("FEMA P-58 fragility id"), max_length=50, blank=True, help_text="P-58 fragility id associated with this fragility model, if applicable.")
    component = models.ForeignKey("Component", on_delete=models.PROTECT, help_text="Identifier of the component type.")
    comp_detail = models.CharField(_("component detail tag"), max_length=100, blank = True, help_text="Classification or short description of the component attachement detailing.")
    material = models.CharField(_("material classification tag"), max_length=100, blank=True, help_text="Classification or short description of the component material (if applicable).")
    size_class = models.CharField(_("size classification tag"), max_length=100, blank=True, help_text="Classification or short description of the general size of this paticular components compared to others of the same type (if applicable).")
    comp_description = models.TextField(_("component description"), blank=False, help_text="Genearl description of the type of component.")

    class Meta:
        verbose_name = "Fragility Model"
        verbose_name_plural = "Fragility Models"

    def __str__(self):
        return self.id

class ExperimentFragilityModelBridge(models.Model):
    """
    A bridge model facilitating a many-to-many relationship between experiments and fragility models.

    Attributes:
        experiment (str): Experiment model ID.
        fragility_model (str): fragility model ID.
    """

    experiment = models.ForeignKey("Experiment", on_delete=models.PROTECT, help_text="Experiment model ID")
    fragility_model = models.ForeignKey("FragilityModel", on_delete=models.PROTECT, help_text="fragility model ID")

    class Meta:
        verbose_name = "Experiment - Fragility Pair"
        verbose_name_plural = "Experiment - Fragility Pairs"

    def __str__(self):
        return f"{self.experiment}_{self.fragility_model}"

class FragilityCurve(models.Model):
    """
    A model representing an individual fragility curve, as a lognormal distribution, for a particular damage state of interest

    Attributes:
        fragility_model (id): Id of the fragility model this fragility belongs to.
        reviewer (str): Person or party resposible for uploading this fragility curve to the database.
        source (str): Source of the fragility data.
        basis (str): Observational basis of the underying data comprising the fragility curve. 
        num_observations (int): Number of observations that form the basis of the fragility curve.
        reference (id): ID of the published reference documenting this fragility.
        edp_metric (str): Measure of the engineering demand parameter (EDP), e.g, peak story drift ratio.
        edp_unit (str): Unit of the engineering demand parameter.
        ds_rank (int): Integer rank ordering this fragility curve with other curves in the fragility model.
        ds_description (str): Description of the damage being modeled.
        median (float): Median point of the fragility curve.
        beta (float): Lognormal dispersion.
        probability (float): Mutually exclusive probability of this damage state. 
    """

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

    fragility_model = models.ForeignKey("FragilityModel", on_delete=models.PROTECT, help_text="Id of the fragility model this fragility belongs to.")
    reviewer = models.CharField(_("reviewer"), max_length=255, blank=True, help_text="Person or party resposible for uploading this fragility curve to the database.")
    source = models.CharField(_("source"), max_length=255, blank=True, help_text="Source of the fragility data.")
    basis = models.CharField(_("basis"), choices=basisChoices.choices, max_length=50, blank=True, help_text="Observational basis of the underying data comprising the fragility curve.")
    num_observations = models.IntegerField(_("number of observations"), null=True, blank=True, help_text="Number of observations that form the basis of the fragility curve.")
    reference = models.ForeignKey("Reference", on_delete=models.PROTECT, help_text="ID of the published reference documenting.")
    edp_metric = models.CharField(_("edp metric"), choices=edpmetricChoices.choices, max_length=255, blank=False, help_text="Measure of the engineering demand parameter (EDP), e.g, peak story drift ratio.")
    edp_unit = models.CharField(_("edp unit"), choices=edpunitChoices.choices, max_length=255, blank=False, help_text="Unit of the engineering demand parameter.")
    ds_rank = models.IntegerField(_("damage state rank"), null=True, blank=True, help_text="Integer rank ordering this fragility curve with other curves in the fragility model.")
    ds_description = models.TextField(_("damage state description"), blank=False, help_text="Description of the damage being modeled.")
    median = models.DecimalField(_("median"), max_digits=9, decimal_places=4, null=True, blank=False, help_text="Median point of the fragility curve.")
    beta = models.DecimalField(_("beta"), max_digits=4, decimal_places=3, null=True, blank=False, help_text="Lognormal dispersion.")
    probability = models.DecimalField(_("probability"), max_digits=3, decimal_places=2, null=True, blank=False, help_text="Mutually exclusive probability of this damage state.")

    class Meta:
        verbose_name = "Fragility Curve"
        verbose_name_plural = "Fragility Curves"

    def __str__(self):
        return self.name

class Component(models.Model):
    """
    A model representing an individual type of building component with specific attachment or material details.

    Attributes:
        name (str): Name of the individual type of building component.
        nistir_subelement (id): NISTIR taxonomy subelement classification
    """

    id = models.CharField(_("id"), primary_key=True,max_length=10) # NOTE: had to bump this up from 5
    name = models.CharField(_("component type name"), max_length=255, blank=False, help_text="Name of the individual type of building component.")
    nistir_subelement = models.ForeignKey("NistirSubElement", on_delete=models.PROTECT, verbose_name="NISTIR Sub Element", help_text="NISTIR taxonomy subelement classification")

    class Meta:
        verbose_name = "Component"
        verbose_name_plural = "Components"

    def __str__(self):
        return self.id

class NistirMajorGroupElement(models.Model):
    """
    A model representing major division in building component types

    Attributes:
        name (str): Broad category of buildng's component categorization.
    """

    id = models.CharField(primary_key=True, max_length=255, verbose_name="ID")
    name = models.CharField(_("name"), max_length=1024, blank=False, help_text="Broad category of buildng's component categorization.")

    class Meta:
        verbose_name = "NISTIR Major Group Element"
        verbose_name_plural = "NISTIR Major Group Elements"

    def __str__(self):
        return self.name

class NistirGroupElement(models.Model):
    """
    A model representing an Sub-group classification in the NISTIR building component taxonomy.

    Attributes:
        name (str): Sub-group classification of the major grouping.
        major_group_element (id): 1-digit alphabetical indentifier of the major group.
    """

    id = models.CharField(primary_key=True, max_length=255, verbose_name="ID")
    name = models.CharField(_("name"), max_length=1024, blank=False, help_text="Sub-group classification of the major grouping.")
    # NOTE: "blank = True" is required for the serializer.is_valid() method to NOT throw a data validation exception.  Note this does not suggest
    # the field in the database will be configured as nullable - unless otherwise specified, the foreign-key remains non nullable when migrations are performed
    major_group_element = models.ForeignKey(NistirMajorGroupElement, on_delete = models.CASCADE, verbose_name="NISTIR Major Group", related_name = "group_elements", blank = True, help_text="1-digit alphabetical indentifier of the major group.")

    class Meta:
        verbose_name = "NISTIR Group Element"
        verbose_name_plural = "NISTIR Group Elements"

    def __str__(self):
        return self.name

class NistirIndivElement(models.Model):
    """
    A model representing an building element in the NISTIR building component taxonomy.

    Attributes:
        name (str): Classification of the specific element of interest within the group.
        group_element (id): 3-digit alphanumeric indentifier of the group.
    """

    id = models.CharField(primary_key=True, max_length=255, verbose_name="ID")
    name = models.CharField(_("name"), max_length=1024, blank=False, help_text="Classification of the specific element of interest within the group.")
    # NOTE: "blank = True" is required for the serializer.is_valid() method to NOT throw a data validation exception.  Note this does not suggest
    # the field in the database will be configured as nullable - unless otherwise specified, the foreign-key remains non nullable when migrations are performed
    group_element = models.ForeignKey(NistirGroupElement, on_delete = models.CASCADE, verbose_name="NISTIR Group", related_name="indiv_elements", blank = True, help_text="3-digit alphanumeric indentifier of the group.")

    class Meta:
        verbose_name = "NISTIR Individual Element"
        verbose_name_plural = "NISTIR Individual Elements"

    def __str__(self):
        return self.name

class NistirSubElement(models.Model):
    """
    A model representing a subcategorization of an element in the NISTIR building component taxonomy.

    Attributes:
        name (str): Sub-element classification of a specific type of element within a given element class.
        indiv_element (id): 5-digit alphanumeric indentifier of the NISTIR element.
    """

    id = models.CharField(primary_key=True, max_length=255, verbose_name="ID")
    name = models.CharField(_("name"), max_length=1024, blank=False, help_text="Sub-element classification of a specific type of element within a given element class.")
    # NOTE: "blank = True" is required for the serializer.is_valid() method to NOT throw a data validation exception.  Note this does not suggest
    # the field in the database will be configured as nullable - unless otherwise specified, the foreign-key remains non nullable when migrations are performed
    indiv_element = models.ForeignKey(NistirIndivElement, on_delete = models.CASCADE, verbose_name="NISTIR Indiv. Element", related_name="sub_elements", blank = True, help_text="5-digit alphanumeric indentifier of the NISTIR element.")

    class Meta:
        verbose_name = "NISTIR Sub Element"
        verbose_name_plural = "NISTIR Sub Elements"

    def __str__(self):
        return self.name
