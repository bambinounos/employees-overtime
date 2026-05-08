"""
Servicio de calificación de pruebas proyectivas mediante IA.

Soporta Anthropic (Claude) y Google (Gemini) via llamadas HTTP directas con httpx.
"""
import json
import logging
import base64

import httpx

from .models import ConfiguracionIA, RespuestaProyectiva

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
GOOGLE_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

TIMEOUT = 60.0

# ────────────────────────────────────────────────
# Prompts
# ────────────────────────────────────────────────

DRAWING_PROMPT = """\
Eres un psicólogo experto en pruebas proyectivas gráficas.
Analiza el siguiente dibujo de la prueba "{tipo_prueba}".

Evalúa los siguientes aspectos:
- Tamaño y ubicación en la hoja
- Presión y calidad del trazo
- Detalles y elementos incluidos
- Indicadores emocionales y de personalidad
- Signos de estrés, ansiedad o estabilidad

Responde EXCLUSIVAMENTE con un JSON válido (sin markdown, sin texto extra):
{{"puntuacion": <1-10>, "interpretacion": "<análisis breve en español, máximo 200 palabras>", "confianza": "<ALTA|MEDIA|BAJA>"}}
"""

# Rúbricas detalladas (nombre, puntaje_max)
ARBOL_INDICADORES = [
    ("Tamaño", 2),
    ("Ubicación", 2),
    ("Tronco", 2),
    ("Copa / Follaje", 2),
    ("Ramas", 2),
    ("Raíces", 2),
    ("Frutos / Flores / Hojas", 2),
    ("Calidad del trazo", 2),
    ("Detalles adicionales", 2),
    ("Proporción general", 2),
]
PERSONA_LLUVIA_INDICADORES = [
    ("Persona completa", 2),
    ("Tamaño de la persona", 2),
    ("Ubicación", 2),
    ("Postura y orientación", 2),
    ("Expresión facial", 2),
    ("Vestimenta", 2),
    ("Paraguas / Protección", 4),
    ("Lluvia representada", 2),
    ("Suelo / Línea base", 2),
    ("Detalles del entorno", 2),
]
COLORES_INDICADORES = [
    ("Consistencia entre rondas", 5),
    ("Posición de Azul", 5),
    ("Posición de Verde", 5),
    ("Posición de Rojo", 5),
    ("Posición de Amarillo", 5),
    ("Acromáticos en últimas posiciones", 5),
    ("Acromáticos en primeras posiciones (índice ansiedad)", 5),
    ("Cromáticos en primeras posiciones", 5),
]


def _format_rubrica(indicadores):
    """Formatea una lista [(nombre, max), ...] como bullets para el prompt."""
    return "\n".join(f"- {nombre} (0-{max_pts})" for nombre, max_pts in indicadores)


DRAWING_DETAIL_PROMPT = """\
Eres un psicólogo experto en pruebas proyectivas gráficas.
Analiza el dibujo de la prueba "{tipo_prueba}" calificando cada uno de los siguientes
indicadores de la rúbrica oficial. Para cada indicador asigna un puntaje entre 0
y su máximo, y agrega una observación breve (máximo 80 caracteres).

RÚBRICA:
{rubrica}

REGLAS:
- Respeta exactamente los nombres de la rúbrica.
- "puntuacion" final (1-10) debe corresponder a normalizar (suma_obtenida / suma_max) * 10.
- Si un indicador está ausente del dibujo, asigna 0 puntos.

Responde EXCLUSIVAMENTE con un JSON válido (sin markdown, sin texto extra):
{{
  "puntuacion": <1-10>,
  "interpretacion": "<análisis breve en español, máximo 200 palabras>",
  "confianza": "<ALTA|MEDIA|BAJA>",
  "indicadores": [
    {{"nombre": "<nombre exacto>", "puntaje": <int>, "max": <int>, "observacion": "<breve>"}},
    ...
  ]
}}
"""

FRASES_PROMPT = """\
Eres un psicólogo experto en la prueba de Frases Incompletas de Sacks.
Analiza las siguientes respuestas agrupadas por dimensión.

{frases_texto}

Evalúa:
- Actitud general hacia el trabajo, autoridad y compromiso
- Indicadores de conflicto o adaptación
- Coherencia y elaboración de las respuestas

Responde EXCLUSIVAMENTE con un JSON válido (sin markdown, sin texto extra):
{{"puntuacion": <1-10>, "interpretacion": "<análisis breve en español, máximo 200 palabras>", "confianza": "<ALTA|MEDIA|BAJA>"}}
"""

