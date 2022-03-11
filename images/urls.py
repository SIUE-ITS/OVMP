from django.urls import path
from . import views

app_name = 'images'

urlpatterns = [
    path('', views.ImageList.as_view(), name='list'),
    path('delete/<image>/', views.ImageDelete.as_view(), name='delete'),
    path('update/<image>/', views.ImageUpdate.as_view(), name='update'),
    path('create/', views.ImageCreate.as_view(), name='create'),
]
