from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError

from psicoevaluacion.models import (
    PerfilObjetivo, Prueba, Pregunta, Opcion, Evaluacion,
    RespuestaPsicometrica, RespuestaProyectiva, RespuestaMemoria,
    RespuestaMatriz, RespuestaSituacional, ResultadoFinal,
)


class PerfilObjetivoModelTest(TestCase):

    def test_crear_perfil_objetivo_con_defaults(self):
        perfil = PerfilObjetivo.objects.create()
        self.assertEqual(perfil.nombre, "Perfil Estándar")
        self.assertEqual(perfil.min_responsabilidad, 4.0)
        self.assertEqual(perfil.min_amabilidad, 3.0)
        self.assertEqual(perfil.max_neuroticismo, 3.0)
        self.assertEqual(perfil.min_apertura, 2.5)
        self.assertEqual(perfil.min_extroversion, 2.0)
        self.assertEqual(perfil.min_compromiso_organizacional, 3.5)
        self.assertEqual(perfil.min_obediencia, 3.5)
        self.assertEqual(perfil.min_memoria, 60.0)
        self.assertEqual(perfil.min_matrices, 50.0)
        self.assertEqual(perfil.min_situacional, 60.0)
        self.assertTrue(perfil.activo)

    def test_str(self):
        perfil = PerfilObjetivo.objects.create(nombre="Perfil Exigente")
        self.assertEqual(str(perfil), "Perfil Exigente")


class PruebaModelTest(TestCase):

    def test_crear_prueba(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE',
            nombre='Big Five',
            instrucciones='Instrucciones de prueba',
        )
        self.assertEqual(prueba.tipo, 'BIGFIVE')
        self.assertTrue(prueba.activa)
        self.assertFalse(prueba.es_proyectiva)

    def test_tipo_unique(self):
        Prueba.objects.create(tipo='BIGFIVE', nombre='BF1', instrucciones='inst')
        with self.assertRaises(IntegrityError):
            Prueba.objects.create(tipo='BIGFIVE', nombre='BF2', instrucciones='inst2')

    def test_str(self):
        prueba = Prueba.objects.create(tipo='MEMORIA', nombre='Test Memoria', instrucciones='i')
        self.assertEqual(str(prueba), 'Test Memoria')

    def test_ordering(self):
        p1 = Prueba.objects.create(tipo='BIGFIVE', nombre='BF', instrucciones='i', orden=2)
        p2 = Prueba.objects.create(tipo='MEMORIA', nombre='Mem', instrucciones='i', orden=1)
        pruebas = list(Prueba.objects.all())
        self.assertEqual(pruebas[0], p2)
        self.assertEqual(pruebas[1], p1)


class PreguntaModelTest(TestCase):

    def setUp(self):
        self.prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='Big Five', instrucciones='inst'
        )

    def test_crear_pregunta(self):
        preg = Pregunta.objects.create(
            prueba=self.prueba,
            texto='Test question',
            tipo_escala='LIKERT5',
            dimension='BF_RESP',
        )
        self.assertEqual(preg.dimension, 'BF_RESP')
        self.assertFalse(preg.es_inversa)
        self.assertIsNone(preg.secuencia_correcta)

    def test_pregunta_inversa(self):
        preg = Pregunta.objects.create(
            prueba=self.prueba,
            texto='Inversa',
            tipo_escala='LIKERT5',
            dimension='BF_RESP',
            es_inversa=True,
        )
        self.assertTrue(preg.es_inversa)

    def test_str(self):
        preg = Pregunta.objects.create(
            prueba=self.prueba,
            texto='Texto largo de prueba para verificar el truncamiento en str',
            tipo_escala='LIKERT5',
        )
        self.assertIn('BIGFIVE', str(preg))

    def test_pregunta_con_secuencia(self):
        prueba_mem = Prueba.objects.create(
            tipo='MEMORIA', nombre='Memoria', instrucciones='inst'
        )
        preg = Pregunta.objects.create(
            prueba=prueba_mem,
            texto='Repita',
            tipo_escala='SECUENCIA',
            secuencia_correcta=[3, 7, 2],
        )
        self.assertEqual(preg.secuencia_correcta, [3, 7, 2])


class OpcionModelTest(TestCase):

    def setUp(self):
        prueba = Prueba.objects.create(tipo='BIGFIVE', nombre='BF', instrucciones='i')
        self.pregunta = Pregunta.objects.create(
            prueba=prueba, texto='Q', tipo_escala='LIKERT5',
        )

    def test_crear_opcion(self):
        opcion = Opcion.objects.create(
            pregunta=self.pregunta, texto='De acuerdo', valor=4,
        )
        self.assertEqual(opcion.valor, 4)

    def test_str(self):
        opcion = Opcion.objects.create(
            pregunta=self.pregunta, texto='Totalmente de acuerdo', valor=5,
        )
        self.assertIn('val=5', str(opcion))


