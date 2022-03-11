from django.forms import ModelForm
from . import models


class ImageForm(ModelForm):

    class Meta:
        model = models.Image
        fields = ['projects']

    def __init__(self, projects, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['projects'].queryset = projects
