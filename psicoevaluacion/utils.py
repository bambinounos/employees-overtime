import uuid
import random
from collections import defaultdict

from .models import Prueba, Pregunta


def generar_token():
    """Genera un token criptográficamente seguro de 64 caracteres hex."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:32]


def seleccionar_preguntas_evaluacion(evaluacion):
    """
    Selecciona preguntas balanceadas por dimensión para una evaluación.
    Usa items_a_aplicar de cada Prueba; si es 0 se aplican todas.
    Los pares de consistencia siempre se incluyen juntos.
    Guarda IDs en evaluacion.preguntas_seleccionadas.
    """
    seleccionadas_ids = []

    pruebas = Prueba.objects.filter(activa=True).prefetch_related('preguntas')
    for prueba in pruebas:
        preguntas = list(prueba.preguntas.all())
        n_aplicar = prueba.items_a_aplicar

        if n_aplicar == 0 or n_aplicar >= len(preguntas):
            # Aplicar todas
            seleccionadas_ids.extend([p.id for p in preguntas])
            continue

        # Identify consistency pairs that must be included together
        pares_obligatorios = set()
        for p in preguntas:
            if p.par_consistencia_id is not None:
                pares_obligatorios.add(p.id)
                pares_obligatorios.add(p.par_consistencia_id)

        # Start with mandatory pair questions that belong to this prueba
        pares_en_prueba = [p for p in preguntas if p.id in pares_obligatorios]
        resto = [p for p in preguntas if p.id not in pares_obligatorios]

        seleccion = list(pares_en_prueba)
        faltan = n_aplicar - len(seleccion)

        if faltan > 0:
            # Balance by dimension
            por_dimension = defaultdict(list)
            for p in resto:
                por_dimension[p.dimension].append(p)

            # Shuffle within each dimension
            for dim_list in por_dimension.values():
                random.shuffle(dim_list)

            # Round-robin selection across dimensions
            dims = list(por_dimension.keys())
            random.shuffle(dims)
            idx = 0
            while faltan > 0 and any(por_dimension[d] for d in dims):
                dim = dims[idx % len(dims)]
                if por_dimension[dim]:
                    seleccion.append(por_dimension[dim].pop())
                    faltan -= 1
                idx += 1

        seleccionadas_ids.extend([p.id for p in seleccion])

    evaluacion.preguntas_seleccionadas = seleccionadas_ids
    evaluacion.save(update_fields=['preguntas_seleccionadas'])
    return seleccionadas_ids
