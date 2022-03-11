from django.urls import path

from . import views


app_name = 'actions'


urlpatterns = [
    path('failed/', views.failed, name='failed'),
    path('spinner/', views.spinner, name='spinner'),
    path('console_url/<project>/<stack>/', views.console_url,
         name='console_url'),
    path('console_url_force/<project>/<stack>/', views.console_url_force,
         name='console_url_force'),
    path('refresh/<project>/', views.refresh, name='refresh'),
    path('console/<project>/', views.console, name='console'),
    path('console/<project>/<image>/', views.console, name='console_image'),
    path('launch/<project>/<image>/<flavor>/', views.launch, name='launch'),
    path('launch/<project>/<image>/<flavor>/<name>', views.launch, name='launch_name'),
    # path('launch/<project>/<image>/<inst_user>', views.launch, name='launch_image_user'),
    path('power/<project>/<stack>/', views.power, name='power'),
    path('power/<project>/<stack>/<reboot>', views.power, name='power_reboot'),
    path('delete/<project>/<stack>/', views.delete, name='delete'),
    #path('volume/create/<project>/<size>/<name>', views.create_volume, name='volume_create'),
]
