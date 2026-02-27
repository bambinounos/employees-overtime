from unittest.mock import MagicMock, patch, PropertyMock
from django.test import TestCase

from psicoevaluacion.models import (
    PerfilObjetivo, Prueba, Pregunta, Opcion, Evaluacion,
    RespuestaPsicometrica, RespuestaMemoria, RespuestaMatriz,
    RespuestaSituacional, RespuestaProyectiva, ResultadoFinal,
)
from psicoevaluacion.scoring import (
    calcular_bigfive, calcular_compromiso, calcular_obediencia,
    calcular_memoria, calcular_matrices, calcular_situacional,
    calcular_resultado_final, determinar_veredicto,
    calcular_deseabilidad_social, calcular_consistencia,
)
from psicoevaluacion.utils import seleccionar_preguntas_evaluacion


def _mock_respuesta(dimension, valor, es_inversa=False):
    """Crea un mock de RespuestaPsicometrica."""
    r = MagicMock()
    r.valor = valor
    r.pregunta = MagicMock()
    r.pregunta.dimension = dimension
    r.pregunta.es_inversa = es_inversa
    return r


def _mock_respuesta_memoria(es_correcta, longitud):
    """Crea un mock de RespuestaMemoria."""
    r = MagicMock()
    r.es_correcta = es_correcta
    r.longitud_secuencia = longitud
    return r


def _mock_respuesta_matriz(es_correcta):
    """Crea un mock de RespuestaMatriz."""
    r = MagicMock()
    r.es_correcta = es_correcta
    return r


def _mock_respuesta_situacional(dimension, valor):
    """Crea un mock de RespuestaSituacional."""
    r = MagicMock()
    r.valor = valor
    r.pregunta = MagicMock()
    r.pregunta.dimension = dimension
    return r


# ──────────────────────────────────────────────
# BIG FIVE TESTS
# ──────────────────────────────────────────────

class CalcBigFiveTest(TestCase):

    def test_todos_directos_valor_5(self):
        respuestas = [_mock_respuesta('BF_RESP', 5) for _ in range(10)]
        result = calcular_bigfive(respuestas)
        self.assertEqual(result['responsabilidad'], 5.0)

    def test_todos_directos_valor_1(self):
        respuestas = [_mock_respuesta('BF_AMAB', 1) for _ in range(5)]
        result = calcular_bigfive(respuestas)
        self.assertEqual(result['amabilidad'], 1.0)

    def test_con_items_inversos(self):
        # 7 directos con valor 5, 3 inversos con valor 1 -> invertido = 5
        respuestas = (
            [_mock_respuesta('BF_RESP', 5) for _ in range(7)] +
            [_mock_respuesta('BF_RESP', 1, es_inversa=True) for _ in range(3)]
        )
        result = calcular_bigfive(respuestas)
        self.assertEqual(result['responsabilidad'], 5.0)

    def test_mezcla_valores(self):
        respuestas = [
            _mock_respuesta('BF_NEUR', 3),
            _mock_respuesta('BF_NEUR', 4),
            _mock_respuesta('BF_NEUR', 5),
        ]
        result = calcular_bigfive(respuestas)
        self.assertEqual(result['neuroticismo'], 4.0)

    def test_sin_respuestas(self):
        result = calcular_bigfive([])
        self.assertEqual(result['responsabilidad'], 0)
        self.assertEqual(result['amabilidad'], 0)
        self.assertEqual(result['neuroticismo'], 0)
        self.assertEqual(result['apertura'], 0)
        self.assertEqual(result['extroversion'], 0)

    def test_todas_dimensiones(self):
        respuestas = []
        for dim in ['BF_RESP', 'BF_AMAB', 'BF_NEUR', 'BF_APER', 'BF_EXTR']:
            respuestas.append(_mock_respuesta(dim, 3))
        result = calcular_bigfive(respuestas)
        for key in ['responsabilidad', 'amabilidad', 'neuroticismo', 'apertura', 'extroversion']:
            self.assertEqual(result[key], 3.0)

    def test_inversion_escala(self):
        # Valor 2 invertido: 6-2 = 4
        respuestas = [_mock_respuesta('BF_EXTR', 2, es_inversa=True)]
        result = calcular_bigfive(respuestas)
        self.assertEqual(result['extroversion'], 4.0)