class EvaluacionModelTest(TestCase):

    def test_crear_evaluacion_genera_token(self):
        ev = Evaluacion(
            nombres='Juan Pérez',
            cedula='1234567890',
            correo='juan@test.com',
        )
        ev.save()
        self.assertIsNotNone(ev.token)
        self.assertEqual(len(ev.token), 64)

    def test_crear_evaluacion_genera_fecha_expiracion(self):
        ev = Evaluacion(
            nombres='María López',
            cedula='0987654321',
            correo='maria@test.com',
        )
        ev.save()
        self.assertIsNotNone(ev.fecha_expiracion)
        # Should be approximately 48 hours from now
        expected = timezone.now() + timedelta(hours=48)
        diff = abs((ev.fecha_expiracion - expected).total_seconds())
        self.assertLess(diff, 5)  # Less than 5 seconds difference

    def test_token_no_cambia_en_resave(self):
        ev = Evaluacion(
            nombres='Test', cedula='111', correo='t@t.com',
        )
        ev.save()
        original_token = ev.token
        ev.estado = 'EN_CURSO'
        ev.save()
        self.assertEqual(ev.token, original_token)

    def test_esta_expirada_false(self):
        ev = Evaluacion(
            nombres='Test', cedula='111', correo='t@t.com',
        )
        ev.save()
        self.assertFalse(ev.esta_expirada())

    def test_esta_expirada_true(self):
        ev = Evaluacion(
            nombres='Test', cedula='111', correo='t@t.com',
            fecha_expiracion=timezone.now() - timedelta(hours=1),
        )
        ev.save()
        self.assertTrue(ev.esta_expirada())

    def test_str(self):
        ev = Evaluacion(
            nombres='Ana García', cedula='1111111111', correo='ana@test.com',
        )
        ev.save()
        self.assertIn('Ana García', str(ev))
        self.assertIn('PENDIENTE', str(ev))

    def test_estado_default(self):
        ev = Evaluacion(
            nombres='Test', cedula='111', correo='t@t.com',
        )
        ev.save()
        self.assertEqual(ev.estado, 'PENDIENTE')

    def test_uuid_unique(self):
        ev1 = Evaluacion(nombres='A', cedula='1', correo='a@a.com')
        ev1.save()
        ev2 = Evaluacion(nombres='B', cedula='2', correo='b@b.com')
        ev2.save()
        self.assertNotEqual(ev1.uuid, ev2.uuid)


class RespuestaPsicometricaModelTest(TestCase):

    def setUp(self):
        self.prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='inst',
        )
        self.pregunta = Pregunta.objects.create(
            prueba=self.prueba, texto='Q', tipo_escala='LIKERT5',
        )
        self.evaluacion = Evaluacion(
            nombres='Test', cedula='111', correo='t@t.com',
        )
        self.evaluacion.save()

    def test_crear_respuesta(self):
        resp = RespuestaPsicometrica.objects.create(
            evaluacion=self.evaluacion,
            pregunta=self.pregunta,
            valor=4,
        )
        self.assertEqual(resp.valor, 4)

    def test_unique_together(self):
        RespuestaPsicometrica.objects.create(
            evaluacion=self.evaluacion,
            pregunta=self.pregunta,
            valor=3,
        )
        with self.assertRaises(IntegrityError):
            RespuestaPsicometrica.objects.create(
                evaluacion=self.evaluacion,
                pregunta=self.pregunta,
                valor=4,
            )


class CascadeDeleteTest(TestCase):

    def test_eliminar_evaluacion_elimina_respuestas(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='inst',
        )
        pregunta = Pregunta.objects.create(
            prueba=prueba, texto='Q', tipo_escala='LIKERT5',
        )
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()

        RespuestaPsicometrica.objects.create(
            evaluacion=ev, pregunta=pregunta, valor=3,
        )
        RespuestaMemoria.objects.create(
            evaluacion=ev, pregunta=pregunta,
            secuencia_presentada=[1, 2], secuencia_respondida=[1, 2],
            es_correcta=True, longitud_secuencia=2,
        )
        RespuestaMatriz.objects.create(
            evaluacion=ev, pregunta=pregunta, es_correcta=True,
        )
        RespuestaSituacional.objects.create(
            evaluacion=ev, pregunta=pregunta, valor=5,
        )
        RespuestaProyectiva.objects.create(
            evaluacion=ev, prueba=prueba, tipo='DIBUJO',
        )
        ResultadoFinal.objects.create(evaluacion=ev)

        ev.delete()

        self.assertEqual(RespuestaPsicometrica.objects.count(), 0)
        self.assertEqual(RespuestaMemoria.objects.count(), 0)
        self.assertEqual(RespuestaMatriz.objects.count(), 0)
        self.assertEqual(RespuestaSituacional.objects.count(), 0)
        self.assertEqual(RespuestaProyectiva.objects.count(), 0)
        self.assertEqual(ResultadoFinal.objects.count(), 0)

    def test_eliminar_prueba_elimina_preguntas_y_opciones(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='inst',
        )
        preg = Pregunta.objects.create(
            prueba=prueba, texto='Q', tipo_escala='LIKERT5',
        )
        Opcion.objects.create(pregunta=preg, texto='Opt', valor=1)

        prueba.delete()
        self.assertEqual(Pregunta.objects.count(), 0)
        self.assertEqual(Opcion.objects.count(), 0)


