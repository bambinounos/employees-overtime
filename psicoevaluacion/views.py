import io
import json
import logging
import zipfile

from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse

from .models import (
    Evaluacion, Prueba, Pregunta, Opcion,
    RespuestaPsicometrica, RespuestaProyectiva,
    RespuestaMemoria, RespuestaMatriz, RespuestaSituacional,
    ResultadoFinal,
)
import random

from .utils import seleccionar_preguntas_evaluacion
from .scoring import calcular_resultado_final

logger = logging.getLogger(__name__)


# --- Helpers ---

def _get_evaluacion_or_404(token):
    evaluacion = get_object_or_404(Evaluacion, token=token)
    if evaluacion.esta_expirada() and evaluacion.estado == 'PENDIENTE':
        evaluacion.estado = 'EXPIRADA'
        evaluacion.save(update_fields=['estado'])
    return evaluacion


TEMPLATE_MAP = {
    'BIGFIVE': 'psicoevaluacion/prueba_likert.html',
    'COMPROMISO': 'psicoevaluacion/prueba_likert.html',
    'OBEDIENCIA': 'psicoevaluacion/prueba_likert.html',
    'DESEABILIDAD': 'psicoevaluacion/prueba_likert.html',
    'SITUACIONAL': 'psicoevaluacion/prueba_situacional.html',
    'MATRICES': 'psicoevaluacion/prueba_matrices.html',
    'MEMORIA': 'psicoevaluacion/prueba_memoria.html',
    'FRASES': 'psicoevaluacion/prueba_frases.html',
    'ARBOL': 'psicoevaluacion/prueba_proyectiva.html',
    'PERSONA_LLUVIA': 'psicoevaluacion/prueba_proyectiva.html',
    'COLORES': 'psicoevaluacion/prueba_colores.html',
}


def _get_pruebas_activas():
    return list(Prueba.objects.filter(activa=True).order_by('orden'))


def _serializar_preguntas(preguntas, tipo):
    resultado = []
    for p in preguntas:
        item = {
            'id': p.id,
            'texto': p.texto,
            'orden': p.orden,
            'dimension': p.dimension,
            'es_inversa': p.es_inversa,
        }
        if tipo == 'MEMORIA':
            item['secuencia_correcta'] = p.secuencia_correcta
        if tipo in ('BIGFIVE', 'COMPROMISO', 'OBEDIENCIA', 'DESEABILIDAD',
                     'SITUACIONAL', 'MATRICES'):
            opciones = list(p.opciones.all().order_by('orden'))
            if tipo == 'MATRICES':
                random.shuffle(opciones)
            item['opciones'] = [
                {'id': o.id, 'texto': o.texto, 'valor': o.valor, 'orden': o.orden}
                for o in opciones
            ]
        resultado.append(item)
    return resultado


def _get_respuestas_existentes(evaluacion, prueba):
    tipo = prueba.tipo
    if tipo in ('BIGFIVE', 'COMPROMISO', 'OBEDIENCIA', 'DESEABILIDAD'):
        return list(evaluacion.respuestas_psicometricas.filter(
            pregunta__prueba=prueba
        ).values_list('pregunta_id', flat=True))
    elif tipo == 'SITUACIONAL':
        return list(evaluacion.respuestas_situacionales.filter(
            pregunta__prueba=prueba
        ).values_list('pregunta_id', flat=True))
    elif tipo == 'MATRICES':
        return list(evaluacion.respuestas_matrices.filter(
            pregunta__prueba=prueba
        ).values_list('pregunta_id', flat=True))
    elif tipo == 'MEMORIA':
        return list(evaluacion.respuestas_memoria.filter(
            pregunta__prueba=prueba
        ).values_list('pregunta_id', flat=True))
    elif tipo in ('ARBOL', 'PERSONA_LLUVIA'):
        return list(evaluacion.respuestas_proyectivas.filter(
            prueba=prueba
        ).values_list('pregunta_id', flat=True))
    elif tipo == 'FRASES':
        return list(evaluacion.respuestas_proyectivas.filter(
            prueba=prueba, tipo='TEXTO'
        ).values_list('pregunta_id', flat=True))
    elif tipo == 'COLORES':
        return list(evaluacion.respuestas_proyectivas.filter(
            prueba=prueba
        ).values_list('pregunta_id', flat=True))
    return []


