#!/usr/bin/env python

import sys
sys.path.insert(0, '/opt/ovmp')
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "ovmp.settings"

import django
django.setup()

from projects.models import Project, Member
from images.models import Image
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from actions.views import launch
from types import SimpleNamespace

def main():

    proj=Project.objects.get(name=sys.argv[1])

    with open('users.txt', 'r') as fh:
        users = fh.readlines()
        for user in users:
            try:
                u = User.objects.create_user(user.strip())
                u.save()
                print('user created', user.strip())
            except IntegrityError:
                u = User.objects.get(username=user.strip())
                print('user already exists', user.strip())
            try:
                m = Member(user=u, project=proj, max_resources=100)
                m.save()
                print('member created', user.strip())
            except IntegrityError:
                print('member already exists', user.strip())



if __name__ == '__main__':
    main()
