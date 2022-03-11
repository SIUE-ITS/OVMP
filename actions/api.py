from keystoneauth1 import identity
from keystoneauth1 import session
from keystoneclient.v3 import client as keystone_client
from heatclient import client as heat_client
from novaclient import client as nova_client
from neutronclient.v2_0 import client as neutron_client
from django.conf import settings
from glanceclient import client as glance_client
from heatclient.common import template_utils
import yaml
import time
from pymemcache.client.base import Client as memcache_client
from pymemcache import serde
import types


def auth_setup(project):
    auth = identity.V3Password(
        auth_url=settings.KEYSTONE_AUTH_URL,
        username=settings.KEYSTONE_USERNAME,
        user_domain_name=settings.KEYSTONE_USER_DOMAIN_NAME,
        password=settings.KEYSTONE_PASSWORD,
        project_name=project,
        project_domain_name=settings.KEYSTONE_PROJECT_DOMAIN_NAME
    )
    return session.Session(auth=auth)


def auth_domain_setup():
    auth = identity.V3Password(
        auth_url=settings.KEYSTONE_AUTH_URL,
        username=settings.KEYSTONE_USERNAME,
        user_domain_name=settings.KEYSTONE_USER_DOMAIN_NAME,
        password=settings.KEYSTONE_PASSWORD,
        domain_name=settings.KEYSTONE_USER_DOMAIN_NAME,
        project_domain_name=settings.KEYSTONE_PROJECT_DOMAIN_NAME
    )
    return session.Session(auth=auth)


def heat_setup(sess):
    return heat_client.Client('1', session=sess, endpoint_type='public',
                              service_type='orchestration')


def nova_setup(sess):
    return nova_client.Client('2.1', session=sess)


def glance_setup(sess):
    return glance_client.Client('2', session=sess)


def neutron_setup(sess):
    return neutron_client.Client(session=sess)


def keystone_setup(sess):
    keystone = keystone_client.Client(session=sess, endpoint_override=settings.KEYSTONE_AUTH_URL)


def get_image_size(image):
    sess = auth_domain_setup()
    glance = glance_setup(sess)
    return len(glance.images.data(image)) / 1073741824


def get_project_uuid(project):
    sess = auth_domain_setup()
    keystone = keystone_setup(sess)
    projects = keystone.projects.list()
    for proj in projects:
        if proj.name.lower() == project.lower():
            return proj


def delete_project(project):
    sess = auth_domain_setup()
    keystone = keystone_client.Client(session=sess, endpoint_override=settings.KEYSTONE_AUTH_URL)
    sess = auth_setup(project.name)
    heat = heat_setup(sess)
    all_stacks = heat.stacks.list()
    proj_stacks = []
    for stack in all_stacks:
        if project.uuid in stack.stack_name:
            stack.delete()
    keystone.projects.delete(project.uuid)


def create_project(user, project, request):
    MEMCACHED = memcache_client(
        (settings.MEMCACHED_SERVER, settings.MEMCACHED_PORT),
        serializer=serde.python_memcache_serializer,
        deserializer=serde.python_memcache_deserializer
    )
    sess = auth_domain_setup()
    keystone = keystone_client.Client(session=sess, endpoint_override=settings.KEYSTONE_AUTH_URL)
    domains = keystone.domains.list()
    for domain in domains:
        if domain.name.lower() == settings.KEYSTONE_USER_DOMAIN_NAME.lower():
            domain_id = domain.id
    roles = keystone.roles.list()
    for role in roles:
        if role.name.lower() == 'admin':
            role_id = role.id
    kusers = keystone.users.list()
    for kuser in kusers:
        if kuser.name.lower() == settings.KEYSTONE_USERNAME:
            user_id = kuser.id
    proj = keystone.projects.create(
        project,
        domain_id,
        enabled=True
    )
    role_assignment = keystone.roles.grant(
        role_id,
        user=user_id,
        project=proj.id
    )
    sess = auth_setup(project)
    heat = heat_setup(sess)
    template_path = 'actions/heat_templates/network.yml'
    _files, template = template_utils.get_template_contents(template_path)
    s_template = yaml.safe_dump(template)
    stack_name = '{}-{}-selfservice-network'.format(user.username, proj.id)
    parameters = {'external_net': settings.OPENSTACK_EXT_NET}
    heat.stacks.create(stack_name=stack_name, template=s_template, parameters=parameters)
    stack = heat.stacks.get(stack_name)
    status = heat.resources.get(stack.id, 'RouterInterface_1').resource_status
    while status not in ['CREATE_COMPLETE', 'CREATE_FAILED']:
        status = heat.resources.get(stack.id, 'RouterInterface_1').resource_status
        #print('Status: {}'.format(status))
        time.sleep(1)
    nova = nova_setup(sess)
    nova.quotas.update(proj.id, cores=100, instances=100, ram=204800)
    stacks = heat.stacks.list()
    stack_list = []
    for stack in stacks:
        stack_obj = types.SimpleNamespace(stack_name=stack.stack_name, id=stack.id)
        stack_list.append(stack_obj)
    MEMCACHED.set('stacks' + request.user.username, stack_list, expire=3600)
    stacks = MEMCACHED.get('stacks' + request.user.username)
    return proj


def image_in_use(project, image):
    sess = auth_setup(project.name)
    heat = heat_setup(sess)
    stacks = heat.stacks.list()
    for stack in stacks:
        if image.uuid in stack.stack_name:
            return True
    return False



def get_image_uuid(image):
    sess = auth_domain_setup()
    glance = glance_setup(sess)
    images = glance.images.list()
    for img in images:
        if img.name.lower() == image.lower():
            return img.id
