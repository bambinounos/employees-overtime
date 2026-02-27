from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from .models import Evaluacion


# --- Helpers ---

def _get_evaluacion_or_404(token):
    evaluacion = get_object_or_404(Evaluacion, token=token)
    if evaluacion.esta_expirada() and evaluacion.estado == 'PENDIENTE':
        evaluacion.estado = 'EXPIRADA'
        evaluacion.save(update_fields=['estado'])
    return evaluacion


# --- Candidato (público, con token) ---

def inicio_evaluacion(request, token):
    """Página de bienvenida para el candidato."""
    evaluacion = _get_evaluacion_or_404(token)
    if evaluacion.estado == 'EXPIRADA':
        return render(request, 'psicoevaluacion/error_expirado.html', status=410)
    return render(request, 'psicoevaluacion/inicio_candidato.html', {
        'evaluacion': evaluacion,
    })


def verificar_candidato(request, token):
    """Verificar datos del candidato antes de iniciar."""
    evaluacion = _get_evaluacion_or_404(token)
    return render(request, 'psicoevaluacion/verificar_candidato.html', {
        'evaluacion': evaluacion,
    })


def realizar_prueba(request, token, tipo_prueba):
    """Renderizar la prueba correspondiente."""
    evaluacion = _get_evaluacion_or_404(token)
    return render(request, f'psicoevaluacion/prueba_{tipo_prueba.lower()}.html', {
        'evaluacion': evaluacion,
    })


def finalizar_evaluacion(request, token):
    """Pantalla de finalización."""
    evaluacion = _get_evaluacion_or_404(token)
    return render(request, 'psicoevaluacion/finalizacion.html', {
        'evaluacion': evaluacion,
    })


# --- API para guardar respuestas (AJAX) - Stubs ---

@require_POST
def api_guardar_psicometrica(request):
    """Stub: guardar respuesta psicométrica."""
    return JsonResponse({'status': 'not_implemented'}, status=501)


@require_POST
def api_guardar_memoria(request):
    """Stub: guardar respuesta de memoria."""
    return JsonResponse({'status': 'not_implemented'}, status=501)


@require_POST
def api_guardar_matriz(request):
    """Stub: guardar respuesta de matriz."""
    return JsonResponse({'status': 'not_implemented'}, status=501)


@require_POST
def api_guardar_proyectiva(request):
    """Stub: guardar respuesta proyectiva."""
    return JsonResponse({'status': 'not_implemented'}, status=501)


@require_POST
def api_guardar_situacional(request):
    """Stub: guardar respuesta situacional."""
    return JsonResponse({'status': 'not_implemented'}, status=501)


# --- Panel del evaluador (requiere login) - Stubs ---

@login_required
def dashboard_evaluador(request):
    """Stub: Dashboard del evaluador."""
    return render(request, 'psicoevaluacion/admin/dashboard.html')


@login_required
def crear_evaluacion(request):
    """Stub: Crear nueva evaluación."""
    return render(request, 'psicoevaluacion/admin/crear_evaluacion.html')


@login_required
def detalle_evaluacion(request, pk):
    """Stub: Detalle de evaluación."""
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    return render(request, 'psicoevaluacion/admin/detalle_candidato.html', {
        'evaluacion': evaluacion,
    })


@login_required
def revisar_proyectivas(request, pk):
    """Stub: Revisión de pruebas proyectivas."""
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    return render(request, 'psicoevaluacion/admin/revisar_proyectivas.html', {
        'evaluacion': evaluacion,
    })


@login_required
def calcular_resultados(request, pk):
    """Stub: Calcular resultados."""
    return JsonResponse({'status': 'not_implemented'}, status=501)


@login_required
def generar_reporte(request, pk):
    """Stub: Generar reporte PDF."""
    return JsonResponse({'status': 'not_implemented'}, status=501)


@login_required
def asignar_veredicto(request, pk):
    """Stub: Asignar veredicto manual."""
    return JsonResponse({'status': 'not_implemented'}, status=501)


@login_required
def comparativo(request):
    """Stub: Vista comparativa de candidatos."""
    return render(request, 'psicoevaluacion/admin/comparativo.html')
