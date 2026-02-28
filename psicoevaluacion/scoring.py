from statistics import mean

from .models import ResultadoFinal, PerfilObjetivo, RespuestaPsicometrica, RespuestaAtencion


def calcular_bigfive(respuestas):
    """Calcula puntajes Big Five por dimensión con inversión de ítems."""
    dimensiones = {
        'BF_RESP': [], 'BF_AMAB': [], 'BF_NEUR': [],
        'BF_APER': [], 'BF_EXTR': []
    }
    for r in respuestas:
        dim = r.pregunta.dimension
        if dim not in dimensiones:
            continue
        valor = r.valor
        if r.pregunta.es_inversa:
            valor = 6 - valor  # Invertir escala 1-5
        dimensiones[dim].append(valor)

    return {
        'responsabilidad': mean(dimensiones['BF_RESP']) if dimensiones['BF_RESP'] else 0,
        'amabilidad': mean(dimensiones['BF_AMAB']) if dimensiones['BF_AMAB'] else 0,
        'neuroticismo': mean(dimensiones['BF_NEUR']) if dimensiones['BF_NEUR'] else 0,
        'apertura': mean(dimensiones['BF_APER']) if dimensiones['BF_APER'] else 0,
        'extroversion': mean(dimensiones['BF_EXTR']) if dimensiones['BF_EXTR'] else 0,
    }


def calcular_compromiso(respuestas):
    """Calcula compromiso organizacional por subdimensión (Allen & Meyer)."""
    dimensiones = {
        'CO_AFEC': [], 'CO_CONT': [], 'CO_NORM': []
    }
    for r in respuestas:
        dim = r.pregunta.dimension
        if dim not in dimensiones:
            continue
        valor = r.valor
        if r.pregunta.es_inversa:
            valor = 6 - valor
        dimensiones[dim].append(valor)

    afectivo = mean(dimensiones['CO_AFEC']) if dimensiones['CO_AFEC'] else 0
    continuidad = mean(dimensiones['CO_CONT']) if dimensiones['CO_CONT'] else 0
    normativo = mean(dimensiones['CO_NORM']) if dimensiones['CO_NORM'] else 0

    return {
        'afectivo': afectivo,
        'continuidad': continuidad,
        'normativo': normativo,
        'total': mean([afectivo, normativo]) if (afectivo or normativo) else 0,
    }


def calcular_obediencia(respuestas):
    """Calcula puntaje general de obediencia/conformidad."""
    valores = []
    for r in respuestas:
        valor = r.valor
        if r.pregunta.es_inversa:
            valor = 6 - valor
        valores.append(valor)
    return mean(valores) if valores else 0


def calcular_memoria(respuestas):
    """Calcula % de aciertos y max span en test de memoria."""
    if not respuestas:
        return {'porcentaje': 0, 'max_span': 0}

    total = len(respuestas)
    correctas = sum(1 for r in respuestas if r.es_correcta)
    max_span = 0
    for r in respuestas:
        if r.es_correcta:
            max_span = max(max_span, r.longitud_secuencia)

    return {
        'porcentaje': (correctas / total) * 100 if total > 0 else 0,
        'max_span': max_span,
    }


def calcular_matrices(respuestas):
    """Calcula % de aciertos ponderado por dificultad en matrices progresivas."""
    if not respuestas:
        return 0

    total_peso = 0
    aciertos_ponderados = 0
    for i, r in enumerate(respuestas):
        peso = 1 + (i * 0.1)  # Preguntas más difíciles pesan más
        total_peso += peso
        if r.es_correcta:
            aciertos_ponderados += peso

    return (aciertos_ponderados / total_peso) * 100 if total_peso > 0 else 0