# ──────────────────────────────────────────────
# COMPROMISO TESTS
# ──────────────────────────────────────────────

class CalcCompromisoTest(TestCase):

    def test_calculo_por_subdimension(self):
        respuestas = [
            _mock_respuesta('CO_AFEC', 5),
            _mock_respuesta('CO_AFEC', 4),
            _mock_respuesta('CO_CONT', 3),
            _mock_respuesta('CO_NORM', 4),
            _mock_respuesta('CO_NORM', 5),
        ]
        result = calcular_compromiso(respuestas)
        self.assertEqual(result['afectivo'], 4.5)
        self.assertEqual(result['continuidad'], 3.0)
        self.assertEqual(result['normativo'], 4.5)

    def test_total_es_promedio_afectivo_normativo(self):
        respuestas = [
            _mock_respuesta('CO_AFEC', 4),
            _mock_respuesta('CO_NORM', 2),
        ]
        result = calcular_compromiso(respuestas)
        # total = mean([4.0, 2.0]) = 3.0
        self.assertEqual(result['total'], 3.0)

    def test_con_inversos(self):
        respuestas = [
            _mock_respuesta('CO_AFEC', 1, es_inversa=True),  # -> 5
        ]
        result = calcular_compromiso(respuestas)
        self.assertEqual(result['afectivo'], 5.0)

    def test_sin_respuestas(self):
        result = calcular_compromiso([])
        self.assertEqual(result['afectivo'], 0)
        self.assertEqual(result['continuidad'], 0)
        self.assertEqual(result['normativo'], 0)
        self.assertEqual(result['total'], 0)


# ──────────────────────────────────────────────
# OBEDIENCIA TESTS
# ──────────────────────────────────────────────

class CalcObedienciaTest(TestCase):

    def test_calculo_general(self):
        respuestas = [
            _mock_respuesta('OB_DISC', 5),
            _mock_respuesta('OB_CONF', 4),
            _mock_respuesta('OB_AUTO', 3),
        ]
        result = calcular_obediencia(respuestas)
        self.assertEqual(result, 4.0)

    def test_con_inversos(self):
        respuestas = [
            _mock_respuesta('OB_DISC', 1, es_inversa=True),  # -> 5
            _mock_respuesta('OB_DISC', 5),
        ]
        result = calcular_obediencia(respuestas)
        self.assertEqual(result, 5.0)

    def test_sin_respuestas(self):
        result = calcular_obediencia([])
        self.assertEqual(result, 0)

    def test_valores_extremos(self):
        respuestas = [_mock_respuesta('OB_DISC', 1) for _ in range(10)]
        result = calcular_obediencia(respuestas)
        self.assertEqual(result, 1.0)


# ──────────────────────────────────────────────
# MEMORIA TESTS
# ──────────────────────────────────────────────

class CalcMemoriaTest(TestCase):

    def test_todo_correcto(self):
        respuestas = [
            _mock_respuesta_memoria(True, 3),
            _mock_respuesta_memoria(True, 4),
            _mock_respuesta_memoria(True, 5),
        ]
        result = calcular_memoria(respuestas)
        self.assertEqual(result['porcentaje'], 100.0)
        self.assertEqual(result['max_span'], 5)

    def test_todo_incorrecto(self):
        respuestas = [
            _mock_respuesta_memoria(False, 3),
            _mock_respuesta_memoria(False, 4),
        ]
        result = calcular_memoria(respuestas)
        self.assertEqual(result['porcentaje'], 0.0)
        self.assertEqual(result['max_span'], 0)

    def test_parcial(self):
        respuestas = [
            _mock_respuesta_memoria(True, 3),
            _mock_respuesta_memoria(False, 4),
            _mock_respuesta_memoria(True, 5),
            _mock_respuesta_memoria(False, 6),
        ]
        result = calcular_memoria(respuestas)
        self.assertEqual(result['porcentaje'], 50.0)
        self.assertEqual(result['max_span'], 5)

    def test_max_span_correcto(self):
        respuestas = [
            _mock_respuesta_memoria(True, 3),
            _mock_respuesta_memoria(True, 6),
            _mock_respuesta_memoria(True, 4),
        ]
        result = calcular_memoria(respuestas)
        self.assertEqual(result['max_span'], 6)

    def test_sin_respuestas(self):
        result = calcular_memoria([])
        self.assertEqual(result['porcentaje'], 0)
        self.assertEqual(result['max_span'], 0)


