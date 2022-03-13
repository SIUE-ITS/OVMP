#!/usr/bin/env python
import sys
sys.path.insert(0, '/opt/ovmp')
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "ovmp.settings"

import django
django.setup()

from projects.models import Project
from images.models import Image
from django.contrib.auth.models import User
from actions.views import launch
from types import SimpleNamespace


def main():

    proj=Project.objects.get(name=sys.argv[1])
    image=Image.objects.get(name=sys.argv[2])
    flavor=proj.flavors.get(name=sys.argv[3])

    members=proj.member_set.all()
    users=User.objects.filter(member__in=members)
    kwargs = {
        "project": proj.name,
        "flavor": flavor.uuid,
        "image": image.uuid,
        "resources_maxed": False,
        "resource_usage": 0,
        "max_resources": 1000000,
    }
    for user in users:
        request = SimpleNamespace(user=user)
        try:
            launch(request, **kwargs)
        except TypeError:
            print("Created -> {}, {}".format(user.username, image.name))

if __name__ == '__main__':
    main()
