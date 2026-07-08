from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

from django.urls import path, include

urlpatterns = [
    path('', views.index, name='index'),
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/<int:employee_id>/salary/', views.employee_salary, name='employee_salary'),
    path('employees/<int:employee_id>/terminate/', views.terminate_employee, name='terminate_employee'),
    path('board/', views.task_board, name='task_board'),
    path('dashboard/', views.strategic_dashboard, name='strategic_dashboard'),
    path('reports/', views.performance_report, name='performance_report'),
    path('ranking/', views.employee_ranking, name='employee_ranking'),
    path('settings/', views.company_settings, name='company_settings'),
    path('mi-panel/', views.mi_panel, name='mi_panel'),
    path('ausencias/', views.mis_ausencias, name='mis_ausencias'),
    path('ausencias/aprobar/', views.ausencias_pendientes, name='ausencias_pendientes'),
    path('ausencias/<int:solicitud_id>/decidir/', views.decidir_ausencia, name='decidir_ausencia'),
    path('mis-recibos/', views.mis_recibos, name='mis_recibos'),
    path('recibos/<int:employee_id>/<int:year>/<int:month>/pdf/', views.recibo_pdf, name='recibo_pdf'),
    path('nomina/', views.nomina_cierre, name='nomina_cierre'),
    path('nomina/planilla/', views.nomina_planilla, name='nomina_planilla'),
    path('post-login/', views.post_login, name='post_login'),
    path('login/', auth_views.LoginView.as_view(template_name='employees/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
    path('api/', include('employees.api_urls')),
]
