from actions import api
from django.shortcuts import render
from django.http import JsonResponse
from glanceclient import exc as glance_exc
from django.core.exceptions import ObjectDoesNotExist
from heatclient import exc as heat_exc
from novaclient import exceptions as nova_exc
from heatclient.common import template_utils
from images.models import Image
import yaml
import time
import re
from actions.decorators import resource_check
from projects import decorators
from . import decorators as a_decorators
from projects.models import Project
from django.contrib import messages
from django.conf import settings
import string
import random
from pymemcache.client.base import Client as memcache_client
from pymemcache import serde
import types
from urllib.parse import urlparse
from collections import OrderedDict


def failed(request, **kwargs):
    return render(request, 'failed.html')


def spinner(request, **kwargs):
    return render(request, 'spinner.html')


def refresh(request, **kwargs):
    MEMCACHED = memcache_client(
        (settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT),
        serializer=serde.python_memcache_serializer,
        deserializer=serde.python_memcache_deserializer
    )
    MEMCACHED.delete('stacks' + request.user.username)
    return console(request, **kwargs)


# def create_volume(request, **kwargs):
#     project = Project.objects.get(name=kwargs['project'])
#     sess = api.auth_setup(kwargs['project'])
#     cinder = api.cinder_setup(sess)
#     heat = api.heat_setup(sess)
#     volume_type = cinder.volume_types.list()[0].id
#     template_path = 'actions/heat_templates/volume.yml'
#     _files, template = template_utils.get_template_contents(template_path)
#     s_template = yaml.safe_dump(template)
#     stack_name = '{}-{}-{}-volume'.format(request.user, project.uuid, kwargs['name'])
#     parameters = {'volume_type': volume_type, 'size': kwargs['size']}
#     heat.stacks.create(stack_name=stack_name, template=s_template, parameters=parameters)
#     stack = heat.stacks.get(stack_name)
#     status = heat.resources.get(stack.id, 'Volume_1').resource_status
#     while status not in ['CREATE_COMPLETE', 'CREATE_FAILED']:
#         status = heat.resources.get(stack.id, 'Volume_1').resource_status
#         #print('Status: {}'.format(status))
#         time.sleep(1)
#     return console(request, **kwargs)



@a_decorators.owner_vm
def delete(request, **kwargs):
    MEMCACHED = memcache_client(
        (settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT),
        serializer=serde.python_memcache_serializer,
        deserializer=serde.python_memcache_deserializer
    )
    project = Project.objects.get(name=kwargs['project'])
    member = request.user.member_set.get(
            project__name=kwargs['project']
        )
    if not (kwargs['stack'].startswith(request.user.username) or member.is_owner):
        return render(request, 'failed.html')
    sess = api.auth_setup(kwargs['project'])
    heat = api.heat_setup(sess)

    stack_name = kwargs['stack']
    try:
        stack = heat.stacks.get(stack_name)
        stack.delete()
    except heat_exc.HTTPNotFound:
        # already gone
        pass
    # time.sleep(1)
    # stack = heat.stacks.get(stack_name)
    # while stack.status == 'IN_PROGRESS':
    #     try:
    #         stack = heat.stacks.get(stack_name)
    #     except heat_exc.HTTPNotFound:
    #         break
    #     print(stack.status)
    #     time.sleep(1)

    stacks = heat.stacks.list()
    stack_list = []
    for stack in stacks:
        if stack.status != 'IN_PROGRESS':
            stack_obj = types.SimpleNamespace(stack_name=stack.stack_name, id=stack.id)
            stack_list.append(stack_obj)
    MEMCACHED.set('stacks' + request.user.username, stack_list, expire=3600)
    stacks = MEMCACHED.get('stacks' + request.user.username)

    return console(request, **kwargs)


