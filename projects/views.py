from django.shortcuts import render
from . import models
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic import DetailView
from django.views.generic.list import ListView
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from . import decorators
from actions import api
from . import forms
from django.contrib import messages
from django.db.models import Sum
import keystoneauth1.exceptions as ke


@method_decorator(decorators.role_required('CR'), name="dispatch")
class UserList(ListView):
    model = User
    template_name = 'user_list.html'


@method_decorator(decorators.role_required('CR'), name="dispatch")
class UserCreate(CreateView):
    model = User
    template_name = 'user_form.html'
    success_url = reverse_lazy('projects:user_list')
    fields = ['username']


@method_decorator(decorators.is_staff, name="dispatch")
class UserDelete(DeleteView):
    model = User
    pk_url_kwarg = 'user'
    template_name = 'user_confirm_delete.html'
    success_url = reverse_lazy('projects:user_list')


@method_decorator(decorators.is_owner, name="dispatch")
class ProjectList(ListView):
    model = models.Project
    template_name = 'project_list.html'

    def get_queryset(self):
        projects = models.Project.objects.filter(id__in=self.request.user.member_set.filter(is_owner=True).values_list('project'))
        return projects


@method_decorator(decorators.is_owner, name="dispatch")
class ProjectDetail(DetailView):
    pk_url_kwarg = 'project'
    model = models.Project
    template_name = 'project_detail.html'


@method_decorator(decorators.role_required('CR'), name="dispatch")
@method_decorator(decorators.max_projects, name="dispatch")
class ProjectCreate(CreateView):
    model = models.Project
    fields = ['name']
    template_name = 'project_form.html'
    success_url = reverse_lazy('projects:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        try:
            proj = api.create_project(self.request.user, self.object.name, self.request)
        except ke.Conflict:
            form.add_error('name', 'A project with that name already exists.')
            return self.form_invalid(form)
        self.object.uuid = proj.id
        proj_name = self.object.name
        try:
            self.object.save()
        except ValidationError:
            form.add_error('name', 'A project with that name already exists.')
            return self.form_invalid(form)
        membership = models.Member(user=self.request.user, project=self.object, is_owner=True, is_creator=True)
        membership.save()
        return HttpResponseRedirect(self.get_success_url())


@method_decorator(decorators.role_required('CR'), name="dispatch")
class ProjectDelete(DeleteView):
    pk_url_kwarg = 'project'
    model = models.Project
    success_url = reverse_lazy('projects:list')
    template_name = 'project_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        api.delete_project(self.object)
        self.object.delete()
        return HttpResponseRedirect(success_url)

@method_decorator(decorators.is_owner, name="dispatch")
class MemberDelete(DeleteView):
    pk_url_kwarg = 'member'
    model = models.Member
    success_url = reverse_lazy('projects:list')
    template_name = 'member_confirm_delete.html'


@method_decorator(decorators.is_owner, name="dispatch")
class MemberCreate(CreateView):
    pk_url_kwarg = 'project'
    form_class = forms.MemberForm
    template_name = 'member_form.html'

    def form_valid(self, form):
        self.object = form.save(commit=False)
        project = models.Project.objects.get(pk=self.object.project.id)

        total = models.Member.objects.filter(project=project).aggregate(Sum('max_resources'))['max_resources__sum']

        if project.max_resources < total + self.object.max_resources:
            allowed = project.max_resources - total
            messages.add_message(self.request, messages.ERROR,
                                 'Project resource maximum met reduce member max_resources for member to less than {}.'.format(allowed))
            return HttpResponseRedirect(self.get_success_url())
        self.object.save()
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['project'] = self.kwargs['project']
        return kwargs

    def get_success_url(self):
        return reverse_lazy('projects:member_list', kwargs={'project': self.kwargs['project']})


@method_decorator(decorators.is_owner, name="dispatch")
class MemberUpdate(UpdateView):
    pk_url_kwarg = 'member'
    model = models.Member
    fields = ['is_owner', 'max_resources']
    template_name = 'member_form.html'

    def post(self, request, *args, **kwargs):
            self.object = self.get_object()
            current = models.Member.objects.get(pk=self.object.id)
            object = self.get_form().save(commit=False)

            project = models.Project.objects.get(pk=self.object.project.id)
            total = models.Member.objects.filter(project=project).aggregate(Sum('max_resources'))['max_resources__sum']

            if project.max_resources < total - current.max_resources + object.max_resources:
                allowed = project.max_resources - (total - current.max_resources)
                messages.add_message(request, messages.ERROR,
                                     'Project resource maximum met reduce member max_resources for member to less than {}.'.format(allowed))
                return HttpResponseRedirect(self.get_success_url())
            self.object = object
            self.object.save()
            return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy('projects:member_list', kwargs={'project': self.object.project.id})

@method_decorator(decorators.is_owner, name="dispatch")
class MemberList(ListView):
    pk_url_kwarg = 'project'
    model = models.Member
    fields = ['project', 'user', 'max_resources']
    template_name = 'member_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project'] = self.kwargs['project']
        return context

    def get_queryset(self):
        return models.Member.objects.filter(project=self.kwargs['project'])
