"""
Recalcula puntaje_parcial y es_correcta de todas las RespuestaAtencion
existentes, usando la lógica corregida que extrae las respuestas correctas
de los campos anidados de secuencia_correcta (diffs, errors, error_index).
Luego recalcula ResultadoFinal para cada evaluación afectada.
"""
from django.core.management.base import BaseCommand

from psicoevaluacion.models import RespuestaAtencion
from psicoevaluacion.scoring import calcular_resultado_final


class Command(BaseCommand):
    help = 'Recalcula scoring de Atención al Detalle desde respuesta_json existentes'

    def handle(self, *args, **options):
        respuestas = RespuestaAtencion.objects.select_related(
            'pregunta', 'evaluacion').all()

        total = respuestas.count()
        if total == 0:
            self.stdout.write('No hay respuestas de Atención al Detalle.')
            return

        self.stdout.write(f'Recalculando {total} respuestas...')

        updated = 0
        evaluaciones_afectadas = set()

        for r in respuestas:
            sec = r.pregunta.secuencia_correcta or {} if r.pregunta else {}
            old_puntaje = r.puntaje_parcial
            old_correcta = r.es_correcta

            es_correcta = False
            puntaje_parcial = 0.0

            if r.subtipo == 'COMPARACION':
                correctas_set = {str(x) for x in sec.get('diffs', [])}
                encontradas = set()
                if r.respuesta_json and isinstance(r.respuesta_json, list):
                    encontradas = {str(x) for x in r.respuesta_json}
                if correctas_set:
                    tp = len(correctas_set & encontradas)
                    precision = tp / len(encontradas) if encontradas else 0
                    recall = tp / len(correctas_set)
                    if precision + recall > 0:
                        puntaje_parcial = 2 * (precision * recall) / (precision + recall)
                    es_correcta = encontradas == correctas_set

            elif r.subtipo == 'VERIFICACION':
                correctas_set = {str(x) for x in sec.get('errors', [])}
                encontradas = set()
                if r.respuesta_json and isinstance(r.respuesta_json, list):
                    encontradas = {str(x) for x in r.respuesta_json}
                if correctas_set:
                    tp = len(correctas_set & encontradas)
                    puntaje_parcial = tp / len(correctas_set)
                    es_correcta = encontradas == correctas_set

            elif r.subtipo == 'SECUENCIA':
                error_idx = sec.get('error_index')
                if r.respuesta_json is not None and error_idx is not None:
                    es_correcta = str(r.respuesta_json) == str(error_idx)
                    puntaje_parcial = 1.0 if es_correcta else 0.0

            if puntaje_parcial != old_puntaje or es_correcta != old_correcta:
                r.puntaje_parcial = puntaje_parcial
                r.es_correcta = es_correcta
                r.save(update_fields=['puntaje_parcial', 'es_correcta'])
                updated += 1
                self.stdout.write(
                    f'  {r.subtipo} pregunta={r.pregunta_id}: '
                    f'{old_puntaje:.2f}→{puntaje_parcial:.2f}, '
                    f'{old_correcta}→{es_correcta}'
                )

            evaluaciones_afectadas.add(r.evaluacion_id)

        self.stdout.write(f'\n{updated}/{total} respuestas actualizadas.')

        # Recalcular ResultadoFinal para cada evaluación afectada
        self.stdout.write(f'Recalculando {len(evaluaciones_afectadas)} evaluaciones...')
        from psicoevaluacion.models import Evaluacion
        for eval_id in evaluaciones_afectadas:
            try:
                evaluacion = Evaluacion.objects.get(id=eval_id)
                calcular_resultado_final(evaluacion)
                self.stdout.write(f'  Evaluacion {eval_id} ({evaluacion.candidato}): OK')
            except Exception as e:
                self.stdout.write(f'  Evaluacion {eval_id}: ERROR - {e}')

        self.stdout.write(self.style.SUCCESS('Recálculo completado.'))
