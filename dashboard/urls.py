from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='dashboard'),
    path('<project>/', views.index, name='dashboard_project'),
]
