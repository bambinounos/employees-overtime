from unittest.mock import patch, MagicMock
from django.test import TestCase

from psicoevaluacion.models import (
    ConfiguracionIA, Evaluacion, Prueba, Pregunta,
    RespuestaProyectiva, ResultadoFinal,
)
from psicoevaluacion.ai_grading import (
    grade_drawing, grade_frases, grade_colores,
    grade_all_projectives, _parse_json_response,
)


class ParseJsonResponseTest(TestCase):

    def test_valid_json(self):
        text = '{"puntuacion": 8, "interpretacion": "Buen dibujo", "confianza": "ALTA"}'
        result = _parse_json_response(text)
        self.assertEqual(result['puntuacion'], 8)
        self.assertEqual(result['confianza'], 'ALTA')

    def test_json_in_markdown_block(self):
        text = '```json\n{"puntuacion": 7, "interpretacion": "Ok", "confianza": "MEDIA"}\n```'
        result = _parse_json_response(text)
        self.assertEqual(result['puntuacion'], 7)
        self.assertEqual(result['confianza'], 'MEDIA')

    def test_invalid_json_returns_default(self):
        text = 'This is not JSON at all'
        result = _parse_json_response(text)
        self.assertEqual(result['puntuacion'], 5)
        self.assertEqual(result['confianza'], 'BAJA')

    def test_puntuacion_clamped(self):
        text = '{"puntuacion": 15, "interpretacion": "x", "confianza": "ALTA"}'
        result = _parse_json_response(text)
        self.assertEqual(result['puntuacion'], 10)

    def test_puntuacion_clamped_low(self):
        text = '{"puntuacion": -2, "interpretacion": "x", "confianza": "ALTA"}'
        result = _parse_json_response(text)
        self.assertEqual(result['puntuacion'], 1)

    def test_invalid_confianza_defaults_baja(self):
        text = '{"puntuacion": 6, "interpretacion": "x", "confianza": "UNKNOWN"}'
        result = _parse_json_response(text)
        self.assertEqual(result['confianza'], 'BAJA')

    def test_json_with_prose_around_it(self):
        # El modelo agrega preámbulo/postámbulo pese a pedir solo JSON
        text = ('Claro, aquí está el análisis solicitado:\n\n'
                '{"puntuacion": 7, "interpretacion": "ok", "confianza": "ALTA"}\n\n'
                'Espero que sea útil.')
        result = _parse_json_response(text)
        self.assertEqual(result['puntuacion'], 7)
        self.assertEqual(result['confianza'], 'ALTA')

    def test_puntuacion_float_string(self):
        text = '{"puntuacion": "7.5", "interpretacion": "x", "confianza": "ALTA"}'
        result = _parse_json_response(text)
        self.assertEqual(result['puntuacion'], 8)

    def test_dimensiones_wrapper_preserved(self):
        text = ('{"dimensiones": {"FR_TRAB": {"puntuacion": 8, '
                '"interpretacion": "ok", "confianza": "ALTA"}}}')
        result = _parse_json_response(text)
        self.assertIn('dimensiones', result)
        self.assertEqual(result['dimensiones']['FR_TRAB']['puntuacion'], 8)


class GradeDrawingTest(TestCase):

    def test_no_image_returns_default(self):
        config = MagicMock()
        resp = MagicMock()
        resp.imagen_canvas = ''
        resp.prueba.get_tipo_display.return_value = 'Test del Arbol'
        result = grade_drawing(config, resp)
        self.assertEqual(result['puntuacion'], 5)
        self.assertEqual(result['confianza'], 'BAJA')

    @patch('psicoevaluacion.ai_grading._call_ai')
    def test_calls_ai_with_image(self, mock_call):
        mock_call.return_value = {
            'puntuacion': 8, 'interpretacion': 'Buen dibujo', 'confianza': 'ALTA'
        }
        config = MagicMock()
        resp = MagicMock()
        resp.imagen_canvas = 'data:image/png;base64,abc123'
        resp.prueba.get_tipo_display.return_value = 'Test del Arbol'

        result = grade_drawing(config, resp)
        self.assertEqual(result['puntuacion'], 8)
        mock_call.assert_called_once()