@a_decorators.owner_vm
def power(request, **kwargs):
    MEMCACHED = memcache_client(
        (settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT),
        serializer=serde.python_memcache_serializer,
        deserializer=serde.python_memcache_deserializer
    )
    project = Project.objects.get(name=kwargs['project'])
    member = request.user.member_set.get(
            project__name=kwargs['project']
        )
    if not (kwargs['stack'].startswith(request.user.username) or member.is_owner):
        return render(request, 'failed.html')
    sess = api.auth_setup(kwargs['project'])
    heat = api.heat_setup(sess)
    nova = api.nova_setup(sess)
    stack_name = kwargs['stack']
    resources = MEMCACHED.get(stack_name + '_resources_'+ request.user.username)
    if resources is None or len(resources) == 0:
        stack = heat.stacks.get(stack_name)
        resources = heat.resources.list(stack.id)
        resources_list = []

        flavors = MEMCACHED.get('flavors')
        if flavors is None:
            flavors_list = []
            flavors = nova.flavors.list()
            flavors = sorted([flavor for flavor in flavors], key=lambda flavor: flavor.name)
            for flavor in flavors:
                flavor_obj = types.SimpleNamespace(id=flavor.id, name=flavor.name, vcpus=flavor.vcpus, ram=flavor.ram, disk=flavor.disk)
                flavor_obj.flavor_usage = 0
                flavor_obj.flavor_usage += flavor_obj.vcpus * settings.R_VCPU
                flavor_obj.flavor_usage += flavor_obj.ram/1024 * settings.R_MEM_GB
                flavor_obj.flavor_usage += flavor_obj.disk * settings.R_VOLUME_GB
                flavors_list.append(flavor_obj)
                MEMCACHED.set('flavors', flavors_list, expire=86400)
                flavors = MEMCACHED.get('flavors')

        for resource in resources:
            # not ideal but we will just skip for now since it probably isn't created yet.
            try:
                server = nova.servers.get(resource.physical_resource_id)
            except (nova_exc.NotFound, nova_exc.Conflict):
                continue
            resource_obj = types.SimpleNamespace(physical_resource_id=resource.physical_resource_id, flavor=server.flavor['id'])
            resource_obj.resource_usage = 0
            for flv in flavors:
                if flv.id == resource_obj.flavor:
                    flavor = flv
                    break
            resource_obj.resource_usage += flavor.vcpus * settings.R_VCPU
            resource_obj.resource_usage += flavor.ram/1024 * settings.R_MEM_GB
            resource_obj.resource_usage += flavor.disk * settings.R_VOLUME_GB
            resources_list.append(resource_obj)

        MEMCACHED.set(stack.stack_name + '_resources_'+ request.user.username, resources_list, expire=3600)
    server = nova.servers.get(resources[0].physical_resource_id)
    instance = resources[0]
    status = server.status
    MEMCACHED = memcache_client((settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT))
    if 'reboot' in kwargs and kwargs['reboot'] == 'reboot':
        server.reboot(reboot_type='HARD')
        messages.add_message(request, messages.INFO,
                            'Hard rebooting instance this might take a few seconds to show on console. Reload Console if it doesn\'t show up after a few seconds.')
        MEMCACHED.set(kwargs['stack'] + '_server_status', 'ACTIVE')
        while status != 'ACTIVE':
            status = nova.servers.get(instance.physical_resource_id).status
            print(status)
            time.sleep(2)
    else:
        if server.status == 'ACTIVE':
            server.stop()
            messages.add_message(request, messages.INFO,
                                 'Powering off instance might take a few seconds to show on console.')
            MEMCACHED.set(kwargs['stack'] + '_server_status', 'SHUTOFF')
            while status != 'SHUTOFF':
                status = nova.servers.get(instance.physical_resource_id).status
                print(status)
                time.sleep(2)
        else:
            server.start()
            messages.add_message(request, messages.INFO,
                                 'Powering on instance might take a few seconds to show on console. Reload Console if it doesn\'t show up after a few seconds.')
            MEMCACHED.set(kwargs['stack'] + '_server_status', 'ACTIVE')
            while status != 'ACTIVE':
                status = nova.servers.get(instance.physical_resource_id).status
                print(status)
                time.sleep(2)
    return console(request, **kwargs)