def calcular_situacional(respuestas):
    """Calcula puntaje de prueba situacional por dimensión.

    Cada dimensión se promedia (escala 1-5), y el total se normaliza
    a porcentaje 0-100 para que sea comparable con los umbrales del sistema.
    Máximo teórico: 3 dimensiones × 5.0 = 15.0 → 100%.
    """
    MAX_SUM = 15.0  # 3 dimensiones × máximo 5.0 cada una

    dimensiones = {
        'SIT_RESP': [], 'SIT_OBED': [], 'SIT_LEAL': []
    }
    for r in respuestas:
        dim = r.pregunta.dimension
        if dim in dimensiones:
            dimensiones[dim].append(r.valor)

    resultado = {}
    for dim, valores in dimensiones.items():
        resultado[dim] = mean(valores) if valores else 0

    raw_total = sum(resultado.values())
    resultado['total'] = (raw_total / MAX_SUM) * 100 if MAX_SUM > 0 else 0
    return resultado


def calcular_deseabilidad_social(respuestas):
    """Calcula puntaje promedio en la escala de Deseabilidad Social."""
    valores = []
    for r in respuestas:
        valor = r.valor
        if r.pregunta.es_inversa:
            valor = 6 - valor
        valores.append(valor)
    return mean(valores) if valores else 0


def calcular_consistencia(evaluacion):
    """
    Compara respuestas de pares vinculados via par_consistencia.
    Retorna 0-100% de concordancia. Si no hay pares, retorna None.
    """
    respuestas = evaluacion.respuestas_psicometricas.select_related(
        'pregunta', 'pregunta__par_consistencia'
    ).all()

    # Build lookup: pregunta_id -> valor (already adjusted for inversion)
    valor_por_pregunta = {}
    for r in respuestas:
        valor = r.valor
        if r.pregunta.es_inversa:
            valor = 6 - valor
        valor_por_pregunta[r.pregunta_id] = valor

    # Find pairs where both members have responses
    pares_evaluados = []
    vistos = set()
    for r in respuestas:
        preg = r.pregunta
        if preg.par_consistencia_id and preg.id not in vistos:
            par_id = preg.par_consistencia_id
            if par_id in valor_por_pregunta and preg.id in valor_por_pregunta:
                val_a = valor_por_pregunta[preg.id]
                val_b = valor_por_pregunta[par_id]
                # Max possible difference on 1-5 scale is 4
                concordancia = 1 - (abs(val_a - val_b) / 4)
                pares_evaluados.append(concordancia)
                vistos.add(preg.id)
                vistos.add(par_id)

    if not pares_evaluados:
        return None

    return mean(pares_evaluados) * 100


def _score_comparacion(respuestas):
    """
    Score for document comparison using F1 (precision × recall balance).
    Each question stores correct_diffs in pregunta.secuencia_correcta (as JSON list)
    and candidate's found diffs in respuesta_json.
    Returns 0-100%.
    """
    if not respuestas:
        return 0

    total_precision = 0
    total_recall = 0
    count = 0

    for r in respuestas:
        correctas = set()
        encontradas = set()

        # Ground truth: stored in pregunta.secuencia_correcta as list of diff keys
        if r.pregunta and r.pregunta.secuencia_correcta:
            correctas = {str(x) for x in r.pregunta.secuencia_correcta}

        # Candidate answer
        if r.respuesta_json and isinstance(r.respuesta_json, list):
            encontradas = {str(x) for x in r.respuesta_json}

        if not correctas:
            continue

        true_positives = len(correctas & encontradas)
        precision = true_positives / len(encontradas) if encontradas else 0
        recall = true_positives / len(correctas) if correctas else 0

        total_precision += precision
        total_recall += recall
        count += 1

    if count == 0:
        return 0

    avg_precision = total_precision / count
    avg_recall = total_recall / count

    if avg_precision + avg_recall == 0:
        return 0

    f1 = 2 * (avg_precision * avg_recall) / (avg_precision + avg_recall)
    return f1 * 100


def _score_verificacion(respuestas):
    """
    Score for data verification: % of correctly identified inconsistencies.
    Returns 0-100%.
    """
    if not respuestas:
        return 0

    total = len(respuestas)
    puntaje_sum = sum(r.puntaje_parcial for r in respuestas)
    return (puntaje_sum / total) * 100


