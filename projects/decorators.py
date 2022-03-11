from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from . import models


def is_staff(function):
        def wrap(request, *args, **kwargs):
            if not request.user.is_staff:
                messages.add_message(request, messages.ERROR,
                                     'Permission denied you must be staff.')
                raise PermissionDenied
            return function(request, *args, **kwargs)
        return wrap


def max_projects(function):
    def wrap(request, *args, **kwargs):
        try:
            role = request.user.role_set.get(name='CR')
            num = len(request.user.member_set.filter(is_creator=True))
            if role.max_projects <= len(request.user.member_set.filter(is_creator=True)):
                messages.add_message(request, messages.ERROR,
                                     'Max projects reached {} of {}.'.format(num, role.max_projects))
                return HttpResponseRedirect(reverse_lazy('projects:list'))
        except ObjectDoesNotExist:
            messages.add_message(request, messages.ERROR,
                                 'Permission denied you must have role creator.')
            raise PermissionDenied
        return function(request, *args, **kwargs)
    return wrap


def role_required(role):
    def wrapper(function):
        def wrap(request, *args, **kwargs):
            try:
                models.Role.objects.get(user=request.user, name=role)
            except ObjectDoesNotExist:
                for m_role in models.Role.ROLES:
                    if m_role[0] == role:
                        p_role = m_role[1]
                messages.add_message(request, messages.ERROR,
                                     'Permission denied you must have role {}.'.format(p_role))
                raise PermissionDenied
            return function(request, *args, **kwargs)
        return wrap
    return wrapper


def is_owner(function):
    def wrap(request, *args, **kwargs):
        if 'project' in kwargs:
            project = models.Project.objects.get(pk=kwargs['project'])
        elif 'member' in kwargs:
            project = models.Member.objects.get(pk=kwargs['member']).project
        else:
            if not request.user.member_set.filter(is_owner=True) \
                    and not models.Role.objects.filter(user=request.user, name='CR'):
                messages.add_message(request, messages.ERROR,
                                     'Permission denied you must be an owner of '
                                     'a project or an admin.')
                raise PermissionDenied
            else:
                return function(request, *args, **kwargs)
        try:
            member = models.Member.objects.get(
                user=request.user,
                project=project,
                is_owner=True,
            )
        except ObjectDoesNotExist:
            messages.add_message(request, messages.ERROR,
                                 'Permission denied you must be an owner of '
                                 'the project.')
            raise PermissionDenied
        return function(request, *args, **kwargs)
    return wrap
