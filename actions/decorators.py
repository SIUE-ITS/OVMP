from actions import api
from django.contrib import messages
from django.conf import settings
from projects import models
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from pymemcache.client.base import Client as memcache_client
from pymemcache import serde
from novaclient import exceptions as nova_exc
import types


def resource_check(function):
    def wrap(request, *args, **kwargs):
        MEMCACHED = memcache_client(
            (settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT),
            serializer=serde.python_memcache_serializer,
            deserializer=serde.python_memcache_deserializer
        )
        member = request.user.member_set.get(project__name=kwargs['project'])
        sess = api.auth_setup(kwargs['project'])
        heat = api.heat_setup(sess)
        nova = api.nova_setup(sess)
        stacks = MEMCACHED.get('stacks' + request.user.username)
        if stacks is None:
            stacks = heat.stacks.list()
            stack_list = []
            for stack in stacks:
                stack_obj = types.SimpleNamespace(stack_name=stack.stack_name, id=stack.id)
                stack_list.append(stack_obj)
            MEMCACHED.set('stacks' + request.user.username, stack_list, expire=3600)
            stacks = MEMCACHED.get('stacks' + request.user.username)

        user_stacks = []
        resource_usage = 0
        for stack in stacks:
            if stack.stack_name.endswith('instance') \
                    and member.project.uuid in stack.stack_name \
                    and stack.stack_name.startswith(request.user.username):
                user_stacks.append(stack)

        for stack in user_stacks:
            resources = MEMCACHED.get(stack.stack_name + '_resources_'+ request.user.username)

            if resources is None or len(resources) == 0:
                resources=heat.resources.list(stack.id)
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
                resources = MEMCACHED.get(stack.stack_name + '_resources_'+ request.user.username)
            for resource in resources:
                resource_usage += resource.resource_usage
        if resource_usage >= member.max_resources:
            kwargs['resources_maxed'] = True
            # messages.add_message(request, messages.ERROR,
            #                      'Resource maximum reached delete an '
            #                      'instance before creating a new one!')
        kwargs['resource_usage'] = resource_usage
        kwargs['max_resources'] = member.max_resources
        return function(request, *args, **kwargs)
    return wrap

def owner_vm(function):
    def wrap(request, *args, **kwargs):
        try:
            member = request.user.member_set.get(project__name=kwargs['project'])
        except ObjectDoesNotExist:
            raise PermissionDenied
        if 'stack' not in kwargs:
            return function(request, *args, **kwargs)
        if member.is_owner or kwargs['stack'].startswith(request.user.username):
            return function(request, *args, **kwargs)
        else:
            raise PermissionDenied
    return wrap
