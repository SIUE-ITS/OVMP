from django.db import models
from projects.models import Project


# Create your models here.
class Image(models.Model):
    uuid = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    size = models.IntegerField(default=0)
    projects = models.ManyToManyField(
        Project,
        related_name='images',
        blank=True
    )

    def __str__(self):
        return self.name


class Flavor(models.Model):
    uuid = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    projects = models.ManyToManyField(
        Project,
        related_name='flavors',
        blank=True
    )

    def __str__(self):
        return self.name
