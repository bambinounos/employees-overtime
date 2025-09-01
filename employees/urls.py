from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

from django.urls import path, include

urlpatterns = [
    path('', views.index, name='index'),
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/<int:employee_id>/salary/', views.employee_salary, name='employee_salary'),
    path('board/', views.task_board, name='task_board'),
    path('reports/', views.performance_report, name='performance_report'),
    path('login/', auth_views.LoginView.as_view(template_name='employees/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
    path('api/', include('employees.api_urls')),
]
