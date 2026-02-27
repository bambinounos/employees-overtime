from django.urls import path
from . import views

app_name = 'psicoevaluacion'

urlpatterns = [
    # --- Candidato (público, con token) ---
    path('evaluar/<str:token>/', views.inicio_evaluacion, name='inicio_evaluacion'),
    path('evaluar/<str:token>/verificar/', views.verificar_candidato, name='verificar_candidato'),
    path('evaluar/<str:token>/prueba/<str:tipo_prueba>/', views.realizar_prueba, name='realizar_prueba'),
    path('evaluar/<str:token>/finalizar/', views.finalizar_evaluacion, name='finalizar_evaluacion'),

    # --- API para guardar respuestas (AJAX) ---
    path('api/respuesta/psicometrica/', views.api_guardar_psicometrica, name='api_psicometrica'),
    path('api/respuesta/memoria/', views.api_guardar_memoria, name='api_memoria'),
    path('api/respuesta/matriz/', views.api_guardar_matriz, name='api_matriz'),
    path('api/respuesta/proyectiva/', views.api_guardar_proyectiva, name='api_proyectiva'),
    path('api/respuesta/situacional/', views.api_guardar_situacional, name='api_situacional'),

    # --- Panel del evaluador (requiere login) ---
    path('panel/dashboard/', views.dashboard_evaluador, name='dashboard_evaluador'),
    path('panel/crear/', views.crear_evaluacion, name='crear_evaluacion'),
    path('panel/evaluacion/<int:pk>/', views.detalle_evaluacion, name='detalle_evaluacion'),
    path('panel/evaluacion/<int:pk>/revisar-proyectivas/', views.revisar_proyectivas, name='revisar_proyectivas'),
    path('panel/evaluacion/<int:pk>/descargar-proyectivas/', views.descargar_proyectivas, name='descargar_proyectivas'),
    path('panel/evaluacion/<int:pk>/calificar-ia/', views.calificar_con_ia, name='calificar_con_ia'),
    path('panel/evaluacion/<int:pk>/aplicar-calificacion/', views.aplicar_calificacion_ia, name='aplicar_calificacion_ia'),
    path('panel/evaluacion/<int:pk>/calcular/', views.calcular_resultados, name='calcular_resultados'),
    path('panel/evaluacion/<int:pk>/reporte/', views.generar_reporte, name='generar_reporte'),
    path('panel/evaluacion/<int:pk>/veredicto/', views.asignar_veredicto, name='asignar_veredicto'),
    path('panel/comparativo/', views.comparativo, name='comparativo'),
]
