#!/usr/bin/env python
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "ovmp.settings"

import django
django.setup()

from projects.models import Project
from images.models import Image
from django.contrib.auth.models import User
from actions.views import launch
import sys
from types import SimpleNamespace

def main():

    proj=Project.objects.get(name=sys.argv[1])

    members=proj.member_set.filter(is_owner=False)
    users=User.objects.filter(member__in=members)
    for user in users:
        user.is_active = False
        user.save()
        


if __name__ == '__main__':
    main()

