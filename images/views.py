from django.shortcuts import render
from django.views.generic.edit import UpdateView, CreateView, DeleteView
from django.views.generic import DetailView
from django.utils.decorators import method_decorator
from django.views.generic.list import ListView
from projects import decorators
from django.urls import reverse_lazy
from django.contrib.admin.views.decorators import staff_member_required
from . import models
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.contrib import messages
from projects.models import Project
from . import forms
from actions import api



@method_decorator(decorators.is_staff, name='dispatch')
class ImageDelete(DeleteView):
    success_url = reverse_lazy('images:list')
    pk_url_kwarg = 'image'
    model = models.Image
    template_name = 'image_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        project = Project.objects.first()
        self.object = self.get_object()
        success_url = self.get_success_url()
        if api.image_in_use(project, self.object):
            messages.add_message(request, messages.ERROR,
                                 'Image is in use cannot be deleted.')
            raise PermissionDenied
        else:
            self.object.delete()
            return HttpResponseRedirect(success_url)


@method_decorator(decorators.is_staff, name='dispatch')
class ImageCreate(CreateView):
    success_url = reverse_lazy('images:list')
    model = models.Image
    fields = ['name', 'projects']
    template_name = 'image_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.uuid = api.get_image_uuid(self.object.name)
        self.object.size = api.get_image_size(self.object.uuid)
        self.object.save()
        return response


@method_decorator(decorators.is_owner, name='dispatch')
class ImageList(ListView):
    model = models.Image
    fields = ['name', 'projects']
    template_name = 'image_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projects'] = models.Project.objects.filter(id__in=self.request.user.member_set.filter(is_owner=True).values_list('project'))
        return context


@method_decorator(decorators.is_owner, name='dispatch')
class ImageUpdate(UpdateView):
    pk_url_kwarg = 'image'
    form_class = forms.ImageForm
    model = models.Image
    success_url = reverse_lazy('images:list')
    template_name = 'image_form.html'

    def get_form_kwargs(self):
        object = self.get_object()
        kwargs = super().get_form_kwargs()
        kwargs['projects'] = models.Project.objects.filter(id__in=self.request.user.member_set.filter(is_owner=True).values_list('project'))
        self.projects_list = kwargs['projects']
        return kwargs

    def form_valid(self, form):
        previous_projects = [project for project in models.Image.objects.get(pk=self.kwargs['image']).projects.all()]
        self.object = form.save()
        current_projects = [project for project in self.object.projects.all()]
        for project in previous_projects:
            if project not in self.projects_list:
                self.object.projects.add(project)
        return HttpResponseRedirect(self.get_success_url())