# ──────────────────────────────────────────────
# MATRICES TESTS
# ──────────────────────────────────────────────

class CalcMatricesTest(TestCase):

    def test_100_porciento(self):
        respuestas = [_mock_respuesta_matriz(True) for _ in range(10)]
        result = calcular_matrices(respuestas)
        self.assertEqual(result, 100.0)

    def test_0_porciento(self):
        respuestas = [_mock_respuesta_matriz(False) for _ in range(10)]
        result = calcular_matrices(respuestas)
        self.assertEqual(result, 0.0)

    def test_50_porciento_aproximado(self):
        # First 5 correct, last 5 wrong. Due to weighting, result != 50 exactly.
        respuestas = (
            [_mock_respuesta_matriz(True) for _ in range(5)] +
            [_mock_respuesta_matriz(False) for _ in range(5)]
        )
        result = calcular_matrices(respuestas)
        # First items weigh less, so <50%
        self.assertGreater(result, 0)
        self.assertLess(result, 100)

    def test_ponderacion_por_dificultad(self):
        # Only last question correct (hardest) vs only first correct (easiest)
        resp_facil = [_mock_respuesta_matriz(False) for _ in range(9)]
        resp_facil.insert(0, _mock_respuesta_matriz(True))
        score_facil = calcular_matrices(resp_facil)

        resp_dificil = [_mock_respuesta_matriz(False) for _ in range(9)]
        resp_dificil.append(_mock_respuesta_matriz(True))
        score_dificil = calcular_matrices(resp_dificil)

        self.assertGreater(score_dificil, score_facil)

    def test_sin_respuestas(self):
        result = calcular_matrices([])
        self.assertEqual(result, 0)


# ──────────────────────────────────────────────
# SITUACIONAL TESTS
# ──────────────────────────────────────────────

class CalcSituacionalTest(TestCase):

    def test_puntaje_por_dimension(self):
        respuestas = [
            _mock_respuesta_situacional('SIT_RESP', 5),
            _mock_respuesta_situacional('SIT_RESP', 3),
            _mock_respuesta_situacional('SIT_OBED', 4),
            _mock_respuesta_situacional('SIT_LEAL', 5),
        ]
        result = calcular_situacional(respuestas)
        self.assertEqual(result['SIT_RESP'], 4.0)
        self.assertEqual(result['SIT_OBED'], 4.0)
        self.assertEqual(result['SIT_LEAL'], 5.0)

    def test_total_normalizado_porcentaje(self):
        respuestas = [
            _mock_respuesta_situacional('SIT_RESP', 4),
            _mock_respuesta_situacional('SIT_OBED', 4),
            _mock_respuesta_situacional('SIT_LEAL', 4),
        ]
        result = calcular_situacional(respuestas)
        # raw sum = 12, normalized = (12/15)*100 = 80.0
        self.assertEqual(result['total'], 80.0)

    def test_total_maximo(self):
        respuestas = [
            _mock_respuesta_situacional('SIT_RESP', 5),
            _mock_respuesta_situacional('SIT_OBED', 5),
            _mock_respuesta_situacional('SIT_LEAL', 5),
        ]
        result = calcular_situacional(respuestas)
        self.assertEqual(result['total'], 100.0)

    def test_sin_respuestas(self):
        result = calcular_situacional([])
        self.assertEqual(result['total'], 0)


# ──────────────────────────────────────────────
# VEREDICTO TESTS
# ──────────────────────────────────────────────

