# OVMP
OpenStack Virtual Machine Portal

### Early project
We need help with development if you are interested also if you have any issues do not hesitate to contact us at its-cluster-support@siue.edu.

#### Note
Below configurations reference an example saml2 authentication if you need help implementing an authentication mechanism contact us from email above.

### Description
Django application which provides simplified access to OpenStack VM management. Allows users to login, create projects, add users, create instances, and much more. Administrators are able to limit projects to specific resources given the weights in the configuration below. External authentication can easily be plugged in by using the `/etc/ovmp/local_settings.py` file.

### Configuration

#### Required and example file for configuration.

`/etc/ovmp/local_settings.py`

```
import sys
import importlib

from split_settings.tools import include

# Django stuff reference docs.
ALLOWED_HOSTS = ['*']

SECRET_KEY = '{{ ovmp_secret_key }}'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': '{{ ovmp_database }}',
        'USER': '{{ ovmp_database_user }}',
        'PASSWORD': '{{ ovmp_database_password }}',
        'HOST': 'localhost',
    }
}

# You'll want a separate domain with an ovmp user and project. OpenStack ovmp user requires admin role system and domain assignment.
KEYSTONE_AUTH_URL = '{{ keystone_auth_url }}'
KEYSTONE_USERNAME = '{{ keystone_username }}'
KEYSTONE_USER_DOMAIN_NAME = '{{ keystone_user_domain_name }}'
KEYSTONE_PASSWORD = '{{ keystone_password }}'
KEYSTONE_PROJECT_DOMAIN_NAME = '{{ keystone_project_domain_name }}'

# The Neutron external network UUID for the virtual router created when a project is created. Required in general but also gives internet access to VM(s).
OPENSTACK_EXT_NET = '{{ openstack_ext_net }}'

# Weights to apply to resources
R_VOLUME_GB = .1
R_VCPU = 1
R_MEM_GB = 1
R_FLOATING_IP = 1

# Console should be the hostname of the OVMP server.
CONSOLE_HOST = '{{ inventory_hostname }}'

# Console upstream is where your nova novnc proxy is living for example could be something like os-ctl.example.com:6080.
CONSOLE_UPSTREAM = 'https://{{ console_upstream }}'
CONSOLE_PATH = 'console'

# attempt to import apps in '/etc/ovmp/local_settings/settings.py
sys.path.insert(0, '/etc/ovmp')
location = 'local_settings'
importlib.import_module(location + '.settings')

# You likely want a custom urls to use for plugging in your own authentication.
ROOT_URLCONF = 'local_settings.urls'

# Include settings for your authentication if you don't want to use Django auth.
# include('/etc/ovmp/saml2_settings/settings.py')
```

#### Example local_settings app for setting extra urls and stuff.

`/etc/ovmp/local_settings/__init__.py`

```
default_app_config = 'local_settings.apps.LocalSettingsAppConfig'
```

`/etc/ovmp/local_settings/apps.py`

```
from django.apps import AppConfig


class LocalSettingsAppConfig(AppConfig):
    name = 'local_settings'
```

`/etc/ovmp/local_settings/settings.py`

```
from ovmp.settings import INSTALLED_APPS


if 'local_settings' not in INSTALLED_APPS:
    INSTALLED_APPS += [
        'local_settings',
    ]
```

Note: below example file is including an authentication url commented out as saml2.

`/etc/ovmp/local_settings/urls.py`

```
from django.urls import include, path
# import saml2_settings.urls as saml2_urls

urlpatterns = [
    # path('saml2/', include(saml2_urls)),
    path('', include('ovmp.urls')),
]
```

#### Example nginx config required for novnc revproxy to work


`/etc/nginx/conf.d/ovmp.conf`

```
upstream nova-consoleproxy {
    server {{ console_upstream }};
}

server {
   listen 80;
   server_name {{ inventory_hostname }};
   return 301 https://$server_name$request_uri;
}

server {
    listen 443;
    server_name {{ inventory_hostname }};

    ssl on;
    ssl_certificate /etc/letsencrypt/live/{{ inventory_hostname }}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{{ inventory_hostname }}/privkey.pem;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";

    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Cache-Control no-cache;


    if ($http_upgrade = "websocket"){
        rewrite ^(.*)$ /websockify/$1;
    }

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        root /opt/ovmp;
    }

    location / {
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://unix:/tmp/ovmp.sock;
        proxy_connect_timeout       60s;
        proxy_send_timeout          60s;
        proxy_read_timeout          60s;
        send_timeout                60s;
    }

    location /websockify {
        rewrite ^/websockify/(.*)$ $1 break;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Server $host;
        proxy_set_header x-forwarded-proto https;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_read_timeout 86400;

        proxy_pass http://nova-consoleproxy;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### Example systemd service file

`/etc/systemd/system/ovmp.service`

```
[Unit]
Description=django daemon
After=network.target

[Service]
User=ovmp
Group=www-data
WorkingDirectory=/opt/ovmp
ExecStart=/opt/ovmp/venv/bin/gunicorn --capture-output --enable-stdio-inheritance --log-file /var/log/ovmp/error.log --workers 8 --bind unix:/tmp/ovmp.sock ovmp.wsgi:application

[Install]
WantedBy=multi-user.target
```