class GradeFrasesTest(TestCase):

    def test_no_frases_returns_default(self):
        config = MagicMock()
        result = grade_frases(config, [])
        self.assertEqual(result['puntuacion'], 5)
        self.assertEqual(result['confianza'], 'BAJA')

    @patch('psicoevaluacion.ai_grading._call_ai')
    def test_calls_ai_once_with_grouped_frases(self, mock_call):
        # Nuevo contrato: una sola llamada que devuelve scores por dimensión
        mock_call.return_value = {
            'dimensiones': {
                'FR_TRAB': {
                    'puntuacion': 7,
                    'interpretacion': 'Buenas frases',
                    'confianza': 'MEDIA',
                },
            }
        }
        config = MagicMock()
        r1 = MagicMock()
        r1.pregunta.dimension = 'FR_TRAB'
        r1.pregunta.texto = 'Mi trabajo ideal es...'
        r1.texto_respuesta = 'uno donde puedo crecer'

        result = grade_frases(config, [r1])
        # Promedio de las dimensiones (solo FR_TRAB = 7)
        self.assertEqual(result['puntuacion'], 7)
        self.assertEqual(result['dimensiones']['FR_TRAB']['puntuacion'], 7)
        # CRÍTICO: una sola llamada IA (evita el timeout del worker gunicorn)
        mock_call.assert_called_once()

    @patch('psicoevaluacion.ai_grading._call_ai')
    def test_tolera_dimensiones_sin_wrapper(self, mock_call):
        # El modelo omite la clave raíz "dimensiones" y devuelve FR_* arriba
        mock_call.return_value = {
            'FR_TRAB': {
                'puntuacion': 9, 'interpretacion': 'Excelente', 'confianza': 'ALTA',
            },
            'puntuacion': 5,  # inyectado por _parse_json_response
            'confianza': 'BAJA',
        }
        config = MagicMock()
        r1 = MagicMock()
        r1.pregunta.dimension = 'FR_TRAB'
        r1.pregunta.texto = 'Mi trabajo ideal es...'
        r1.texto_respuesta = 'uno donde puedo crecer'

        result = grade_frases(config, [r1])
        self.assertEqual(result['dimensiones']['FR_TRAB']['puntuacion'], 9)
        self.assertEqual(result['puntuacion'], 9)


class GradeColoresTest(TestCase):

    def test_no_data_returns_default(self):
        config = MagicMock()
        resp = MagicMock()
        resp.datos_trazo = None
        resp.texto_respuesta = ''
        result = grade_colores(config, resp)
        self.assertEqual(result['puntuacion'], 5)
        self.assertEqual(result['confianza'], 'BAJA')

    @patch('psicoevaluacion.ai_grading._call_ai')
    def test_calls_ai_with_color_data(self, mock_call):
        mock_call.return_value = {
            'puntuacion': 6, 'interpretacion': 'Preferencias normales', 'confianza': 'ALTA'
        }
        config = MagicMock()
        resp = MagicMock()
        resp.datos_trazo = {'ranking': [1, 2, 3]}
        resp.texto_respuesta = ''

        result = grade_colores(config, resp)
        self.assertEqual(result['puntuacion'], 6)


class GradeAllProjectivesTest(TestCase):

    def setUp(self):
        self.ev = Evaluacion(nombres='Test AI', cedula='111', correo='ai@test.com')
        self.ev.save()
        self.prueba_arbol = Prueba.objects.create(
            tipo='ARBOL', nombre='Arbol', instrucciones='i', es_proyectiva=True,
        )
        self.prueba_frases = Prueba.objects.create(
            tipo='FRASES', nombre='Frases', instrucciones='i', es_proyectiva=True,
        )

    def test_raises_when_not_configured(self):
        # Ensure ConfiguracionIA exists but has no key
        config = ConfiguracionIA.load()
        config.anthropic_api_key = ''
        config.google_api_key = ''
        config.save()

        with self.assertRaises(ValueError):
            grade_all_projectives(self.ev)

    @patch('psicoevaluacion.ai_grading._call_ai')
    def test_grades_drawing_and_frases(self, mock_call):
        mock_call.return_value = {
            'puntuacion': 7, 'interpretacion': 'Analisis', 'confianza': 'MEDIA'
        }
        config = ConfiguracionIA.load()
        config.anthropic_api_key = 'test-key'
        config.save()

        RespuestaProyectiva.objects.create(
            evaluacion=self.ev, prueba=self.prueba_arbol,
            tipo='DIBUJO', imagen_canvas='data:image/png;base64,abc',
        )
        preg = Pregunta.objects.create(
            prueba=self.prueba_frases, texto='Mi jefe es...',
            tipo_escala='TEXTO_LIBRE', dimension='FR_TRAB',
        )
        RespuestaProyectiva.objects.create(
            evaluacion=self.ev, prueba=self.prueba_frases,
            pregunta=preg, tipo='TEXTO', texto_respuesta='exigente pero justo',
        )

        resultados = grade_all_projectives(self.ev)
        self.assertIsNotNone(resultados['arbol'])
        self.assertEqual(resultados['arbol']['puntuacion'], 7)
        self.assertIsNotNone(resultados['frases'])

    @patch('psicoevaluacion.ai_grading._call_ai')
    def test_handles_ai_error_gracefully(self, mock_call):
        mock_call.side_effect = Exception('API error')
        config = ConfiguracionIA.load()
        config.anthropic_api_key = 'test-key'
        config.save()

        RespuestaProyectiva.objects.create(
            evaluacion=self.ev, prueba=self.prueba_arbol,
            tipo='DIBUJO', imagen_canvas='data:image/png;base64,abc',
        )

        resultados = grade_all_projectives(self.ev)
        self.assertIsNotNone(resultados['arbol'])
        self.assertEqual(resultados['arbol']['confianza'], 'BAJA')