def _calcular_progreso(evaluacion):
    pruebas = _get_pruebas_activas()
    total = len(pruebas)
    if total == 0:
        return {'porcentaje': 0, 'prueba_numero': 0, 'total_pruebas': 0}

    prueba_actual = evaluacion.prueba_actual
    prueba_numero = 1
    if prueba_actual:
        for i, p in enumerate(pruebas):
            if p.id == prueba_actual.id:
                prueba_numero = i + 1
                break

    porcentaje = int((prueba_numero - 1) / total * 100)
    return {
        'porcentaje': porcentaje,
        'prueba_numero': prueba_numero,
        'total_pruebas': total,
    }


def _get_siguiente_prueba(prueba_actual, pruebas):
    for i, p in enumerate(pruebas):
        if p.id == prueba_actual.id and i + 1 < len(pruebas):
            return pruebas[i + 1]
    return None


def _validar_api_request(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None, JsonResponse({'error': 'JSON invalido'}, status=400)

    token = data.get('evaluacion_token')
    if not token:
        return None, JsonResponse({'error': 'Token requerido'}, status=400)

    try:
        evaluacion = Evaluacion.objects.get(token=token)
    except Evaluacion.DoesNotExist:
        return None, JsonResponse({'error': 'Token invalido'}, status=404)

    if evaluacion.estado != 'EN_CURSO':
        return None, JsonResponse(
            {'error': 'Evaluacion no esta en curso'}, status=409)

    data['_evaluacion'] = evaluacion
    return data, None


# --- Candidato (publico, con token) ---

def inicio_evaluacion(request, token):
    evaluacion = _get_evaluacion_or_404(token)

    if evaluacion.estado == 'EXPIRADA':
        return render(request, 'psicoevaluacion/error_expirado.html', status=410)

    if evaluacion.estado in ('COMPLETADA', 'REVISADA'):
        return redirect('psicoevaluacion:finalizar_evaluacion', token=token)

    if evaluacion.estado == 'EN_CURSO':
        pruebas = _get_pruebas_activas()
        prueba_actual = evaluacion.prueba_actual
        if prueba_actual and prueba_actual.tipo in TEMPLATE_MAP:
            return redirect('psicoevaluacion:realizar_prueba',
                            token=token, tipo_prueba=prueba_actual.tipo.lower())
        elif pruebas:
            return redirect('psicoevaluacion:realizar_prueba',
                            token=token, tipo_prueba=pruebas[0].tipo.lower())

    pruebas = _get_pruebas_activas()
    duracion_map = {
        'BIGFIVE': '15-20 min',
        'COMPROMISO': '8-10 min',
        'OBEDIENCIA': '5-8 min',
        'DESEABILIDAD': '3-5 min',
        'SITUACIONAL': '10-15 min',
        'MATRICES': '20 min',
        'MEMORIA': '10-15 min',
        'FRASES': '10-15 min',
        'ARBOL': '10-15 min',
        'PERSONA_LLUVIA': '10-15 min',
        'COLORES': '5 min',
    }
    pruebas_info = []
    for p in pruebas:
        pruebas_info.append({
            'nombre': p.nombre,
            'duracion': duracion_map.get(p.tipo, '10 min'),
        })

    return render(request, 'psicoevaluacion/inicio_candidato.html', {
        'evaluacion': evaluacion,
        'pruebas_info': pruebas_info,
    })


def verificar_candidato(request, token):
    evaluacion = _get_evaluacion_or_404(token)

    if evaluacion.estado == 'EXPIRADA':
        return render(request, 'psicoevaluacion/error_expirado.html', status=410)
    if evaluacion.estado in ('COMPLETADA', 'REVISADA'):
        return redirect('psicoevaluacion:finalizar_evaluacion', token=token)
    if evaluacion.estado == 'EN_CURSO':
        return redirect('psicoevaluacion:inicio_evaluacion', token=token)

    error = None
    if request.method == 'POST':
        cedula_ingresada = request.POST.get('cedula', '').strip()
        if cedula_ingresada == evaluacion.cedula:
            seleccionar_preguntas_evaluacion(evaluacion)
            evaluacion.estado = 'EN_CURSO'
            evaluacion.fecha_inicio = timezone.now()
            evaluacion.ip_acceso = _get_client_ip(request)
            evaluacion.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            pruebas = _get_pruebas_activas()
            if pruebas:
                evaluacion.prueba_actual = pruebas[0]
            evaluacion.save()
            if pruebas:
                return redirect('psicoevaluacion:realizar_prueba',
                                token=token,
                                tipo_prueba=pruebas[0].tipo.lower())
            return redirect('psicoevaluacion:finalizar_evaluacion', token=token)
        else:
            error = 'El numero de cedula no coincide con nuestros registros.'

    return render(request, 'psicoevaluacion/verificar_candidato.html', {
        'evaluacion': evaluacion,
        'error': error,
    })


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def realizar_prueba(request, token, tipo_prueba):
    evaluacion = _get_evaluacion_or_404(token)

    if evaluacion.estado != 'EN_CURSO':
        return redirect('psicoevaluacion:inicio_evaluacion', token=token)

    tipo_upper = tipo_prueba.upper()
    template = TEMPLATE_MAP.get(tipo_upper)
    if not template:
        raise Http404('Tipo de prueba no encontrado')

    try:
        prueba = Prueba.objects.get(tipo=tipo_upper, activa=True)
    except Prueba.DoesNotExist:
        raise Http404('Prueba no encontrada')

    # Get questions: intersect prueba.preguntas with evaluacion.preguntas_seleccionadas
    preguntas = prueba.preguntas.all().order_by('orden')
    if evaluacion.preguntas_seleccionadas:
        preguntas = preguntas.filter(id__in=evaluacion.preguntas_seleccionadas)
    preguntas = preguntas.prefetch_related('opciones')
    preguntas_list = list(preguntas)

    # Shuffle options for matrices to prevent position bias
    if tipo_upper == 'MATRICES':
        for p in preguntas_list:
            shuffled = list(p.opciones.all())
            random.shuffle(shuffled)
            p.shuffled_opciones = shuffled

    # Serialize for JS
    preguntas_json = _serializar_preguntas(preguntas_list, tipo_upper)

    # Existing answers (for resume)
    respondidas = _get_respuestas_existentes(evaluacion, prueba)

    # Update prueba_actual
    if evaluacion.prueba_actual_id != prueba.id:
        evaluacion.prueba_actual = prueba
        evaluacion.save(update_fields=['prueba_actual'])

    # Calculate progress and next test
    pruebas = _get_pruebas_activas()
    progreso = _calcular_progreso(evaluacion)
    siguiente = _get_siguiente_prueba(prueba, pruebas)
    if siguiente:
        siguiente_url = reverse('psicoevaluacion:realizar_prueba',
                                kwargs={'token': token,
                                        'tipo_prueba': siguiente.tipo.lower()})
    else:
        siguiente_url = reverse('psicoevaluacion:finalizar_evaluacion',
                                kwargs={'token': token})

    context = {
        'evaluacion': evaluacion,
        'prueba': prueba,
        'preguntas': preguntas_list,
        'preguntas_json': json.dumps(preguntas_json),
        'respondidas_json': json.dumps(respondidas),
        'progreso': progreso,
        'siguiente_url': siguiente_url,
        'token': token,
    }

    return render(request, template, context)


def finalizar_evaluacion(request, token):
    evaluacion = _get_evaluacion_or_404(token)

    if evaluacion.estado == 'EN_CURSO':
        evaluacion.estado = 'COMPLETADA'
        evaluacion.fecha_finalizacion = timezone.now()
        evaluacion.save(update_fields=['estado', 'fecha_finalizacion'])
        try:
            calcular_resultado_final(evaluacion)
        except Exception:
            pass

    return render(request, 'psicoevaluacion/finalizacion.html', {
        'evaluacion': evaluacion,
    })


# --- API para guardar respuestas (AJAX) ---

@require_POST
def api_guardar_psicometrica(request):
    data, error = _validar_api_request(request)
    if error:
        return error

    evaluacion = data['_evaluacion']
    pregunta_id = data.get('pregunta_id')
    valor = data.get('valor')
    opcion_id = data.get('opcion_id')
    tiempo = data.get('tiempo_respuesta_seg')

    if not pregunta_id or valor is None:
        return JsonResponse({'error': 'pregunta_id y valor requeridos'}, status=400)

    try:
        pregunta = Pregunta.objects.get(id=pregunta_id)
    except Pregunta.DoesNotExist:
        return JsonResponse({'error': 'Pregunta no encontrada'}, status=404)

    opcion = None
    if opcion_id:
        try:
            opcion = Opcion.objects.get(id=opcion_id)
        except Opcion.DoesNotExist:
            pass

    _, created = RespuestaPsicometrica.objects.update_or_create(
        evaluacion=evaluacion,
        pregunta=pregunta,
        defaults={
            'valor': valor,
            'opcion_seleccionada': opcion,
            'tiempo_respuesta_seg': tiempo,
        }
    )

    return JsonResponse({
        'status': 'ok',
        'pregunta_id': pregunta_id,
        'created': created,
    })


@require_POST
def api_guardar_situacional(request):
    data, error = _validar_api_request(request)
    if error:
        return error

    evaluacion = data['_evaluacion']
    pregunta_id = data.get('pregunta_id')
    opcion_id = data.get('opcion_id')
    valor = data.get('valor')
    justificacion = data.get('justificacion', '')
    tiempo = data.get('tiempo_respuesta_seg')

    if not pregunta_id or valor is None:
        return JsonResponse({'error': 'pregunta_id y valor requeridos'}, status=400)

    try:
        pregunta = Pregunta.objects.get(id=pregunta_id)
    except Pregunta.DoesNotExist:
        return JsonResponse({'error': 'Pregunta no encontrada'}, status=404)

    opcion = None
    if opcion_id:
        try:
            opcion = Opcion.objects.get(id=opcion_id)
        except Opcion.DoesNotExist:
            pass

    _, created = RespuestaSituacional.objects.update_or_create(
        evaluacion=evaluacion,
        pregunta=pregunta,
        defaults={
            'opcion_seleccionada': opcion,
            'valor': valor,
            'justificacion': justificacion,
            'tiempo_respuesta_seg': tiempo,
        }
    )

    return JsonResponse({
        'status': 'ok',
        'pregunta_id': pregunta_id,
        'created': created,
    })


@require_POST
def api_guardar_matriz(request):
    data, error = _validar_api_request(request)
    if error:
        return error

    evaluacion = data['_evaluacion']
    pregunta_id = data.get('pregunta_id')
    opcion_id = data.get('opcion_id')
    tiempo = data.get('tiempo_respuesta_seg')

    if not pregunta_id or not opcion_id:
        return JsonResponse({'error': 'pregunta_id y opcion_id requeridos'}, status=400)

    try:
        pregunta = Pregunta.objects.get(id=pregunta_id)
    except Pregunta.DoesNotExist:
        return JsonResponse({'error': 'Pregunta no encontrada'}, status=404)

    try:
        opcion = Opcion.objects.get(id=opcion_id)
    except Opcion.DoesNotExist:
        return JsonResponse({'error': 'Opcion no encontrada'}, status=404)

    es_correcta = opcion.valor == 1

    _, created = RespuestaMatriz.objects.update_or_create(
        evaluacion=evaluacion,
        pregunta=pregunta,
        defaults={
            'opcion_seleccionada': opcion,
            'es_correcta': es_correcta,
            'tiempo_respuesta_seg': tiempo,
        }
    )

    return JsonResponse({
        'status': 'ok',
        'pregunta_id': pregunta_id,
        'created': created,
    })


@require_POST
def api_guardar_memoria(request):
    data, error = _validar_api_request(request)
    if error:
        return error

    evaluacion = data['_evaluacion']
    pregunta_id = data.get('pregunta_id')
    secuencia_respondida = data.get('secuencia_respondida', [])
    tiempo = data.get('tiempo_respuesta_seg')

    if not pregunta_id:
        return JsonResponse({'error': 'pregunta_id requerido'}, status=400)

    try:
        pregunta = Pregunta.objects.get(id=pregunta_id)
    except Pregunta.DoesNotExist:
        return JsonResponse({'error': 'Pregunta no encontrada'}, status=404)

    secuencia_correcta = pregunta.secuencia_correcta or []
    es_correcta = secuencia_respondida == secuencia_correcta

    _, created = RespuestaMemoria.objects.update_or_create(
        evaluacion=evaluacion,
        pregunta=pregunta,
        defaults={
            'secuencia_presentada': secuencia_correcta,
            'secuencia_respondida': secuencia_respondida,
            'es_correcta': es_correcta,
            'longitud_secuencia': len(secuencia_correcta),
            'tiempo_respuesta_seg': tiempo,
        }
    )

    return JsonResponse({
        'status': 'ok',
        'pregunta_id': pregunta_id,
        'es_correcta': es_correcta,
        'created': created,
    })


@require_POST
def api_guardar_proyectiva(request):
    data, error = _validar_api_request(request)
    if error:
        return error

    evaluacion = data['_evaluacion']
    pregunta_id = data.get('pregunta_id')
    prueba_id = data.get('prueba_id')
    tipo = data.get('tipo', 'TEXTO')
    tiempo = data.get('tiempo_total_seg')

    if not prueba_id:
        return JsonResponse({'error': 'prueba_id requerido'}, status=400)

    try:
        prueba = Prueba.objects.get(id=prueba_id)
    except Prueba.DoesNotExist:
        return JsonResponse({'error': 'Prueba no encontrada'}, status=404)

    pregunta = None
    if pregunta_id:
        try:
            pregunta = Pregunta.objects.get(id=pregunta_id)
        except Pregunta.DoesNotExist:
            pass

    defaults = {
        'tipo': tipo,
        'tiempo_total_seg': tiempo,
    }

    if tipo == 'DIBUJO':
        defaults['imagen_canvas'] = data.get('imagen_canvas', '')
        defaults['datos_trazo'] = data.get('datos_trazo')
    else:
        defaults['texto_respuesta'] = data.get('texto_respuesta', '')

    lookup = {
        'evaluacion': evaluacion,
        'prueba': prueba,
        'pregunta': pregunta,
    }

    _, created = RespuestaProyectiva.objects.update_or_create(
        **lookup, defaults=defaults
    )

    return JsonResponse({
        'status': 'ok',
        'pregunta_id': pregunta_id,
        'created': created,
    })


# --- Panel del evaluador (requiere login) - Stubs ---

@login_required
def dashboard_evaluador(request):
    evaluaciones = Evaluacion.objects.select_related(
        'perfil_objetivo'
    ).order_by('-fecha_creacion')
    return render(request, 'psicoevaluacion/admin/dashboard.html', {
        'evaluaciones': evaluaciones,
    })


@login_required
def crear_evaluacion(request):
    return render(request, 'psicoevaluacion/admin/crear_evaluacion.html')


@login_required
def detalle_evaluacion(request, pk):
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    resultado = getattr(evaluacion, 'resultado', None)
    tiene_proyectivas = evaluacion.respuestas_proyectivas.exists()
    proyectivas_pendientes = evaluacion.respuestas_proyectivas.filter(revisado=False).exists()
    return render(request, 'psicoevaluacion/admin/detalle_candidato.html', {
        'evaluacion': evaluacion,
        'resultado': resultado,
        'tiene_proyectivas': tiene_proyectivas,
        'proyectivas_pendientes': proyectivas_pendientes,
    })


@login_required
def revisar_proyectivas(request, pk):
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    proyectivas = evaluacion.respuestas_proyectivas.select_related(
        'prueba', 'pregunta'
    ).all()

    dibujos = [r for r in proyectivas if r.tipo == 'DIBUJO']
    frases = [r for r in proyectivas if r.tipo == 'TEXTO' and r.prueba.tipo == 'FRASES']
    colores = [r for r in proyectivas if r.prueba.tipo == 'COLORES']

    # Group frases by dimension
    frases_agrupadas = {}
    for r in frases:
        dim = r.pregunta.get_dimension_display() if r.pregunta else "General"
        frases_agrupadas.setdefault(dim, []).append(r)

    resultado = getattr(evaluacion, 'resultado', None)

    from .models import ConfiguracionIA
    ia_configurada = ConfiguracionIA.load().is_configured()

    return render(request, 'psicoevaluacion/admin/revisar_proyectivas.html', {
        'evaluacion': evaluacion,
        'dibujos': dibujos,
        'frases_agrupadas': frases_agrupadas,
        'colores': colores,
        'resultado': resultado,
        'ia_configurada': ia_configurada,
    })


@login_required
def descargar_proyectivas(request, pk):
    """Descarga ZIP con todos los datos proyectivos de la evaluación."""
    import base64

    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    proyectivas = evaluacion.respuestas_proyectivas.select_related(
        'prueba', 'pregunta'
    ).all()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        metadata = {
            'evaluacion_id': evaluacion.pk,
            'candidato': evaluacion.nombres,
            'cedula': evaluacion.cedula,
            'fecha': str(evaluacion.fecha_creacion),
        }
        zf.writestr('metadata.json', json.dumps(metadata, ensure_ascii=False, indent=2))

        for resp in proyectivas:
            tipo_prueba = resp.prueba.tipo
            folder = tipo_prueba

            if resp.tipo == 'DIBUJO' and resp.imagen_canvas:
                img_data = resp.imagen_canvas
                # Strip data URI prefix
                if img_data.startswith("data:"):
                    _, img_data = img_data.split(",", 1)
                try:
                    img_bytes = base64.b64decode(img_data)
                    zf.writestr(f'{folder}/dibujo.png', img_bytes)
                except Exception:
                    zf.writestr(f'{folder}/dibujo_base64.txt', resp.imagen_canvas)

                if resp.datos_trazo:
                    zf.writestr(
                        f'{folder}/datos_trazo.json',
                        json.dumps(resp.datos_trazo, ensure_ascii=False, indent=2)
                    )

            elif resp.tipo == 'TEXTO':
                pregunta_txt = resp.pregunta.texto if resp.pregunta else "sin_pregunta"
                idx = resp.pregunta.orden if resp.pregunta else resp.pk
                entry = {
                    'pregunta': pregunta_txt,
                    'respuesta': resp.texto_respuesta,
                    'dimension': resp.pregunta.dimension if resp.pregunta else '',
                }
                zf.writestr(
                    f'{folder}/respuesta_{idx}.json',
                    json.dumps(entry, ensure_ascii=False, indent=2)
                )

            elif tipo_prueba == 'COLORES':
                data = {
                    'datos_trazo': resp.datos_trazo,
                    'texto': resp.texto_respuesta,
                }
                zf.writestr(
                    f'{folder}/datos.json',
                    json.dumps(data, ensure_ascii=False, indent=2)
                )

    buf.seek(0)
    filename = f"proyectivas_{evaluacion.cedula}_{evaluacion.pk}.zip"
    response = HttpResponse(buf.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def calificar_con_ia(request, pk):
    """POST: Llama IA para calificar proyectivas, retorna sugerencias JSON."""
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    try:
        from .ai_grading import grade_all_projectives
        resultados = grade_all_projectives(evaluacion)
    except ImportError as e:
        return JsonResponse(
            {'error': f'Dependencia faltante: {e}. Ejecute: pip install httpx'},
            status=500)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.exception("Error en calificación IA para evaluación %s", pk)
        return JsonResponse({'error': f'Error inesperado: {e}'}, status=500)

    return JsonResponse({'resultados': resultados})


@login_required
@require_POST
def aplicar_calificacion_ia(request, pk):
    """POST: Guarda scores en ResultadoFinal, marca proyectivas como revisadas, recalcula veredicto."""
    evaluacion = get_object_or_404(Evaluacion, pk=pk)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    resultado, _ = ResultadoFinal.objects.get_or_create(evaluacion=evaluacion)

    # Apply scores
    if data.get('puntaje_arbol') is not None:
        resultado.puntaje_arbol = float(data['puntaje_arbol'])
    if data.get('puntaje_persona_lluvia') is not None:
        resultado.puntaje_persona_lluvia = float(data['puntaje_persona_lluvia'])
    if data.get('puntaje_frases') is not None:
        resultado.puntaje_frases = float(data['puntaje_frases'])
    if data.get('puntaje_colores') is not None:
        puntaje_colores = data['puntaje_colores']
        if isinstance(puntaje_colores, dict):
            resultado.puntaje_colores = puntaje_colores
        else:
            resultado.puntaje_colores = {
                'puntuacion': float(puntaje_colores),
                'interpretacion': data.get('interpretacion_colores', ''),
            }

    # Store interpretations in observaciones
    interpretaciones = []
    for key in ('interpretacion_arbol', 'interpretacion_persona_lluvia',
                'interpretacion_frases', 'interpretacion_colores'):
        if data.get(key):
            interpretaciones.append(f"**{key.replace('interpretacion_', '').title()}**: {data[key]}")
    if interpretaciones:
        existing = resultado.observaciones or ''
        separator = '\n\n---\n\n' if existing else ''
        resultado.observaciones = existing + separator + '\n'.join(interpretaciones)

    resultado.save()

    # Mark projective responses as reviewed
    evaluacion.respuestas_proyectivas.update(
        revisado=True,
        fecha_revision=timezone.now(),
    )

    # Recalculate verdict
    from .scoring import determinar_veredicto
    from .models import PerfilObjetivo
    perfil = evaluacion.perfil_objetivo or PerfilObjetivo.objects.filter(activo=True).first()
    if perfil:
        resultado.veredicto_automatico = determinar_veredicto(resultado, perfil)
        resultado.save(update_fields=['veredicto_automatico'])

    return JsonResponse({
        'status': 'ok',
        'veredicto_automatico': resultado.veredicto_automatico,
        'puntaje_arbol': resultado.puntaje_arbol,
        'puntaje_persona_lluvia': resultado.puntaje_persona_lluvia,
        'puntaje_frases': resultado.puntaje_frases,
        'puntaje_colores': resultado.puntaje_colores,
    })


@login_required
def calcular_resultados(request, pk):
    return JsonResponse({'status': 'not_implemented'}, status=501)


@login_required
def generar_reporte(request, pk):
    evaluacion = get_object_or_404(Evaluacion, pk=pk)
    resultado = getattr(evaluacion, 'resultado', None)

    try:
        from .report_pdf import generar_informe_pdf
        pdf_bytes = generar_informe_pdf(evaluacion, resultado)
    except ImportError as e:
        return JsonResponse(
            {'error': f'Dependencia faltante: {e}. Ejecute: pip install reportlab'},
            status=500)
    except Exception as e:
        logger.exception("Error generando reporte PDF para evaluación %s", pk)
        return JsonResponse({'error': f'Error generando PDF: {e}'}, status=500)

    filename = f"informe_{evaluacion.cedula}_{evaluacion.pk}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def asignar_veredicto(request, pk):
    return JsonResponse({'status': 'not_implemented'}, status=501)


@login_required
def comparativo(request):
    return render(request, 'psicoevaluacion/admin/comparativo.html')
