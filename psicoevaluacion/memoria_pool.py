"""
Pool de secuencias para la prueba de Memoria.

Fuente única de verdad usada tanto por el comando de seed (`seed_pruebas`)
como por la migración de datos (`0008_memoria_pool`).

Diseño:
- 10 niveles de dificultad creciente (3 → 7 números).
- Cada nivel es una `dimension` distinta (MEM_N01..MEM_N10) con 5 variantes.
- `Prueba.items_a_aplicar = 10` hace que `seleccionar_preguntas_evaluacion`
  (round-robin por dimensión) tome exactamente UNA variante aleatoria por nivel.
- La mecánica es "memoriza y repite": lo que se muestra es lo que se teclea.
- Los niveles altos (N07-N10) incluyen números de dos cifras.
"""

# Cada nivel: (dimension, orden, texto, [5 secuencias])
MEMORIA_POOL = [
    ('MEM_N01', 1,
     "Memoriza la siguiente secuencia de 3 números y escríbela en el mismo orden.",
     [[4, 7, 2], [9, 1, 5], [3, 8, 6], [2, 5, 9], [7, 4, 1]]),

    ('MEM_N02', 2,
     "Memoriza la siguiente secuencia de 4 números y escríbela en el mismo orden.",
     [[8, 3, 1, 6], [2, 7, 4, 9], [5, 1, 8, 3], [6, 2, 9, 4], [1, 5, 7, 2]]),

    ('MEM_N03', 3,
     "Memoriza la siguiente secuencia de 4 números y escríbela en el mismo orden.",
     [[3, 9, 5, 1], [7, 2, 6, 8], [4, 8, 1, 5], [9, 6, 3, 7], [2, 4, 8, 6]]),

    ('MEM_N04', 4,
     "Memoriza la siguiente secuencia de 5 números y escríbela en el mismo orden.",
     [[5, 9, 2, 7, 4], [1, 6, 3, 8, 2], [7, 4, 9, 1, 5], [3, 8, 6, 2, 9],
      [6, 1, 4, 7, 3]]),

    ('MEM_N05', 5,
     "Memoriza la siguiente secuencia de 5 números y escríbela en el mismo orden.",
     [[2, 7, 5, 9, 1], [8, 3, 6, 1, 4], [4, 9, 2, 6, 8], [1, 5, 7, 3, 9],
      [6, 2, 8, 4, 7]]),

    ('MEM_N06', 6,
     "Memoriza la siguiente secuencia de 6 números y escríbela en el mismo orden.",
     [[3, 8, 1, 6, 2, 9], [7, 2, 5, 9, 4, 1], [5, 1, 8, 3, 7, 6], [9, 4, 2, 7, 1, 5],
      [2, 6, 9, 4, 8, 3]]),

    # --- Niveles altos: incluyen números de dos cifras (ejercitan el campo ancho) ---
    ('MEM_N07', 7,
     "Memoriza la siguiente secuencia y escríbela en el mismo orden. Incluye números de dos cifras.",
     [[7, 3, 14, 5, 2], [4, 21, 6, 1, 8], [12, 5, 9, 3, 7], [6, 1, 18, 4, 2],
      [3, 16, 8, 5, 1]]),

    ('MEM_N08', 8,
     "Memoriza la siguiente secuencia y escríbela en el mismo orden. Incluye números de dos cifras.",
     [[7, 3, 14, 5, 2, 9], [4, 21, 6, 1, 8, 3], [12, 5, 9, 3, 17, 1], [6, 1, 18, 4, 2, 7],
      [3, 16, 8, 5, 1, 24]]),

    ('MEM_N09', 9,
     "Memoriza la siguiente secuencia y escríbela en el mismo orden. Incluye números de dos cifras.",
     [[15, 3, 22, 6, 1, 9], [4, 18, 6, 13, 8, 2], [12, 5, 27, 3, 7, 1], [6, 21, 1, 4, 19, 8],
      [9, 16, 8, 25, 1, 3]]),

    ('MEM_N10', 10,
     "Memoriza la siguiente secuencia y escríbela en el mismo orden. Incluye números de dos cifras.",
     [[8, 15, 3, 22, 6, 1, 9], [4, 18, 6, 13, 8, 27, 2], [12, 5, 21, 3, 17, 1, 9],
      [6, 24, 1, 14, 8, 2, 19], [3, 16, 28, 5, 11, 7, 1]]),
]


def sync_memoria_pool(Prueba, Pregunta):
    """
    Sincroniza las preguntas de la prueba de Memoria con MEMORIA_POOL.

    Idempotente y no destructivo:
    - Reutiliza preguntas existentes in situ (preserva sus IDs y, por tanto,
      las RespuestaMemoria históricas que las referencian via FK CASCADE).
    - Crea las preguntas faltantes.
    - Nunca borra (las respuestas históricas guardan su propio snapshot, así que
      reescribir la secuencia de una pregunta no las corrompe).
    - Fija items_a_aplicar=10 para que se seleccione una variante por nivel.

    Recibe los modelos como parámetros para ser compatible con los modelos
    históricos de apps.get_model() dentro de migraciones.
    """
    prueba = Prueba.objects.filter(tipo='MEMORIA').first()
    if not prueba:
        return

    desired = [
        (dim, orden, texto, seq)
        for dim, orden, texto, seqs in MEMORIA_POOL
        for seq in seqs
    ]
    existing = list(Pregunta.objects.filter(prueba=prueba).order_by('orden', 'id'))

    for i, (dim, orden, texto, seq) in enumerate(desired):
        if i < len(existing):
            q = existing[i]
            q.dimension = dim
            q.orden = orden
            q.texto = texto
            q.secuencia_correcta = seq
            q.tipo_escala = 'SECUENCIA'
            q.save()
        else:
            Pregunta.objects.create(
                prueba=prueba,
                dimension=dim,
                orden=orden,
                texto=texto,
                secuencia_correcta=seq,
                tipo_escala='SECUENCIA',
            )

    prueba.items_a_aplicar = 10
    prueba.save()
