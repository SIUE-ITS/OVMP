from django.forms import ModelForm
from . import models


class MemberForm(ModelForm):

    class Meta:
        model = models.Member
        fields = ['project', 'user', 'is_owner', 'max_resources']

    def __init__(self, request, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project'].queryset = models.Project.objects.filter(pk=project)