def _score_secuencias(respuestas):
    """
    Score for sequence error detection: % correct.
    Returns 0-100%.
    """
    if not respuestas:
        return 0

    total = len(respuestas)
    correctas = sum(1 for r in respuestas if r.es_correcta)
    return (correctas / total) * 100


def calcular_atencion_detalle(respuestas):
    """
    Calcula puntaje compuesto de Atención al Detalle.
    Pesos: Comparación 40%, Verificación 35%, Secuencias 25%.
    Returns dict with subsection scores and composite.
    """
    comparacion = [r for r in respuestas if r.subtipo == 'COMPARACION']
    verificacion = [r for r in respuestas if r.subtipo == 'VERIFICACION']
    secuencias = [r for r in respuestas if r.subtipo == 'SECUENCIA']

    score_comp = _score_comparacion(comparacion)
    score_veri = _score_verificacion(verificacion)
    score_secu = _score_secuencias(secuencias)

    # Weighted composite
    compuesto = score_comp * 0.40 + score_veri * 0.35 + score_secu * 0.25

    return {
        'comparacion': score_comp,
        'verificacion': score_veri,
        'secuencias': score_secu,
        'total': compuesto,
    }


def calcular_resultado_final(evaluacion):
    """Orquestador principal: calcula todos los puntajes y genera ResultadoFinal."""
    resultado, _ = ResultadoFinal.objects.get_or_create(evaluacion=evaluacion)

    # 0. Confiabilidad — Deseabilidad Social + Consistencia
    ds_respuestas = evaluacion.respuestas_psicometricas.filter(
        pregunta__prueba__tipo='DESEABILIDAD').select_related('pregunta')
    resultado.puntaje_deseabilidad_social = calcular_deseabilidad_social(ds_respuestas)

    resultado.indice_consistencia = calcular_consistencia(evaluacion)

    # Determinar confiabilidad: DS > 4.0 o consistencia < 60% → no confiable
    ds = resultado.puntaje_deseabilidad_social or 0
    consistencia = resultado.indice_consistencia
    confiable = True
    if ds > 4.0:
        confiable = False
    if consistencia is not None and consistencia < 60:
        confiable = False
    resultado.evaluacion_confiable = confiable

    # 1. Big Five
    bf = calcular_bigfive(evaluacion.respuestas_psicometricas.filter(
        pregunta__prueba__tipo='BIGFIVE').select_related('pregunta'))
    resultado.puntaje_responsabilidad = bf['responsabilidad']
    resultado.puntaje_amabilidad = bf['amabilidad']
    resultado.puntaje_neuroticismo = bf['neuroticismo']
    resultado.puntaje_apertura = bf['apertura']
    resultado.puntaje_extroversion = bf['extroversion']

    # 2. Compromiso Allen & Meyer
    co = calcular_compromiso(evaluacion.respuestas_psicometricas.filter(
        pregunta__prueba__tipo='COMPROMISO').select_related('pregunta'))
    resultado.puntaje_compromiso_afectivo = co['afectivo']
    resultado.puntaje_compromiso_continuidad = co['continuidad']
    resultado.puntaje_compromiso_normativo = co['normativo']
    resultado.puntaje_compromiso_total = co['total']

    # 3. Obediencia
    resultado.puntaje_obediencia = calcular_obediencia(
        evaluacion.respuestas_psicometricas.filter(
            pregunta__prueba__tipo='OBEDIENCIA').select_related('pregunta'))

    # 4. Memoria
    mem = calcular_memoria(list(evaluacion.respuestas_memoria.all()))
    resultado.puntaje_memoria = mem['porcentaje']
    resultado.max_secuencia_memoria = mem['max_span']

    # 5. Matrices
    resultado.puntaje_matrices = calcular_matrices(
        list(evaluacion.respuestas_matrices.all()))

    # 6. Situacional
    sit = calcular_situacional(
        evaluacion.respuestas_situacionales.select_related('pregunta').all())
    resultado.puntaje_situacional = sit.get('total', 0)

    # 6b. Atención al Detalle
    atencion_respuestas = list(
        evaluacion.respuestas_atencion.select_related('pregunta').all())
    if atencion_respuestas:
        aten = calcular_atencion_detalle(atencion_respuestas)
        resultado.puntaje_atencion_detalle = aten['total']
        resultado.puntaje_atencion_comparacion = aten['comparacion']
        resultado.puntaje_atencion_verificacion = aten['verificacion']
        resultado.puntaje_atencion_secuencias = aten['secuencias']

    # 7. Índices combinados
    resp = resultado.puntaje_responsabilidad or 0
    sit_total = resultado.puntaje_situacional or 0
    mem_pct = resultado.puntaje_memoria or 0
    comp_total = resultado.puntaje_compromiso_total or 0
    obed = resultado.puntaje_obediencia or 0
    aten_pct = resultado.puntaje_atencion_detalle or 0

    resultado.indice_responsabilidad_total = (
        resp * 0.40 +
        (sit_total / 20) * 0.25 +
        (mem_pct / 20) * 0.15 +
        (aten_pct / 20) * 0.20
    )

    resultado.indice_lealtad = (
        comp_total * 0.6 +
        resp * 0.2 +
        obed * 0.2
    )

    resultado.indice_obediencia_total = (
        obed * 0.6 +
        (sit_total / 20) * 0.4
    )

    # 8. Veredicto automático
    perfil = evaluacion.perfil_objetivo or PerfilObjetivo.objects.filter(activo=True).first()
    if perfil:
        resultado.veredicto_automatico = determinar_veredicto(resultado, perfil)
    else:
        resultado.veredicto_automatico = 'REVISION'

    resultado.save()
    return resultado