@a_decorators.owner_vm
@resource_check
def launch(request, **kwargs):
    project = Project.objects.get(name=kwargs['project'])
    try:
        proj_flavor = project.flavors.get(uuid=kwargs['flavor'])
    except ObjectDoesNotExist:
        messages.add_message(request, messages.ERROR,
                             'You are not authorized to launch an instance'
                             ' with this flavor!')
        return console(request, **kwargs)
    if 'name' not in kwargs:
        kwargs['name'] = ''
    MEMCACHED = memcache_client(
        (settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT),
        serializer=serde.python_memcache_serializer,
        deserializer=serde.python_memcache_deserializer
    )
    if 'resources_maxed' in kwargs and kwargs['resources_maxed']:
        messages.add_message(request, messages.ERROR,
                             'Resource maximum delete an instance before creating a new instance!')
        return console(request, **kwargs)
    try:
        image = project.images.get(uuid=kwargs['image'])
    except ObjectDoesNotExist:
        return render(request, 'failed.html')
    sess = api.auth_setup(kwargs['project'])
    nova = api.nova_setup(sess)
    flavors = MEMCACHED.get('flavors')
    if flavors is None:
        flavors_list = []
        flavors = nova.flavors.list()
        flavors = sorted([flavor for flavor in flavors], key=lambda flavor: flavor.name)
        for flavor in flavors:
            flavor_obj = types.SimpleNamespace(id=flavor.id, name=flavor.name, vcpus=flavor.vcpus, ram=flavor.ram, disk=flavor.disk)
            flavor_obj.flavor_usage = 0
            flavor_obj.flavor_usage += flavor_obj.vcpus * settings.R_VCPU
            flavor_obj.flavor_usage += flavor_obj.ram/1024 * settings.R_MEM_GB
            flavor_obj.flavor_usage += flavor_obj.disk * settings.R_VOLUME_GB
            flavors_list.append(flavor_obj)
        MEMCACHED.set('flavors', flavors_list, expire=86400)
        flavors = MEMCACHED.get('flavors')
    for flv in flavors:
        if flv.id == kwargs['flavor']:
            flavor = flv
    kwargs['resource_usage'] += flavor.vcpus * settings.R_VCPU
    kwargs['resource_usage'] += flavor.ram/1024 * settings.R_MEM_GB
    kwargs['resource_usage'] += flavor.disk * settings.R_VOLUME_GB
    if kwargs['resource_usage'] > kwargs['max_resources']:
        messages.add_message(request, messages.ERROR,
                             'Resource maximum reached select a smaller flavor '
                             'or delete an instance before creating a new instance!')
        return console(request, **kwargs)
    stack_name = '{}-{}-{}-{}'.format(
        request.user,
        project.uuid,
        kwargs['image'],
        kwargs['name']
    )
    try:
        if image.size > flavor.disk:
            messages.add_message(request, messages.ERROR,
                                 'Flavor disk size is to small for the image '
                                 'select a flavor with disk {}GB or more!'.format(image.size))
            return console(request, **kwargs)
    except glance_exc.HTTPNotFound:
        return render(request, 'failed.html')

    template_path = 'actions/heat_templates/instance.yml'

    _files, template = template_utils.get_template_contents(template_path)
    heat = api.heat_setup(sess)
    s_template = yaml.safe_dump(template)
    stacks = MEMCACHED.get('stacks' + request.user.username)
    if stacks is None:
        stacks = heat.stacks.list()
        stack_list = []
        for stack in stacks:
            stack_obj = types.SimpleNamespace(stack_name=stack.stack_name, id=stack.id)
            stack_list.append(stack_obj)
        MEMCACHED.set('stacks' + request.user.username, stack_list, expire=3600)
        stacks = MEMCACHED.get('stacks' + request.user.username)
    for stack in stacks:
        if stack.stack_name.endswith('{}-selfservice-network'.format(project.uuid)):
            selfservice = heat.resources.get(stack.id, 'Net_1').physical_resource_id
    parameters = {'flavor': flavor.id, 'image': kwargs['image'], 'network': selfservice}
    while (True):
        try:
            random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
            heat.stacks.create(stack_name='{}-{}-instance'.format(stack_name, random_string),
                               template=s_template,
                               parameters=parameters)
            stack_name = '{}-{}-instance'.format(stack_name, random_string)
            break
        except heat_exc.HTTPConflict:
            pass

    # stack = heat.stacks.get(stack_name)
    # status = heat.resources.get(stack.id, 'Instance_1').resource_status
    # while status not in ['CREATE_COMPLETE', 'CREATE_FAILED', 'CREATE_IN_PROGRESS']:
    #     status = heat.resources.get(stack.id, 'Instance_1').resource_status
    #     print('Status: {}'.format(status))
    #     time.sleep(1)
    stacks = heat.stacks.list()
    stack_list = []
    for stack in stacks:
        stack_obj = types.SimpleNamespace(stack_name=stack.stack_name, id=stack.id)
        stack_list.append(stack_obj)
    MEMCACHED.set('stacks' + request.user.username, stack_list, expire=3600)
    stacks = MEMCACHED.get('stacks' + request.user.username)
    messages.add_message(request, messages.INFO,
                         'Launching instance might take a few seconds to show below. Reload Console if it doesn\'t show up after a few seconds.')
    return console(request, **kwargs)