class ResultadoFinalModelTest(TestCase):

    def test_str_con_veredicto_final(self):
        ev = Evaluacion(nombres='Carlos', cedula='111', correo='c@c.com')
        ev.save()
        resultado = ResultadoFinal.objects.create(
            evaluacion=ev,
            veredicto_automatico='REVISION',
            veredicto_final='APTO',
        )
        self.assertIn('APTO', str(resultado))
        self.assertIn('Carlos', str(resultado))

    def test_str_sin_veredicto_final(self):
        ev = Evaluacion(nombres='Diana', cedula='222', correo='d@d.com')
        ev.save()
        resultado = ResultadoFinal.objects.create(
            evaluacion=ev,
            veredicto_automatico='NO_APTO',
        )
        self.assertIn('NO_APTO', str(resultado))

    def test_one_to_one_con_evaluacion(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        ResultadoFinal.objects.create(evaluacion=ev)
        with self.assertRaises(IntegrityError):
            ResultadoFinal.objects.create(evaluacion=ev)


# ──────────────────────────────────────────────
# V2 MODEL TESTS
# ──────────────────────────────────────────────

class PreguntaParConsistenciaTest(TestCase):

    def test_par_consistencia_fk(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='inst',
        )
        preg_a = Pregunta.objects.create(
            prueba=prueba, texto='Q_A', tipo_escala='LIKERT5', dimension='BF_RESP',
        )
        preg_b = Pregunta.objects.create(
            prueba=prueba, texto='Q_B', tipo_escala='LIKERT5', dimension='BF_RESP',
        )
        preg_a.par_consistencia = preg_b
        preg_a.save()
        preg_a.refresh_from_db()
        self.assertEqual(preg_a.par_consistencia_id, preg_b.id)

    def test_par_consistencia_null_by_default(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='inst',
        )
        preg = Pregunta.objects.create(
            prueba=prueba, texto='Q', tipo_escala='LIKERT5',
        )
        self.assertIsNone(preg.par_consistencia)

    def test_par_consistencia_reverse_relation(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='inst',
        )
        preg_a = Pregunta.objects.create(
            prueba=prueba, texto='Q_A', tipo_escala='LIKERT5',
        )
        preg_b = Pregunta.objects.create(
            prueba=prueba, texto='Q_B', tipo_escala='LIKERT5',
        )
        preg_a.par_consistencia = preg_b
        preg_a.save()
        self.assertIn(preg_a, preg_b.par_vinculado.all())


class EvaluacionPreguntasSeleccionadasTest(TestCase):

    def test_preguntas_seleccionadas_persiste_json(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        ev.preguntas_seleccionadas = [1, 2, 3, 4, 5]
        ev.save()
        ev.refresh_from_db()
        self.assertEqual(ev.preguntas_seleccionadas, [1, 2, 3, 4, 5])

    def test_preguntas_seleccionadas_null_default(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        self.assertIsNone(ev.preguntas_seleccionadas)


class ResultadoFinalConfiabilidadTest(TestCase):

    def test_evaluacion_confiable_default_true(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        resultado = ResultadoFinal.objects.create(evaluacion=ev)
        self.assertTrue(resultado.evaluacion_confiable)

    def test_puntaje_deseabilidad_y_consistencia_null(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        resultado = ResultadoFinal.objects.create(evaluacion=ev)
        self.assertIsNone(resultado.puntaje_deseabilidad_social)
        self.assertIsNone(resultado.indice_consistencia)


class PruebaItemsBancoTest(TestCase):

    def test_items_banco_defaults(self):
        prueba = Prueba.objects.create(
            tipo='BIGFIVE', nombre='BF', instrucciones='inst',
        )
        self.assertEqual(prueba.items_banco, 0)
        self.assertEqual(prueba.items_a_aplicar, 0)

    def test_deseabilidad_tipo(self):
        prueba = Prueba.objects.create(
            tipo='DESEABILIDAD', nombre='DS', instrucciones='inst',
        )
        self.assertEqual(prueba.tipo, 'DESEABILIDAD')