FRASES_DIM_PROMPT = """\
Eres un psicólogo experto en la prueba de Frases Incompletas de Sacks.
Analiza las siguientes respuestas correspondientes a la dimensión "{dim_nombre}".

{frases_texto}

Evalúa específicamente esta dimensión:
- Coherencia y profundidad de las respuestas
- Indicadores favorables o desfavorables propios de la dimensión
- Posibles signos de conflicto o adaptación

Responde EXCLUSIVAMENTE con un JSON válido (sin markdown, sin texto extra):
{{"puntuacion": <1-10>, "interpretacion": "<análisis breve en español, máximo 150 palabras>", "confianza": "<ALTA|MEDIA|BAJA>"}}
"""

# Mapeo de código de dimensión a nombre legible
FRASES_DIM_NOMBRES = {
    'FR_TRAB': 'Actitud hacia el trabajo',
    'FR_AUTO': 'Relación con la autoridad',
    'FR_COMP': 'Compromiso organizacional',
}

COLORES_PROMPT = """\
Eres un psicólogo experto en el Test de Colores de Lüscher.
Analiza la siguiente secuencia de preferencia de colores:

{colores_data}

Evalúa cada uno de los siguientes indicadores de la rúbrica oficial.
Para cada indicador asigna un puntaje entre 0 y su máximo, y una observación breve.

RÚBRICA:
{rubrica}

NOTAS sobre los datos:
- Códigos de color: 0=Gris, 1=Azul, 2=Verde, 3=Rojo-Anaranjado, 4=Amarillo, 5=Violeta, 6=Marrón, 7=Negro
- Acromáticos: Gris (0), Negro (7), Marrón (6) — su presencia en cabecera puede indicar ansiedad
- Cromáticos primarios: Azul (1), Verde (2), Rojo (3), Amarillo (4)
- ronda1 y ronda2 son las dos pasadas; idealmente concuerdan

REGLAS:
- Respeta exactamente los nombres de la rúbrica.
- "puntuacion" final (1-10) debe corresponder a (suma_obtenida / suma_max) * 10.

Responde EXCLUSIVAMENTE con un JSON válido (sin markdown, sin texto extra):
{{
  "puntuacion": <1-10>,
  "interpretacion": "<análisis breve en español, máximo 200 palabras>",
  "confianza": "<ALTA|MEDIA|BAJA>",
  "indicadores": [
    {{"nombre": "<nombre exacto>", "puntaje": <int>, "max": <int>, "observacion": "<breve>"}},
    ...
  ]
}}
"""


# ────────────────────────────────────────────────
# HTTP helpers
# ────────────────────────────────────────────────

