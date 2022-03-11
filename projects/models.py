from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


alphanumeric = RegexValidator(r'^[0-9a-zA-Z-_]*$', 'Only alphanumeric characters are allowed.')


class Role(models.Model):
    CREATOR = 'CR'
    ROLES = [
        (CREATOR, 'Creator'),
    ]
    name = models.CharField(max_length=255, choices=ROLES)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    max_projects = models.PositiveIntegerField(default=1, null=True, help_text="Only applicable for creator role.")

    class Meta:
        unique_together = ['user', 'name']

    def __str__(self):
        return "{} {}".format(self.get_name_display(), self.user)


class Project(models.Model):
    name = models.CharField(max_length=255, unique=True, validators=[alphanumeric])
    uuid = models.CharField(max_length=255)
    max_resources = models.PositiveIntegerField(default=100)

    def __str__(self):
        return self.name


class Member(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    is_creator = models.BooleanField(default=False)
    is_owner = models.BooleanField(default=False)
    max_resources = models.PositiveIntegerField(default=6)

    class Meta:
        unique_together = ['user', 'project']

    def __str__(self):
        return "{} {} is_owner {}".format(self.user, self.project,
                                          self.is_owner)