class DeterminarVeredictoTest(TestCase):

    def setUp(self):
        self.perfil = PerfilObjetivo.objects.create(
            nombre="Test",
            min_responsabilidad=4.0,
            min_amabilidad=3.0,
            max_neuroticismo=3.0,
            min_compromiso_organizacional=3.5,
            min_obediencia=3.5,
            min_memoria=60.0,
            min_matrices=50.0,
        )

    def _make_resultado(self, **kwargs):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        defaults = {
            'evaluacion': ev,
            'puntaje_responsabilidad': 4.5,
            'puntaje_amabilidad': 4.0,
            'puntaje_neuroticismo': 2.0,
            'puntaje_apertura': 3.5,
            'puntaje_extroversion': 3.0,
            'puntaje_compromiso_total': 4.0,
            'puntaje_obediencia': 4.0,
            'puntaje_memoria': 80.0,
            'puntaje_matrices': 70.0,
        }
        defaults.update(kwargs)
        return ResultadoFinal.objects.create(**defaults)

    def test_apto_cumple_todo(self):
        resultado = self._make_resultado()
        veredicto = determinar_veredicto(resultado, self.perfil)
        self.assertEqual(veredicto, 'APTO')

    def test_no_apto_falla_2_criterios(self):
        resultado = self._make_resultado(
            puntaje_responsabilidad=2.0,  # Falla
            puntaje_compromiso_total=1.0,  # Falla
        )
        veredicto = determinar_veredicto(resultado, self.perfil)
        self.assertEqual(veredicto, 'NO_APTO')

    def test_revision_falla_1_criterio(self):
        resultado = self._make_resultado(
            puntaje_responsabilidad=3.0,  # Falla (min 4.0)
        )
        veredicto = determinar_veredicto(resultado, self.perfil)
        self.assertEqual(veredicto, 'REVISION')

    def test_revision_proyectivas_pendientes(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        prueba = Prueba.objects.create(
            tipo='ARBOL', nombre='Árbol', instrucciones='i', es_proyectiva=True,
        )
        RespuestaProyectiva.objects.create(
            evaluacion=ev, prueba=prueba, tipo='DIBUJO', revisado=False,
        )
        resultado = ResultadoFinal.objects.create(
            evaluacion=ev,
            puntaje_responsabilidad=4.5,
            puntaje_neuroticismo=2.0,
            puntaje_compromiso_total=4.0,
            puntaje_obediencia=4.0,
            puntaje_memoria=80.0,
            puntaje_matrices=70.0,
        )
        veredicto = determinar_veredicto(resultado, self.perfil)
        self.assertEqual(veredicto, 'REVISION')

    def test_no_apto_neuroticismo_alto(self):
        resultado = self._make_resultado(
            puntaje_neuroticismo=4.5,  # Falla (max 3.0)
            puntaje_responsabilidad=2.0,  # Falla
        )
        veredicto = determinar_veredicto(resultado, self.perfil)
        self.assertEqual(veredicto, 'NO_APTO')

    def test_no_apto_multiples_fallos(self):
        resultado = self._make_resultado(
            puntaje_responsabilidad=1.0,
            puntaje_compromiso_total=1.0,
            puntaje_obediencia=1.0,
            puntaje_memoria=10.0,
            puntaje_matrices=10.0,
            puntaje_neuroticismo=5.0,
        )
        veredicto = determinar_veredicto(resultado, self.perfil)
        self.assertEqual(veredicto, 'NO_APTO')


# ──────────────────────────────────────────────
# RESULTADO FINAL INTEGRATION TEST
# ──────────────────────────────────────────────

class CalcResultadoFinalTest(TestCase):

    def _setup_full_evaluation(self):
        """Create a full evaluation with responses for all test types."""
        perfil = PerfilObjetivo.objects.create(nombre="Test", activo=True)

        # Create pruebas
        bf_prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='i',
        )
        co_prueba = Prueba.objects.create(
            tipo='COMPROMISO', nombre='CO', instrucciones='i',
        )
        ob_prueba = Prueba.objects.create(
            tipo='OBEDIENCIA', nombre='OB', instrucciones='i',
        )
        mem_prueba = Prueba.objects.create(
            tipo='MEMORIA', nombre='MEM', instrucciones='i',
        )
        mat_prueba = Prueba.objects.create(
            tipo='MATRICES', nombre='MAT', instrucciones='i',
        )
        sit_prueba = Prueba.objects.create(
            tipo='SITUACIONAL', nombre='SIT', instrucciones='i',
        )

        # Create evaluation
        ev = Evaluacion(
            nombres='Test Completo', cedula='111', correo='t@t.com',
            perfil_objetivo=perfil,
        )
        ev.save()

        # Create Big Five questions and responses (2 per dimension)
        for dim in ['BF_RESP', 'BF_AMAB', 'BF_NEUR', 'BF_APER', 'BF_EXTR']:
            for j in range(2):
                preg = Pregunta.objects.create(
                    prueba=bf_prueba, texto=f'{dim}_{j}',
                    tipo_escala='LIKERT5', dimension=dim,
                )
                RespuestaPsicometrica.objects.create(
                    evaluacion=ev, pregunta=preg, valor=4,
                )

        # Compromiso
        for dim in ['CO_AFEC', 'CO_CONT', 'CO_NORM']:
            preg = Pregunta.objects.create(
                prueba=co_prueba, texto=f'{dim}_1',
                tipo_escala='LIKERT5', dimension=dim,
            )
            RespuestaPsicometrica.objects.create(
                evaluacion=ev, pregunta=preg, valor=4,
            )

        # Obediencia
        for dim in ['OB_DISC', 'OB_CONF', 'OB_AUTO']:
            preg = Pregunta.objects.create(
                prueba=ob_prueba, texto=f'{dim}_1',
                tipo_escala='LIKERT5', dimension=dim,
            )
            RespuestaPsicometrica.objects.create(
                evaluacion=ev, pregunta=preg, valor=4,
            )

        # Memoria
        preg_mem = Pregunta.objects.create(
            prueba=mem_prueba, texto='Mem1', tipo_escala='SECUENCIA',
        )
        RespuestaMemoria.objects.create(
            evaluacion=ev, pregunta=preg_mem,
            secuencia_presentada=[1, 2, 3], secuencia_respondida=[1, 2, 3],
            es_correcta=True, longitud_secuencia=3,
        )

        # Matrices
        preg_mat = Pregunta.objects.create(
            prueba=mat_prueba, texto='Mat1', tipo_escala='OPCION_MULTIPLE',
        )
        RespuestaMatriz.objects.create(
            evaluacion=ev, pregunta=preg_mat, es_correcta=True,
        )

        # Situacional
        for dim in ['SIT_RESP', 'SIT_OBED', 'SIT_LEAL']:
            preg = Pregunta.objects.create(
                prueba=sit_prueba, texto=f'{dim}_1',
                tipo_escala='OPCION_MULTIPLE', dimension=dim,
            )
            RespuestaSituacional.objects.create(
                evaluacion=ev, pregunta=preg, valor=4,
            )

        return ev

    def test_orquestacion_completa(self):
        ev = self._setup_full_evaluation()
        resultado = calcular_resultado_final(ev)

        self.assertIsNotNone(resultado.puntaje_responsabilidad)
        self.assertIsNotNone(resultado.puntaje_amabilidad)
        self.assertIsNotNone(resultado.puntaje_compromiso_total)
        self.assertIsNotNone(resultado.puntaje_obediencia)
        self.assertIsNotNone(resultado.puntaje_memoria)
        self.assertIsNotNone(resultado.puntaje_matrices)
        self.assertIsNotNone(resultado.puntaje_situacional)
        self.assertIsNotNone(resultado.indice_responsabilidad_total)
        self.assertIsNotNone(resultado.indice_lealtad)
        self.assertIsNotNone(resultado.indice_obediencia_total)
        self.assertIsNotNone(resultado.veredicto_automatico)

    def test_evaluacion_sin_respuestas(self):
        perfil = PerfilObjetivo.objects.create(nombre="Test", activo=True)
        ev = Evaluacion(
            nombres='Sin Resp', cedula='222', correo='s@s.com',
            perfil_objetivo=perfil,
        )
        ev.save()
        resultado = calcular_resultado_final(ev)
        # Should not crash, all scores 0
        self.assertEqual(resultado.puntaje_responsabilidad, 0)
        self.assertEqual(resultado.puntaje_memoria, 0)

    def test_evaluacion_sin_perfil(self):
        """Si no hay perfil, veredicto = REVISION."""
        ev = Evaluacion(nombres='NoPerfil', cedula='333', correo='n@n.com')
        ev.save()
        # Make sure no active profiles exist
        PerfilObjetivo.objects.all().delete()
        resultado = calcular_resultado_final(ev)
        self.assertEqual(resultado.veredicto_automatico, 'REVISION')

    def test_resultado_se_actualiza_no_duplica(self):
        ev = self._setup_full_evaluation()
        r1 = calcular_resultado_final(ev)
        r2 = calcular_resultado_final(ev)
        self.assertEqual(r1.pk, r2.pk)
        self.assertEqual(ResultadoFinal.objects.filter(evaluacion=ev).count(), 1)


