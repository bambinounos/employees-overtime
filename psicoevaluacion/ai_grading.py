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

COLORES_PROMPT = """\
Eres un psicólogo experto en el Test de Colores de Lüscher.
Analiza la siguiente secuencia de preferencia de colores:

{colores_data}

Evalúa:
- Preferencias y rechazos significativos
- Estado emocional actual
- Necesidades y fuentes de estrés
- Compatibilidad con un perfil laboral

Responde EXCLUSIVAMENTE con un JSON válido (sin markdown, sin texto extra):
{{"puntuacion": <1-10>, "interpretacion": "<análisis breve en español, máximo 200 palabras>", "confianza": "<ALTA|MEDIA|BAJA>"}}
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

def grade_drawing(config, respuesta):
    """Analiza una imagen base64 de dibujo proyectivo (árbol / persona bajo la lluvia)."""
    tipo = respuesta.prueba.get_tipo_display()
    prompt = DRAWING_PROMPT.format(tipo_prueba=tipo)
    image_b64 = respuesta.imagen_canvas or ""
    if not image_b64:
        return {
            "puntuacion": 5,
            "interpretacion": "No se encontró imagen para analizar.",
            "confianza": "BAJA",
        }
    return _call_ai(config, prompt, image_b64=image_b64)


def grade_frases(config, respuestas_qs):
    """Analiza respuestas de frases incompletas agrupadas por dimensión."""
    agrupadas = {}
    for r in respuestas_qs:
        dim = r.pregunta.get_dimension_display() if r.pregunta else "General"
        agrupadas.setdefault(dim, []).append({
            "frase": r.pregunta.texto if r.pregunta else "",
            "respuesta": r.texto_respuesta,
        })

    if not agrupadas:
        return {
            "puntuacion": 5,
            "interpretacion": "No se encontraron frases para analizar.",
            "confianza": "BAJA",
        }

    frases_texto = ""
    for dim, items in agrupadas.items():
        frases_texto += f"\n### {dim}\n"
        for item in items:
            frases_texto += f'- "{item["frase"]}" → "{item["respuesta"]}"\n'

    prompt = FRASES_PROMPT.format(frases_texto=frases_texto)
    return _call_ai(config, prompt)


def grade_colores(config, respuesta):
    """Interpreta ranking de colores Lüscher."""
    datos = respuesta.datos_trazo or {}
    texto = respuesta.texto_respuesta or ""
    colores_data = json.dumps(datos, ensure_ascii=False) if datos else texto

    if not colores_data:
        return {
            "puntuacion": 5,
            "interpretacion": "No se encontraron datos de colores para analizar.",
            "confianza": "BAJA",
        }

    prompt = COLORES_PROMPT.format(colores_data=colores_data)
    return _call_ai(config, prompt)


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
