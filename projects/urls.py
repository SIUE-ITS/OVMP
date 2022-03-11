from django.urls import path
from . import views


app_name = 'projects'

urlpatterns = [
    path('', views.ProjectList.as_view(), name='list'),
    path('create/', views.ProjectCreate.as_view(), name='create'),
    path('delete/<project>/', views.ProjectDelete.as_view(), name='delete'),
    path('detail/<project>/', views.ProjectDetail.as_view(), name='detail'),
    path('user/', views.UserList.as_view(), name='user_list'),
    path('user/create/', views.UserCreate.as_view(), name='user_create'),
    path('user/delete/<user>', views.UserDelete.as_view(), name='user_delete'),
    path('member/delete/<member>/', views.MemberDelete.as_view(),
         name='member_delete'),
     path('member/create/<project>/', views.MemberCreate.as_view(),
          name='member_create'),
    path('member/update/<member>/', views.MemberUpdate.as_view(),
         name='member_update'),
    path('member/list/<project>/', views.MemberList.as_view(), name='member_list'),
]