# ──────────────────────────────────────────────
# V2: DESEABILIDAD SOCIAL TESTS
# ──────────────────────────────────────────────

class CalcDeseabilidadSocialTest(TestCase):

    def test_valores_normales(self):
        respuestas = [
            _mock_respuesta('DS_DESB', 2),
            _mock_respuesta('DS_DESB', 3),
            _mock_respuesta('DS_DESB', 2),
        ]
        result = calcular_deseabilidad_social(respuestas)
        self.assertAlmostEqual(result, 2.333, places=2)

    def test_valores_altos_sospechoso(self):
        respuestas = [_mock_respuesta('DS_DESB', 5) for _ in range(10)]
        result = calcular_deseabilidad_social(respuestas)
        self.assertEqual(result, 5.0)
        self.assertGreater(result, 4.0)

    def test_sin_respuestas(self):
        result = calcular_deseabilidad_social([])
        self.assertEqual(result, 0)

    def test_con_items_inversos(self):
        # Valor 2 inverso -> 6 - 2 = 4
        respuestas = [_mock_respuesta('DS_DESB', 2, es_inversa=True)]
        result = calcular_deseabilidad_social(respuestas)
        self.assertEqual(result, 4.0)


# ──────────────────────────────────────────────
# V2: CONSISTENCIA TESTS
# ──────────────────────────────────────────────