@a_decorators.owner_vm
@resource_check
def console(request, **kwargs):
    MEMCACHED = memcache_client(
        (settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT),
        serializer=serde.python_memcache_serializer,
        deserializer=serde.python_memcache_deserializer
    )
    project = Project.objects.get(name=kwargs['project'])
    proj_flavors = project.flavors.values_list('name', flat=True)
    avail_images = project.images.all()
    sess = api.auth_setup(kwargs['project'])
    heat = api.heat_setup(sess)
    nova = api.nova_setup(sess)
    flavors = MEMCACHED.get('flavors')
    if flavors is None:
        flavors_list = []
        flavors = nova.flavors.list()
        flavors = sorted([flavor for flavor in flavors], key=lambda flavor: flavor.name)
        for flavor in flavors:
            flavor_obj = types.SimpleNamespace(id=flavor.id, name=flavor.name, vcpus=flavor.vcpus, ram=flavor.ram, disk=flavor.disk)
            flavor_obj.flavor_usage = 0
            flavor_obj.flavor_usage += flavor_obj.vcpus * settings.R_VCPU
            flavor_obj.flavor_usage += flavor_obj.ram/1024 * settings.R_MEM_GB
            flavor_obj.flavor_usage += flavor_obj.disk * settings.R_VOLUME_GB
            flavors_list.append(flavor_obj)
        MEMCACHED.set('flavors', flavors_list, expire=86400)
        flavors = MEMCACHED.get('flavors')
    stacks = MEMCACHED.get('stacks' + request.user.username)
    if stacks is None:
        stacks = heat.stacks.list()
        stack_list = []
        for stack in stacks:
            stack_obj = types.SimpleNamespace(stack_name=stack.stack_name, id=stack.id)
            stack_list.append(stack_obj)
        MEMCACHED.set('stacks' + request.user.username, stack_list, expire=3600)
        stacks = MEMCACHED.get('stacks' + request.user.username)
    images = Image.objects.all()
    user_stacks = {}
    for stack in stacks:
        if (stack.stack_name.startswith(request.user.username) \
                or request.user.member_set.get(
                    project__name=kwargs['project']).is_owner) \
                and stack.stack_name.endswith('-instance') \
                and project.uuid in stack.stack_name:
            s_name = stack.stack_name
            l_name = s_name.split('-')
            s_image = None
            for image in images:
                if image.uuid in s_name:
                    s_image = image
            user_stacks[s_name] = {
                'stack': stack,
                'user': l_name[0],
                'image': s_image,
                'iteration': l_name[-2],
                'name': l_name[-3],
            }
    if user_stacks:
        # lets sort by username.
        stack_names = user_stacks.keys()
        ordered_stacks = []
        for stack_name in stack_names:
            if stack_name.startswith(request.user.username):
                ordered_stacks.insert(0, stack_name)
            else:
                ordered_stacks.append(stack_name)
        ordered_dict = OrderedDict()
        for stack in ordered_stacks:
            ordered_dict[stack] = user_stacks[stack]
        context = {
            'user_stacks': ordered_dict,
            'project': kwargs['project'],
            'images': avail_images,
            'flavors': flavors,
            'proj_flavors': proj_flavors,
            'resource_usage': kwargs['resource_usage'],
            'max_resources': kwargs['max_resources']
        }
        return render(request, 'console.html', context)
    else:
        context = {
            'images': avail_images,
            'project': kwargs['project'],
            'flavors': flavors,
            'proj_flavors': proj_flavors,
            'resource_usage': kwargs['resource_usage'],
            'max_resources': kwargs['max_resources']
        }
        return render(request, 'console_none.html', context=context)


