from django import template
from projects import models

register = template.Library()


@register.simple_tag
def has_owner_projects(user):
    if user.is_anonymous:
        return False
    elif user.member_set.filter(is_owner=True):
        return True
    else:
        return False

@register.simple_tag
def has_creator(user, role):
    if user.is_anonymous:
        return False
    elif models.Role.objects.filter(user=user, name=role):
        return True
    else:
        return False