class CalcConsistenciaTest(TestCase):

    def _setup_par(self, val_a, val_b, es_inversa_a=False, es_inversa_b=False):
        """Create a pair of questions linked by par_consistencia and respond."""
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='inst',
        )
        preg_a = Pregunta.objects.create(
            prueba=prueba, texto='Par_A', tipo_escala='LIKERT5',
            dimension='BF_RESP', es_inversa=es_inversa_a,
        )
        preg_b = Pregunta.objects.create(
            prueba=prueba, texto='Par_B', tipo_escala='LIKERT5',
            dimension='BF_RESP', es_inversa=es_inversa_b,
        )
        preg_a.par_consistencia = preg_b
        preg_a.save()
        preg_b.par_consistencia = preg_a
        preg_b.save()

        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()

        RespuestaPsicometrica.objects.create(
            evaluacion=ev, pregunta=preg_a, valor=val_a,
        )
        RespuestaPsicometrica.objects.create(
            evaluacion=ev, pregunta=preg_b, valor=val_b,
        )
        return ev

    def test_100_porciento_pares_identicos(self):
        ev = self._setup_par(4, 4)
        result = calcular_consistencia(ev)
        self.assertEqual(result, 100.0)

    def test_0_porciento_maxima_diferencia(self):
        ev = self._setup_par(1, 5)
        result = calcular_consistencia(ev)
        self.assertEqual(result, 0.0)

    def test_parcial(self):
        ev = self._setup_par(3, 5)
        result = calcular_consistencia(ev)
        # diff=2, concordancia = 1 - 2/4 = 0.5 -> 50%
        self.assertEqual(result, 50.0)

    def test_sin_pares(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='inst',
        )
        preg = Pregunta.objects.create(
            prueba=prueba, texto='Solo', tipo_escala='LIKERT5',
        )
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        RespuestaPsicometrica.objects.create(
            evaluacion=ev, pregunta=preg, valor=3,
        )
        result = calcular_consistencia(ev)
        self.assertIsNone(result)

    def test_con_inversion(self):
        # preg_a direct val=4, preg_b inverse val=2 -> inverted=4
        ev = self._setup_par(4, 2, es_inversa_a=False, es_inversa_b=True)
        result = calcular_consistencia(ev)
        self.assertEqual(result, 100.0)