def _call_anthropic(config, prompt, image_b64=None):
    """Llama la API de Anthropic Messages."""
    content = []
    if image_b64:
        # Detect format from base64 header or default to png
        media_type = "image/png"
        data = image_b64
        if image_b64.startswith("data:"):
            # Strip data URI prefix: data:image/png;base64,xxxxx
            header, data = image_b64.split(",", 1)
            if "image/jpeg" in header:
                media_type = "image/jpeg"
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data,
            }
        })
    content.append({"type": "text", "text": prompt})

    payload = {
        "model": config.anthropic_model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": content}],
    }
    headers = {
        "x-api-key": config.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    resp = httpx.post(ANTHROPIC_API_URL, json=payload, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    text = data["content"][0]["text"]
    return _parse_json_response(text)


def _call_google(config, prompt, image_b64=None):
    """Llama la API de Google Gemini."""
    parts = []
    if image_b64:
        data = image_b64
        mime = "image/png"
        if image_b64.startswith("data:"):
            header, data = image_b64.split(",", 1)
            if "image/jpeg" in header:
                mime = "image/jpeg"
        parts.append({
            "inline_data": {
                "mime_type": mime,
                "data": data,
            }
        })
    parts.append({"text": prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
    }
    url = GOOGLE_API_URL.format(model=config.google_model)
    resp = httpx.post(
        url, json=payload,
        params={"key": config.google_api_key},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_json_response(text)


def _call_ai(config, prompt, image_b64=None):
    """Dispatcher: llama al proveedor activo."""
    if config.proveedor_activo == 'ANTHROPIC':
        return _call_anthropic(config, prompt, image_b64)
    return _call_google(config, prompt, image_b64)


def _parse_json_response(text):
    """Parsea respuesta JSON del modelo, tolerando markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        # Strip ```json ... ```
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("AI returned non-JSON: %s", text[:200])
        result = {
            "puntuacion": 5,
            "interpretacion": f"No se pudo parsear la respuesta de IA: {text[:200]}",
            "confianza": "BAJA",
        }
    # Validate bounds
    score = result.get("puntuacion", 5)
    result["puntuacion"] = max(1, min(10, int(score)))
    if result.get("confianza") not in ("ALTA", "MEDIA", "BAJA"):
        result["confianza"] = "BAJA"
    return result


# ────────────────────────────────────────────────
# Public grading functions
# ────────────────────────────────────────────────

def _normalizar_indicadores(raw, rubrica):
    """Valida y normaliza la lista de indicadores devuelta por la IA.

    Garantiza que cada item tenga nombre/puntaje/max/observacion y descarta los
    inválidos. Calcula totales. Devuelve un dict con la estructura esperada o
    None si no hay datos utilizables.
    """
    if not isinstance(raw, list) or not raw:
        return None

    rubrica_dict = {nombre: max_pts for nombre, max_pts in rubrica}
    indicadores_validos = []
    total_obtenido = 0
    total_max = 0

    for item in raw:
        if not isinstance(item, dict):
            continue
        nombre = item.get("nombre")
        puntaje = item.get("puntaje")
        max_pts = item.get("max")
        observacion = item.get("observacion", "")
        if nombre is None or puntaje is None or max_pts is None:
            continue
        try:
            puntaje_int = int(puntaje)
            max_int = int(max_pts)
        except (TypeError, ValueError):
            continue
        # Si la rúbrica define el max y la IA devolvió otro, preferir el oficial
        if nombre in rubrica_dict:
            max_int = rubrica_dict[nombre]
        # Acotar puntaje a [0, max]
        puntaje_int = max(0, min(puntaje_int, max_int))
        indicadores_validos.append({
            "nombre": str(nombre),
            "puntaje": puntaje_int,
            "max": max_int,
            "observacion": str(observacion)[:200],
        })
        total_obtenido += puntaje_int
        total_max += max_int

    if not indicadores_validos:
        return None

    puntaje_normalizado = (total_obtenido / total_max * 10) if total_max > 0 else 0

    return {
        "indicadores": indicadores_validos,
        "total_obtenido": total_obtenido,
        "total_max": total_max,
        "puntaje_normalizado": round(puntaje_normalizado, 1),
    }


def grade_drawing(config, respuesta):
    """Analiza una imagen base64 de dibujo proyectivo (árbol / persona bajo la lluvia).

    Devuelve dict con puntuacion, interpretacion, confianza y `detalle` (rúbrica).
    """
    tipo = respuesta.prueba.get_tipo_display()
    image_b64 = respuesta.imagen_canvas or ""
    if not image_b64:
        return {
            "puntuacion": 5,
            "interpretacion": "No se encontró imagen para analizar.",
            "confianza": "BAJA",
        }

    # Seleccionar rúbrica según tipo
    tipo_codigo = respuesta.prueba.tipo
    if tipo_codigo == 'ARBOL':
        rubrica = ARBOL_INDICADORES
    elif tipo_codigo == 'PERSONA_LLUVIA':
        rubrica = PERSONA_LLUVIA_INDICADORES
    else:
        # Fallback al prompt genérico
        prompt = DRAWING_PROMPT.format(tipo_prueba=tipo)
        return _call_ai(config, prompt, image_b64=image_b64)

    prompt = DRAWING_DETAIL_PROMPT.format(
        tipo_prueba=tipo, rubrica=_format_rubrica(rubrica))
    resultado = _call_ai(config, prompt, image_b64=image_b64)

    # Normalizar y persistir el detalle
    detalle = _normalizar_indicadores(resultado.get("indicadores"), rubrica)
    if detalle is not None:
        resultado["detalle"] = detalle
        # Si la IA dio un puntaje inconsistente con la rúbrica, alinearlo
        resultado["puntuacion"] = max(1, min(10, int(round(detalle["puntaje_normalizado"]))))
    # Limpiar el array crudo para no duplicarlo en la respuesta
    resultado.pop("indicadores", None)
    return resultado


def grade_frases(config, respuestas_qs):
    """Analiza respuestas de frases incompletas calificando cada dimensión por separado.

    Retorna un dict con:
        puntuacion: promedio general (1-10)
        interpretacion: texto consolidado
        confianza: peor confianza entre las dimensiones
        dimensiones: {FR_TRAB: {...}, FR_AUTO: {...}, FR_COMP: {...}}
    """
    # Agrupar por código de dimensión (no display name) para poder mapear luego
    agrupadas = {}
    for r in respuestas_qs:
        if not r.pregunta:
            continue
        dim_code = r.pregunta.dimension or 'GENERAL'
        agrupadas.setdefault(dim_code, []).append({
            "frase": r.pregunta.texto,
            "respuesta": r.texto_respuesta,
        })

    if not agrupadas:
        return {
            "puntuacion": 5,
            "interpretacion": "No se encontraron frases para analizar.",
            "confianza": "BAJA",
            "dimensiones": {},
        }

    # Calificar cada dimensión por separado
    resultados_dim = {}
    for dim_code, items in agrupadas.items():
        dim_nombre = FRASES_DIM_NOMBRES.get(dim_code, dim_code)
        frases_texto = ""
        for item in items:
            frases_texto += f'- "{item["frase"]}" → "{item["respuesta"]}"\n'

        prompt = FRASES_DIM_PROMPT.format(
            dim_nombre=dim_nombre, frases_texto=frases_texto)
        try:
            resultado = _call_ai(config, prompt)
        except Exception as e:
            logger.error("Error calificando dimension %s: %s", dim_code, e)
            resultado = {
                "puntuacion": 5,
                "interpretacion": f"Error al calificar {dim_nombre}: {e}",
                "confianza": "BAJA",
            }
        resultados_dim[dim_code] = resultado

    # Promedio general
    puntuaciones = [r['puntuacion'] for r in resultados_dim.values()]
    promedio = sum(puntuaciones) / len(puntuaciones) if puntuaciones else 5

    # Peor confianza
    confianzas_orden = {'ALTA': 3, 'MEDIA': 2, 'BAJA': 1}
    peor = min(
        (confianzas_orden.get(r.get('confianza', 'BAJA'), 1)
         for r in resultados_dim.values()),
        default=1,
    )
    confianza_global = next(
        (k for k, v in confianzas_orden.items() if v == peor), 'BAJA')

    # Interpretación consolidada
    partes = []
    for dim_code, r in resultados_dim.items():
        nombre = FRASES_DIM_NOMBRES.get(dim_code, dim_code)
        partes.append(f"**{nombre}** ({r['puntuacion']}/10): {r['interpretacion']}")
    interpretacion = "\n\n".join(partes)

    return {
        "puntuacion": round(promedio, 1),
        "interpretacion": interpretacion,
        "confianza": confianza_global,
        "dimensiones": resultados_dim,
    }


def grade_colores(config, respuesta):
    """Interpreta ranking de colores Lüscher con rúbrica detallada."""
    datos = respuesta.datos_trazo or {}
    texto = respuesta.texto_respuesta or ""
    colores_data = json.dumps(datos, ensure_ascii=False) if datos else texto

    if not colores_data:
        return {
            "puntuacion": 5,
            "interpretacion": "No se encontraron datos de colores para analizar.",
            "confianza": "BAJA",
        }

    prompt = COLORES_PROMPT.format(
        colores_data=colores_data,
        rubrica=_format_rubrica(COLORES_INDICADORES),
    )
    resultado = _call_ai(config, prompt)

    detalle = _normalizar_indicadores(resultado.get("indicadores"), COLORES_INDICADORES)
    if detalle is not None:
        resultado["detalle"] = detalle
        resultado["puntuacion"] = max(1, min(10, int(round(detalle["puntaje_normalizado"]))))
    resultado.pop("indicadores", None)
    return resultado


def grade_all_projectives(evaluacion):
    """
    Orquestador: califica todas las pruebas proyectivas de una evaluación.
    Retorna dict con resultados sin escribir en BD.

    Returns:
        {
            'arbol': {puntuacion, interpretacion, confianza} | None,
            'persona_lluvia': {...} | None,
            'frases': {...} | None,
            'colores': {...} | None,
        }
    """
    config = ConfiguracionIA.load()
    if not config.is_configured():
        raise ValueError(
            "La configuración de IA no está completa. "
            "Configure una API key en Admin > Configuración IA."
        )

    resultados = {
        'arbol': None,
        'persona_lluvia': None,
        'frases': None,
        'colores': None,
    }

    proyectivas = evaluacion.respuestas_proyectivas.select_related(
        'prueba', 'pregunta'
    ).all()

    for resp in proyectivas:
        tipo_prueba = resp.prueba.tipo
        try:
            if tipo_prueba == 'ARBOL' and resp.tipo == 'DIBUJO':
                resultados['arbol'] = grade_drawing(config, resp)
            elif tipo_prueba == 'PERSONA_LLUVIA' and resp.tipo == 'DIBUJO':
                resultados['persona_lluvia'] = grade_drawing(config, resp)
            elif tipo_prueba == 'COLORES':
                resultados['colores'] = grade_colores(config, resp)
        except Exception as e:
            logger.error("Error calificando %s: %s", tipo_prueba, e)
            resultados[tipo_prueba.lower()] = {
                "puntuacion": 5,
                "interpretacion": f"Error al calificar: {e}",
                "confianza": "BAJA",
            }

    # Frases: agrupar todas las respuestas de tipo TEXTO de prueba FRASES
    frases_qs = proyectivas.filter(prueba__tipo='FRASES', tipo='TEXTO')
    if frases_qs.exists():
        try:
            resultados['frases'] = grade_frases(config, frases_qs)
        except Exception as e:
            logger.error("Error calificando FRASES: %s", e)
            resultados['frases'] = {
                "puntuacion": 5,
                "interpretacion": f"Error al calificar frases: {e}",
                "confianza": "BAJA",
            }

    return resultados