@a_decorators.owner_vm
def console_url(request, **kwargs):
    MEMCACHED = memcache_client((settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT))
    sess = api.auth_setup(kwargs['project'])
    heat = api.heat_setup(sess)
    nova = api.nova_setup(sess)
    while (True):
        try:
            time.sleep(1)
            vnc_url = MEMCACHED.get(kwargs['stack'] + '_vnc_url')
            server_status = MEMCACHED.get(kwargs['stack'] + '_server_status')
            if vnc_url is None or server_status is None:
                instance = heat.resources.get(kwargs['stack'], 'Instance_1')
                server = nova.servers.get(instance.physical_resource_id)
                vnc_url = server.get_vnc_console('novnc')
                vnc_url = vnc_url['console']['url']
                server_status = server.status
                # set vnc url in memcache expire after 1 hour
                # Openstack expires urls after 24 hours
                MEMCACHED.set(kwargs['stack'] + '_vnc_url', vnc_url, expire=3600)
                MEMCACHED.set(kwargs['stack'] + '_server_status', server_status)
                vnc_url = MEMCACHED.get(kwargs['stack'] + '_vnc_url')
                server_status = MEMCACHED.get(kwargs['stack'] + '_server_status')
            vnc_url = urlparse(vnc_url.decode())

            if settings.CONSOLE_HOST:
               vnc_url = vnc_url._replace(netloc=settings.CONSOLE_HOST)
            if settings.CONSOLE_PATH:
               vnc_url = vnc_url._replace(path="/{}/{}/{}{}".format(
                   settings.CONSOLE_PATH, kwargs['project'], kwargs['stack'], vnc_url.path)
               )
            server_status = server_status.decode()
            data = {
                'vnc_url': vnc_url.geturl() + "&autoconnect=true&resize=scale&show_dot=true",
                'state': 'Off' if server_status == 'ACTIVE' else 'On'
            }
            break
        except (nova_exc.NotFound, nova_exc.Conflict) as e:
            time.sleep(1)

    return JsonResponse(data)

@a_decorators.owner_vm
def console_url_force(request, **kwargs):
    MEMCACHED = memcache_client((settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT))
    sess = api.auth_setup(kwargs['project'])
    heat = api.heat_setup(sess)
    nova = api.nova_setup(sess)
    while (True):
        try:
            instance = heat.resources.get(kwargs['stack'], 'Instance_1')
            server = nova.servers.get(instance.physical_resource_id)
            vnc_url = server.get_vnc_console('novnc')['console']['url']
            server_status = server.status
            # set vnc url in memcache expire after 1 hour
            # Openstack expires urls after 24 hours
            MEMCACHED.set(kwargs['stack'] + '_vnc_url', vnc_url, expire=3600)
            MEMCACHED.set(kwargs['stack'] + '_server_status', server_status)
            vnc_url = MEMCACHED.get(kwargs['stack'] + '_vnc_url')
            server_status = MEMCACHED.get(kwargs['stack'] + '_server_status')
            vnc_url = urlparse(vnc_url.decode())

            if settings.CONSOLE_HOST:
               vnc_url = vnc_url._replace(netloc=settings.CONSOLE_HOST)
            if settings.CONSOLE_PATH:
               vnc_url = vnc_url._replace(path="/{}/{}/{}{}".format(
                   settings.CONSOLE_PATH, kwargs['project'], kwargs['stack'], vnc_url.path)
               )

            server_status = server_status.decode()
            data = {
                'vnc_url': vnc_url.geturl() + "&autoconnect=true&resize=scale&show_dot=true",
                'state': 'Off' if server_status == 'ACTIVE' else 'On'
            }
            break
        except (nova_exc.NotFound, nova_exc.Conflict) as e:
            time.sleep(1)

    return JsonResponse(data)