# ──────────────────────────────────────────────
# V2: VEREDICTO CON CONFIABILIDAD
# ──────────────────────────────────────────────

class DeterminarVeredictoConfiabilidadTest(TestCase):

    def setUp(self):
        self.perfil = PerfilObjetivo.objects.create(
            nombre="Test",
            min_responsabilidad=4.0,
            min_amabilidad=3.0,
            max_neuroticismo=3.0,
            min_compromiso_organizacional=3.5,
            min_obediencia=3.5,
            min_memoria=60.0,
            min_matrices=50.0,
        )

    def test_revision_cuando_no_confiable(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        resultado = ResultadoFinal.objects.create(
            evaluacion=ev,
            puntaje_responsabilidad=4.5,
            puntaje_neuroticismo=2.0,
            puntaje_compromiso_total=4.0,
            puntaje_obediencia=4.0,
            puntaje_memoria=80.0,
            puntaje_matrices=70.0,
            evaluacion_confiable=False,
        )
        veredicto = determinar_veredicto(resultado, self.perfil)
        self.assertEqual(veredicto, 'REVISION')

    def test_apto_cuando_confiable_y_todo_bien(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        resultado = ResultadoFinal.objects.create(
            evaluacion=ev,
            puntaje_responsabilidad=4.5,
            puntaje_neuroticismo=2.0,
            puntaje_compromiso_total=4.0,
            puntaje_obediencia=4.0,
            puntaje_memoria=80.0,
            puntaje_matrices=70.0,
            evaluacion_confiable=True,
        )
        veredicto = determinar_veredicto(resultado, self.perfil)
        self.assertEqual(veredicto, 'APTO')


# ──────────────────────────────────────────────
# V2: RESULTADO FINAL CON DESEABILIDAD + CONSISTENCIA
# ──────────────────────────────────────────────

class CalcResultadoFinalV2Test(TestCase):

    def test_deseabilidad_se_calcula(self):
        perfil = PerfilObjetivo.objects.create(nombre="Test", activo=True)
        ds_prueba = Prueba.objects.create(
            tipo='DESEABILIDAD', nombre='DS', instrucciones='i',
        )
        ev = Evaluacion(
            nombres='Test DS', cedula='111', correo='t@t.com',
            perfil_objetivo=perfil,
        )
        ev.save()

        for i in range(5):
            preg = Pregunta.objects.create(
                prueba=ds_prueba, texto=f'DS_{i}',
                tipo_escala='LIKERT5', dimension='DS_DESB',
            )
            RespuestaPsicometrica.objects.create(
                evaluacion=ev, pregunta=preg, valor=5,
            )

        resultado = calcular_resultado_final(ev)
        self.assertEqual(resultado.puntaje_deseabilidad_social, 5.0)
        self.assertFalse(resultado.evaluacion_confiable)

    def test_evaluacion_confiable_con_ds_normal(self):
        perfil = PerfilObjetivo.objects.create(nombre="Test", activo=True)
        ds_prueba = Prueba.objects.create(
            tipo='DESEABILIDAD', nombre='DS', instrucciones='i',
        )
        ev = Evaluacion(
            nombres='Test DS Normal', cedula='222', correo='n@n.com',
            perfil_objetivo=perfil,
        )
        ev.save()

        for i in range(5):
            preg = Pregunta.objects.create(
                prueba=ds_prueba, texto=f'DSN_{i}',
                tipo_escala='LIKERT5', dimension='DS_DESB',
            )
            RespuestaPsicometrica.objects.create(
                evaluacion=ev, pregunta=preg, valor=2,
            )

        resultado = calcular_resultado_final(ev)
        self.assertEqual(resultado.puntaje_deseabilidad_social, 2.0)
        self.assertTrue(resultado.evaluacion_confiable)


# ──────────────────────────────────────────────
# V2: SELECCIÓN ALEATORIA DE PREGUNTAS
# ──────────────────────────────────────────────

class SeleccionarPreguntasTest(TestCase):

    def test_aplica_todas_cuando_items_a_aplicar_es_0(self):
        prueba = Prueba.objects.create(
            tipo='MEMORIA', nombre='MEM', instrucciones='i',
            activa=True, items_banco=5, items_a_aplicar=0,
        )
        for i in range(5):
            Pregunta.objects.create(
                prueba=prueba, texto=f'M_{i}', tipo_escala='SECUENCIA',
            )
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()

        ids = seleccionar_preguntas_evaluacion(ev)
        self.assertEqual(len(ids), 5)

    def test_seleccion_respeta_items_a_aplicar(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='i',
            activa=True, items_banco=10, items_a_aplicar=5,
        )
        for i in range(10):
            Pregunta.objects.create(
                prueba=prueba, texto=f'BF_{i}', tipo_escala='LIKERT5',
                dimension='BF_RESP',
            )
        ev = Evaluacion(nombres='Test', cedula='222', correo='s@s.com')
        ev.save()

        ids = seleccionar_preguntas_evaluacion(ev)
        self.assertEqual(len(ids), 5)

    def test_pares_consistencia_siempre_incluidos(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='i',
            activa=True, items_banco=10, items_a_aplicar=4,
        )
        preguntas = []
        for i in range(10):
            p = Pregunta.objects.create(
                prueba=prueba, texto=f'BF_{i}', tipo_escala='LIKERT5',
                dimension='BF_RESP',
            )
            preguntas.append(p)

        # Link pair
        preguntas[0].par_consistencia = preguntas[1]
        preguntas[0].save()
        preguntas[1].par_consistencia = preguntas[0]
        preguntas[1].save()

        ev = Evaluacion(nombres='Test', cedula='333', correo='p@p.com')
        ev.save()

        ids = seleccionar_preguntas_evaluacion(ev)
        self.assertIn(preguntas[0].id, ids)
        self.assertIn(preguntas[1].id, ids)
        self.assertEqual(len(ids), 4)

    def test_guarda_en_evaluacion(self):
        prueba = Prueba.objects.create(
            tipo='MEMORIA', nombre='MEM', instrucciones='i',
            activa=True, items_banco=3, items_a_aplicar=0,
        )
        for i in range(3):
            Pregunta.objects.create(
                prueba=prueba, texto=f'M_{i}', tipo_escala='SECUENCIA',
            )
        ev = Evaluacion(nombres='Test', cedula='444', correo='g@g.com')
        ev.save()

        seleccionar_preguntas_evaluacion(ev)
        ev.refresh_from_db()
        self.assertIsNotNone(ev.preguntas_seleccionadas)
        self.assertEqual(len(ev.preguntas_seleccionadas), 3)

    def test_seleccion_balanceada_por_dimension(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='i',
            activa=True, items_banco=20, items_a_aplicar=10,
        )
        dims = ['BF_RESP', 'BF_AMAB', 'BF_NEUR', 'BF_APER', 'BF_EXTR']
        for dim in dims:
            for i in range(4):
                Pregunta.objects.create(
                    prueba=prueba, texto=f'{dim}_{i}', tipo_escala='LIKERT5',
                    dimension=dim,
                )
        ev = Evaluacion(nombres='Test', cedula='555', correo='b@b.com')
        ev.save()

        ids = seleccionar_preguntas_evaluacion(ev)
        self.assertEqual(len(ids), 10)
        # Each dimension should have 2 questions selected (10 / 5 dims)
        selected_pregs = Pregunta.objects.filter(id__in=ids)
        dim_counts = {}
        for p in selected_pregs:
            dim_counts[p.dimension] = dim_counts.get(p.dimension, 0) + 1
        for dim in dims:
            self.assertEqual(dim_counts.get(dim, 0), 2)