def determinar_veredicto(resultado, perfil):
    """
    Determina veredicto según el método configurado en el perfil.

    CONTEO_FALLOS (default):
        APTO: 0 fallos y sin proyectivas pendientes
        NO_APTO: 2+ fallos
        REVISION: 1 fallo, proyectivas pendientes, o evaluación no confiable

    ESTRICTO:
        APTO: 0 fallos y sin proyectivas pendientes
        NO_APTO: cualquier fallo
        (no existe REVISION por fallos, solo por confiabilidad o proyectivas pendientes)
    """
    # Si evaluación no es confiable, forzar REVISION
    if not resultado.evaluacion_confiable:
        return 'REVISION'

    fallos = 0

    if (resultado.puntaje_responsabilidad or 0) < perfil.min_responsabilidad:
        fallos += 1
    if (resultado.puntaje_compromiso_total or 0) < perfil.min_compromiso_organizacional:
        fallos += 1
    if (resultado.puntaje_obediencia or 0) < perfil.min_obediencia:
        fallos += 1
    if (resultado.puntaje_memoria or 0) < perfil.min_memoria:
        fallos += 1
    if (resultado.puntaje_matrices or 0) < perfil.min_matrices:
        fallos += 1
    if (resultado.puntaje_neuroticismo or 0) > perfil.max_neuroticismo:
        fallos += 1
    if resultado.puntaje_atencion_detalle is not None:
        if resultado.puntaje_atencion_detalle < perfil.min_atencion_detalle:
            fallos += 1

    # Verificar si hay proyectivas sin revisar
    proyectivas_pendientes = resultado.evaluacion.respuestas_proyectivas.filter(
        revisado=False).exists()

    metodo = getattr(perfil, 'metodo_veredicto', 'CONTEO_FALLOS')

    if metodo == 'ESTRICTO':
        if fallos > 0:
            return 'NO_APTO'
        if proyectivas_pendientes:
            return 'REVISION'
        return 'APTO'

    # CONTEO_FALLOS (default)
    if fallos == 0 and not proyectivas_pendientes:
        return 'APTO'
    elif fallos >= 2:
        return 'NO_APTO'
    else:
        return 'REVISION'
