from rest_framework import serializers
from ned_app.models import Reference, Component, FragilityModel, Experiment, ExperimentFragilityModelBridge, FragilityCurve, NistirMajorGroupElement, NistirGroupElement, NistirIndivElement, NistirSubElement

class ReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = '__all__'
        # exclude = ('field_abc',)  # useful if there are any exclusions to consider

    # create the Reference record in the database via the framework
    def create(self, json_data) -> Reference:
        # 'json_data' is simply seen as a kwargs input...
        reference: Reference = Reference.objects.create(**json_data)

        return reference
    
class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = '__all__'

    # create the Component record in the database via the framework
    def create(self, json_data) -> Component:
        # 'json_data' is simply seen as a kwargs input...
        component: Component = Component.objects.create(**json_data)

        return component
    
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
        bridge: ExperimentFragilityModelBridge = ExperimentFragilityModelBridge.objects.create(**json_data)

        return bridge
    
class FragilityCurveSerializer(serializers.ModelSerializer):
    class Meta:
        model = FragilityCurve
        fields = '__all__'

    def create(self, json_data) -> FragilityCurve:
        # 'json_data' is simply seen as a kwargs input...
        curve: FragilityCurve = FragilityCurve.objects.create(**json_data)

        return curve
    
class NistirSubElementSerializer(serializers.ModelSerializer):
        
    class Meta:
        model = NistirSubElement
        # fields = '__all__'
        fields = ['id', 'name']

    def create(self, validated_data) -> NistirIndivElement:
        # 'validated_data' is simply seen as a kwargs input...
        sub_element: NistirSubElement = NistirSubElement.objects.create(**validated_data)

        return sub_element 

class NistirIndivElementSerializer(serializers.ModelSerializer):
    
    sub_elements = NistirSubElementSerializer(many = True, read_only = False, required = False) # NOTE: not requiring that all sub-elements be present in the JSON data
    
    class Meta:
        model = NistirIndivElement
        # fields = '__all__'
        fields = ['id', 'name', 'sub_elements']

    def create(self, validated_data) -> NistirIndivElement:
        # 'validated_data' is simply seen as a kwargs input...
        indiv_element: NistirIndivElement = NistirIndivElement.objects.create(**validated_data)

        return indiv_element 

class NistirGroupElementSerializer(serializers.ModelSerializer):
    # adding as its of field ensures the serializer picks up and deserializes the indiv_elements content
    indiv_elements = NistirIndivElementSerializer(many = True, read_only = False)
    
    class Meta:
        model = NistirGroupElement
        # fields = '__all__'
        fields = ['id', 'name', 'indiv_elements']

    def create(self, validated_data) -> NistirGroupElement:

        # 'validated_data' is simply seen as a kwargs input...
        group_element: NistirGroupElement = NistirGroupElement.objects.create(**validated_data)

        return group_element  

class NistirMajorGroupElementSerializer(serializers.ModelSerializer):

    group_elements = NistirGroupElementSerializer(many = True, read_only = False)
    
    class Meta:
        model = NistirMajorGroupElement
        fields = '__all__' # includes the declared "group_elements" field above
        fields = ['id', 'name', 'group_elements']

    # create the NISTIR record in the database via the framework
    def create(self, validated_data) -> NistirMajorGroupElement:
        group_elements_data = validated_data.pop('group_elements')
        major_group_element: NistirMajorGroupElement = NistirMajorGroupElement.objects.create(**validated_data)
        
        for group_element_data in group_elements_data:
            indiv_elements_data = group_element_data.pop('indiv_elements')
            group_element: NistirGroupElement = NistirGroupElement.objects.create(major_group_element=major_group_element, **group_element_data)
            
            for indiv_element_data in indiv_elements_data:
                if 'sub_elements' in indiv_element_data:
                    sub_elements_data = indiv_element_data.pop('sub_elements')
                    indiv_element: NistirIndivElement = NistirIndivElement.objects.create(group_element = group_element, **indiv_element_data)

                    for sub_element_data in sub_elements_data:
                        sub_element: NistirSubElement = NistirSubElement.objects.create(indiv_element = indiv_element, **sub_element_data)
                else:
                    indiv_element: NistirIndivElement = NistirIndivElement.objects.create(group_element = group_element, **indiv_element_data)
        
        return major_group_element