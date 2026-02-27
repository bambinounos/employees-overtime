from django.core.management.base import BaseCommand

from psicoevaluacion.models import Prueba, Pregunta, Opcion, PerfilObjetivo


class Command(BaseCommand):
    help = 'Carga el banco completo de pruebas psicológicas v2 (~346 preguntas + opciones)'

    def handle(self, *args, **options):
        self.stdout.write('Cargando banco de pruebas psicológicas v2...')

        # Crear perfil objetivo por defecto
        PerfilObjetivo.objects.get_or_create(
            nombre="Perfil Estándar",
            defaults={'activo': True},
        )

        self._seed_bigfive()
        self._seed_compromiso()
        self._seed_obediencia()
        self._seed_memoria()
        self._seed_matrices()
        self._seed_arbol()
        self._seed_persona_lluvia()
        self._seed_frases()
        self._seed_colores()
        self._seed_situacional()
        self._seed_deseabilidad()

        self._vincular_pares_consistencia()
        self._actualizar_banco_metadata()

        total_preguntas = Pregunta.objects.count()
        total_opciones = Opcion.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'Banco v2 cargado: {total_preguntas} preguntas, {total_opciones} opciones'
        ))

    # ──────────────────────────────────────────────
    # LIKERT 1-5 helper
    # ──────────────────────────────────────────────
    def _crear_opciones_likert5(self, pregunta):
        opciones = [
            ("Totalmente en desacuerdo", 1),
            ("En desacuerdo", 2),
            ("Ni de acuerdo ni en desacuerdo", 3),
            ("De acuerdo", 4),
            ("Totalmente de acuerdo", 5),
        ]
        for i, (texto, valor) in enumerate(opciones):
            Opcion.objects.get_or_create(
                pregunta=pregunta, valor=valor,
                defaults={'texto': texto, 'orden': i},
            )

    # ──────────────────────────────────────────────
    # 1. BIG FIVE (120 ítems — 24 por dimensión)
    # ──────────────────────────────────────────────
    def _seed_bigfive(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='BIGFIVE',
            defaults={
                'nombre': 'Test de Personalidad Big Five (OCEAN)',
                'descripcion': 'Evalúa los 5 grandes rasgos de personalidad: '
                               'Responsabilidad, Amabilidad, Neuroticismo, Apertura y Extroversión.',
                'instrucciones': (
                    'A continuación encontrará una serie de afirmaciones sobre comportamientos '
                    'y actitudes. Indique qué tan de acuerdo está con cada una usando la escala '
                    'de 1 (Totalmente en desacuerdo) a 5 (Totalmente de acuerdo). '
                    'No hay respuestas correctas o incorrectas; responda con sinceridad.'
                ),
                'orden': 1,
                'activa': True,
                'es_proyectiva': False,
            },
        )

        items = [
            # ── Responsabilidad (BF_RESP) — v1: 7 directos + 3 inversos ──
            ("Siempre termino lo que empiezo, sin importar cuánto tiempo me tome.", 'BF_RESP', False),
            ("Me resulta imposible ir a dormir si tengo tareas pendientes.", 'BF_RESP', False),
            ("Soy muy organizado/a con mi agenda y mis compromisos.", 'BF_RESP', False),
            ("Prefiero quedarme hasta tarde trabajando que dejar algo incompleto.", 'BF_RESP', False),
            ("Reviso mi trabajo varias veces antes de entregarlo.", 'BF_RESP', False),
            ("Planifico mis actividades con anticipación para no dejar nada al azar.", 'BF_RESP', False),
            ("Cumplo mis promesas y compromisos aunque me cueste esfuerzo.", 'BF_RESP', False),
            ("A veces dejo las cosas para el último momento.", 'BF_RESP', True),
            ("Me cuesta mantener el orden en mi espacio de trabajo.", 'BF_RESP', True),
            ("Suelo olvidar tareas que me asignaron si no las anoto.", 'BF_RESP', True),
            # v2: +14 nuevos
            ("Me fijo metas claras y las cumplo de manera consistente.", 'BF_RESP', False),
            ("Cuando asumo un compromiso, lo cumplo sin excusas.", 'BF_RESP', False),
            ("Llevo un control detallado de mis pendientes y prioridades.", 'BF_RESP', False),
            ("Me esfuerzo por entregar un trabajo de calidad en todo momento.", 'BF_RESP', False),
            ("Antes de actuar, evalúo las consecuencias de mis decisiones.", 'BF_RESP', False),
            ("Me considero una persona disciplinada y constante.", 'BF_RESP', False),
            ("Cuando prometo algo, muevo cielo y tierra para cumplirlo.", 'BF_RESP', False),
            ("Presto atención a los detalles en todo lo que hago.", 'BF_RESP', False),
            ("Suelo improvisar en lugar de planificar.", 'BF_RESP', True),
            ("Me aburro rápidamente de las tareas rutinarias y las abandono.", 'BF_RESP', True),
            ("Frecuentemente me distraigo con cosas que no son prioritarias.", 'BF_RESP', True),
            ("No suelo revisar mi trabajo una vez que lo termino.", 'BF_RESP', True),
            ("A veces prometo cosas que sé que no podré cumplir.", 'BF_RESP', True),
            ("Me cuesta establecer un orden de prioridades.", 'BF_RESP', True),

            # ── Amabilidad (BF_AMAB) — v1: 7 directos + 3 inversos ──
            ("Me preocupo genuinamente por el bienestar de mis compañeros.", 'BF_AMAB', False),
            ("Disfruto ayudando a otros aunque no me lo pidan.", 'BF_AMAB', False),
            ("Trato de ver las cosas desde la perspectiva de los demás.", 'BF_AMAB', False),
            ("Soy paciente cuando alguien necesita que le explique algo varias veces.", 'BF_AMAB', False),
            ("Prefiero ceder en una discusión antes que generar conflicto.", 'BF_AMAB', False),
            ("Me resulta fácil perdonar los errores de otros.", 'BF_AMAB', False),
            ("Hago un esfuerzo por ser amable incluso cuando estoy estresado/a.", 'BF_AMAB', False),
            ("Si alguien me cae mal, me cuesta disimularlo.", 'BF_AMAB', True),
            ("A veces soy demasiado directo/a y puedo herir sentimientos.", 'BF_AMAB', True),
            ("Me irrita cuando las personas son lentas para entender.", 'BF_AMAB', True),
            # v2: +14 nuevos
            ("Trato a todas las personas con respeto independientemente de su cargo.", 'BF_AMAB', False),
            ("Me resulta fácil ponerme en el lugar de otro.", 'BF_AMAB', False),
            ("Evito los chismes y los comentarios negativos sobre otros.", 'BF_AMAB', False),
            ("Cuando alguien está triste, trato de animarlo.", 'BF_AMAB', False),
            ("Soy tolerante con las diferencias de opinión.", 'BF_AMAB', False),
            ("Prefiero construir puentes que ganar discusiones.", 'BF_AMAB', False),
            ("Valoro la armonía en el grupo por encima de tener la razón.", 'BF_AMAB', False),
            ("Reconozco el mérito de los demás sin sentir envidia.", 'BF_AMAB', False),
            ("Me cuesta pedir disculpas aunque sepa que me equivoqué.", 'BF_AMAB', True),
            ("A veces ignoro las necesidades de otros cuando estoy concentrado en lo mío.", 'BF_AMAB', True),
            ("Tiendo a juzgar rápidamente a las personas.", 'BF_AMAB', True),
            ("Me resulta difícil confiar en las intenciones de los demás.", 'BF_AMAB', True),
            ("Cuando alguien me molesta, le doy la espalda en lugar de resolver la situación.", 'BF_AMAB', True),
            ("Me cuesta trabajar con personas que piensan diferente a mí.", 'BF_AMAB', True),

            # ── Neuroticismo (BF_NEUR) — v1: 7 directos + 3 inversos ──
            ("Me preocupo frecuentemente por cosas que podrían salir mal.", 'BF_NEUR', False),
            ("Me cuesta controlar mis emociones cuando estoy bajo presión.", 'BF_NEUR', False),
            ("Pequeños problemas pueden arruinarme el día.", 'BF_NEUR', False),
            ("Suelo sentirme ansioso/a sin una razón clara.", 'BF_NEUR', False),
            ("Me tomo los comentarios negativos de forma muy personal.", 'BF_NEUR', False),
            ("Cambio de humor con facilidad a lo largo del día.", 'BF_NEUR', False),
            ("Me cuesta recuperarme emocionalmente después de un fracaso.", 'BF_NEUR', False),
            ("Mantengo la calma fácilmente en situaciones difíciles.", 'BF_NEUR', True),
            ("Raramente me siento triste o deprimido/a.", 'BF_NEUR', True),
            ("Las críticas no me afectan demasiado.", 'BF_NEUR', True),
            # v2: +14 nuevos
            ("Me altero con facilidad cuando las cosas no salen como esperaba.", 'BF_NEUR', False),
            ("Tiendo a anticipar lo peor en situaciones inciertas.", 'BF_NEUR', False),
            ("Cuando cometo un error, me castigo mentalmente durante días.", 'BF_NEUR', False),
            ("Me cuesta conciliar el sueño cuando tengo preocupaciones.", 'BF_NEUR', False),
            ("Reacciono de forma exagerada ante situaciones menores.", 'BF_NEUR', False),
            ("Me siento fácilmente abrumado/a por las responsabilidades.", 'BF_NEUR', False),
            ("La incertidumbre me genera mucha ansiedad.", 'BF_NEUR', False),
            ("Me cuesta dejar de pensar en los problemas del trabajo cuando llego a casa.", 'BF_NEUR', False),
            ("Me considero una persona emocionalmente estable.", 'BF_NEUR', True),
            ("Sé manejar la frustración sin que afecte mi rendimiento.", 'BF_NEUR', True),
            ("Puedo separar los problemas personales de los laborales.", 'BF_NEUR', True),
            ("Me recupero rápidamente de los contratiempos.", 'BF_NEUR', True),
            ("No suelo sentir culpa por cosas que escapan a mi control.", 'BF_NEUR', True),
            ("Me siento seguro/a de mí mismo/a la mayor parte del tiempo.", 'BF_NEUR', True),

            # ── Apertura (BF_APER) — v1: 7 directos + 3 inversos ──
            ("Disfruto aprendiendo cosas nuevas aunque no estén relacionadas con mi trabajo.", 'BF_APER', False),
            ("Me gusta explorar formas diferentes de hacer las cosas.", 'BF_APER', False),
            ("Tengo curiosidad por culturas y puntos de vista diferentes al mío.", 'BF_APER', False),
            ("Prefiero actividades que me desafíen intelectualmente.", 'BF_APER', False),
            ("Me considero una persona creativa e imaginativa.", 'BF_APER', False),
            ("Leo o investigo sobre temas variados por iniciativa propia.", 'BF_APER', False),
            ("Estoy abierto/a a cambiar de opinión si me presentan buenos argumentos.", 'BF_APER', False),
            ("Prefiero las rutinas predecibles a los cambios constantes.", 'BF_APER', True),
            ("No me interesa mucho el arte o la cultura.", 'BF_APER', True),
            ("Me siento incómodo/a cuando las cosas no se hacen de la forma habitual.", 'BF_APER', True),
            # v2: +14 nuevos
            ("Busco activamente nuevas experiencias y aprendizajes.", 'BF_APER', False),
            ("Me entusiasman los proyectos que requieren pensar fuera de lo convencional.", 'BF_APER', False),
            ("Me gusta cuestionar las suposiciones y buscar nuevas soluciones.", 'BF_APER', False),
            ("Disfruto de las conversaciones profundas sobre temas abstractos.", 'BF_APER', False),
            ("Me adapto con facilidad a los cambios en mi entorno.", 'BF_APER', False),
            ("Considero que la innovación es fundamental para el progreso.", 'BF_APER', False),
            ("Me gusta probar métodos nuevos antes de descartarlos.", 'BF_APER', False),
            ("Disfruto resolviendo problemas que no tienen una respuesta obvia.", 'BF_APER', False),
            ("Prefiero lo seguro y conocido a arriesgarme con algo nuevo.", 'BF_APER', True),
            ("No me gusta que cambien los procesos que ya conozco.", 'BF_APER', True),
            ("Me cuesta aceptar ideas que son muy diferentes a las mías.", 'BF_APER', True),
            ("Rara vez busco información nueva por cuenta propia.", 'BF_APER', True),
            ("Las discusiones filosóficas me parecen una pérdida de tiempo.", 'BF_APER', True),
            ("Me resulta difícil imaginar formas distintas de hacer mi trabajo.", 'BF_APER', True),

            # ── Extroversión (BF_EXTR) — v1: 7 directos + 3 inversos ──
            ("Me siento cómodo/a iniciando conversaciones con personas nuevas.", 'BF_EXTR', False),
            ("Disfruto trabajar en equipo más que solo/a.", 'BF_EXTR', False),
            ("En reuniones sociales tiendo a ser el centro de atención.", 'BF_EXTR', False),
            ("Me recargo de energía al estar rodeado de personas.", 'BF_EXTR', False),
            ("Suelo tomar la iniciativa en actividades grupales.", 'BF_EXTR', False),
            ("Me gusta conocer gente nueva y ampliar mi círculo social.", 'BF_EXTR', False),
            ("Soy una persona entusiasta y expresiva.", 'BF_EXTR', False),
            ("Prefiero trabajar solo/a que en equipo.", 'BF_EXTR', True),
            ("Me cuesta hablar frente a un grupo grande de personas.", 'BF_EXTR', True),
            ("Necesito tiempo a solas para recargar energía después de socializar.", 'BF_EXTR', True),
            # v2: +14 nuevos
            ("Me resulta fácil hacer amigos en ambientes nuevos.", 'BF_EXTR', False),
            ("Disfruto participar activamente en reuniones de trabajo.", 'BF_EXTR', False),
            ("Me gusta organizar actividades sociales para mis compañeros.", 'BF_EXTR', False),
            ("Transmito entusiasmo y motivación a quienes me rodean.", 'BF_EXTR', False),
            ("No me incomoda ser el primero en hablar en una reunión.", 'BF_EXTR', False),
            ("Me siento más productivo/a cuando trabajo rodeado de personas.", 'BF_EXTR', False),
            ("Suelo ser quien anima el ambiente en el grupo.", 'BF_EXTR', False),
            ("Expreso mis opiniones con confianza en cualquier situación.", 'BF_EXTR', False),
            ("Evito las situaciones sociales cuando puedo.", 'BF_EXTR', True),
            ("Me siento incómodo/a al ser el centro de atención.", 'BF_EXTR', True),
            ("Me cuesta expresar mis ideas de forma espontánea.", 'BF_EXTR', True),
            ("Prefiero comunicarme por escrito que en persona.", 'BF_EXTR', True),
            ("Las conversaciones triviales me resultan agotadoras.", 'BF_EXTR', True),
            ("Me cuesta mantener conversaciones largas con personas que no conozco.", 'BF_EXTR', True),
        ]

        for i, (texto, dimension, es_inversa) in enumerate(items):
            preg, created = Pregunta.objects.get_or_create(
                prueba=prueba, texto=texto,
                defaults={
                    'tipo_escala': 'LIKERT5',
                    'dimension': dimension,
                    'es_inversa': es_inversa,
                    'orden': i + 1,
                },
            )
            if created:
                self._crear_opciones_likert5(preg)

        self.stdout.write(f'  Big Five: {len(items)} ítems')

    # ──────────────────────────────────────────────
    # 2. COMPROMISO ORGANIZACIONAL (48 ítems)
    # ──────────────────────────────────────────────
    def _seed_compromiso(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='COMPROMISO',
            defaults={
                'nombre': 'Compromiso Organizacional (Allen & Meyer)',
                'descripcion': 'Evalúa tres dimensiones del compromiso: afectivo, de continuidad y normativo.',
                'instrucciones': (
                    'Piense en su relación ideal con una empresa. Indique qué tan de acuerdo '
                    'está con cada afirmación usando la escala de 1 a 5.'
                ),
                'orden': 2,
                'activa': True,
                'es_proyectiva': False,
            },
        )

        items = [
            # ── Afectivo (CO_AFEC) — v1: 6 directos + 2 inversos ──
            ("Me sentiría culpable si dejara mi empresa en un momento difícil.", 'CO_AFEC', False),
            ("Siento un fuerte sentido de pertenencia hacia la empresa donde trabajo.", 'CO_AFEC', False),
            ("Los problemas de mi empresa los siento como propios.", 'CO_AFEC', False),
            ("Me siento emocionalmente unido/a a mi lugar de trabajo.", 'CO_AFEC', False),
            ("Trabajar en mi empresa tiene un gran significado personal para mí.", 'CO_AFEC', False),
            ("Siento orgullo de decir que trabajo en mi empresa.", 'CO_AFEC', False),
            ("No me siento como parte de una familia en mi trabajo.", 'CO_AFEC', True),
            ("No tengo un fuerte apego emocional a mi empresa.", 'CO_AFEC', True),
            # v2: +8 nuevos
            ("Disfruto hablar con otros sobre mi empresa.", 'CO_AFEC', False),
            ("Me alegra cuando mi empresa logra sus objetivos.", 'CO_AFEC', False),
            ("Siento que mi empresa se preocupa por mi bienestar.", 'CO_AFEC', False),
            ("Los valores de mi empresa coinciden con los míos.", 'CO_AFEC', False),
            ("Me siento motivado/a al empezar mi jornada laboral.", 'CO_AFEC', False),
            ("Me identifico profundamente con la misión de mi empresa.", 'CO_AFEC', False),
            ("Me da igual si mi empresa tiene éxito o no.", 'CO_AFEC', True),
            ("No siento ninguna emoción especial cuando pienso en mi trabajo.", 'CO_AFEC', True),

            # ── Continuidad (CO_CONT) — v1: 6 directos + 2 inversos ──
            ("Cambiar de trabajo significaría un gran sacrificio personal para mí.", 'CO_CONT', False),
            ("Permanezco en mi empresa porque necesito el ingreso y los beneficios.", 'CO_CONT', False),
            ("Si dejara mi empresa, pocas alternativas serían tan buenas.", 'CO_CONT', False),
            ("Mucho de mi vida se vería afectada si decidiera dejar mi empresa ahora.", 'CO_CONT', False),
            ("Sería muy difícil para mí dejar mi empresa aunque quisiera.", 'CO_CONT', False),
            ("He invertido demasiado tiempo y esfuerzo en mi empresa como para irme.", 'CO_CONT', False),
            ("Si quisiera, podría encontrar fácilmente otro trabajo igual o mejor.", 'CO_CONT', True),
            ("Irme de mi empresa no me causaría ninguna dificultad importante.", 'CO_CONT', True),
            # v2: +8 nuevos
            ("Mis beneficios actuales son difíciles de igualar en otra empresa.", 'CO_CONT', False),
            ("Tengo demasiadas cosas en juego como para dejar mi empleo.", 'CO_CONT', False),
            ("El costo personal de cambiar de empresa sería muy alto.", 'CO_CONT', False),
            ("Mi experiencia en esta empresa no se trasladaría fácilmente a otra.", 'CO_CONT', False),
            ("Perder mi antigüedad sería un gran retroceso para mí.", 'CO_CONT', False),
            ("Dependo de los beneficios que me ofrece esta empresa.", 'CO_CONT', False),
            ("Cambiar de empresa no me representaría ningún riesgo importante.", 'CO_CONT', True),
            ("Podría adaptarme a cualquier nuevo empleo sin problemas.", 'CO_CONT', True),

            # ── Normativo (CO_NORM) — v1: 6 directos + 2 inversos ──
            ("Creo que una persona debe ser leal a su organización.", 'CO_NORM', False),
            ("Cambiar de empresa frecuentemente me parece irresponsable.", 'CO_NORM', False),
            ("Le debo mucho a mi empresa y sería injusto irme.", 'CO_NORM', False),
            ("Siento la obligación moral de permanecer en mi empresa.", 'CO_NORM', False),
            ("Mi empresa merece mi lealtad por todo lo que me ha dado.", 'CO_NORM', False),
            ("Es mejor permanecer en una empresa que andar saltando de trabajo en trabajo.", 'CO_NORM', False),
            ("No creo que estar comprometido con una sola empresa sea algo importante.", 'CO_NORM', True),
            ("Si encuentro una mejor oferta, no dudaría en irme sin mirar atrás.", 'CO_NORM', True),
            # v2: +8 nuevos
            ("Siento gratitud hacia mi empresa por las oportunidades que me ha dado.", 'CO_NORM', False),
            ("Creo que es mi deber dar lo mejor de mí en mi empresa.", 'CO_NORM', False),
            ("La lealtad a la empresa es un valor que me inculcaron desde siempre.", 'CO_NORM', False),
            ("Me sentiría mal conmigo mismo/a si abandonara a mi equipo.", 'CO_NORM', False),
            ("Creo que uno debe quedarse en su empresa hasta completar un ciclo.", 'CO_NORM', False),
            ("Es importante retribuir a la empresa que confió en mí.", 'CO_NORM', False),
            ("La lealtad laboral es un concepto anticuado que ya no aplica.", 'CO_NORM', True),
            ("No le debo nada a mi empresa más allá de mi trabajo diario.", 'CO_NORM', True),
        ]

        for i, (texto, dimension, es_inversa) in enumerate(items):
            preg, created = Pregunta.objects.get_or_create(
                prueba=prueba, texto=texto,
                defaults={
                    'tipo_escala': 'LIKERT5',
                    'dimension': dimension,
                    'es_inversa': es_inversa,
                    'orden': i + 1,
                },
            )
            if created:
                self._crear_opciones_likert5(preg)

        self.stdout.write(f'  Compromiso: {len(items)} ítems')

    # ──────────────────────────────────────────────
    # 3. OBEDIENCIA Y CONFORMIDAD (40 ítems)
    # ──────────────────────────────────────────────
    def _seed_obediencia(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='OBEDIENCIA',
            defaults={
                'nombre': 'Escala de Obediencia y Conformidad',
                'descripcion': 'Evalúa disciplina, conformidad normativa y orientación a la autoridad.',
                'instrucciones': (
                    'Indique qué tan de acuerdo está con cada afirmación sobre su actitud '
                    'hacia las reglas, instrucciones y figuras de autoridad.'
                ),
                'orden': 3,
                'activa': True,
                'es_proyectiva': False,
            },
        )

        items = [
            # ── Disciplina (OB_DISC) — v1: 7 ítems ──
            ("Siempre llego puntual a mis compromisos laborales.", 'OB_DISC', False),
            ("Cumplo con los plazos establecidos sin necesidad de que me lo recuerden.", 'OB_DISC', False),
            ("Sigo los procedimientos paso a paso, sin saltarme ninguno.", 'OB_DISC', False),
            ("Mantengo mi área de trabajo ordenada y organizada.", 'OB_DISC', False),
            ("Respeto estrictamente los horarios de entrada y salida.", 'OB_DISC', False),
            ("No inicio una tarea nueva sin haber completado la anterior.", 'OB_DISC', False),
            ("Considero que la disciplina es una de mis principales cualidades.", 'OB_DISC', False),
            # v2: +7 nuevos
            ("Me preparo con anticipación para las reuniones y compromisos.", 'OB_DISC', False),
            ("Llevo un registro ordenado de mis actividades diarias.", 'OB_DISC', False),
            ("No necesito supervisión constante para mantener mi productividad.", 'OB_DISC', False),
            ("Cuando hay un plazo, lo cumplo sin necesidad de recordatorios.", 'OB_DISC', False),
            ("A veces llego tarde porque subestimo el tiempo de traslado.", 'OB_DISC', True),
            ("Me cuesta mantener una rutina constante de trabajo.", 'OB_DISC', True),
            ("En ocasiones me salto pasos de un procedimiento para ahorrar tiempo.", 'OB_DISC', True),

            # ── Conformidad normativa (OB_CONF) — v1: 7 ítems ──
            ("Seguir las reglas es más importante que ser creativo.", 'OB_CONF', False),
            ("Las normas existen por una buena razón y deben respetarse.", 'OB_CONF', False),
            ("Prefiero seguir el protocolo establecido aunque parezca lento.", 'OB_CONF', False),
            ("Me siento incómodo/a cuando veo a alguien romper las reglas.", 'OB_CONF', False),
            ("Respeto las políticas de la empresa aunque no esté de acuerdo con todas.", 'OB_CONF', False),
            ("Creo que la estabilidad organizacional depende de que todos sigan las normas.", 'OB_CONF', False),
            ("Me adapto rápidamente a nuevos reglamentos sin cuestionarlos.", 'OB_CONF', False),
            # v2: +7 nuevos
            ("Considero que las reglas aplican para todos por igual, incluido yo.", 'OB_CONF', False),
            ("Cuando no entiendo una norma, busco su razón antes de criticarla.", 'OB_CONF', False),
            ("Me parece importante que todos cumplan las mismas reglas.", 'OB_CONF', False),
            ("Creo que un equipo funciona mejor cuando hay reglas claras.", 'OB_CONF', False),
            ("A veces pienso que las reglas limitan más de lo que ayudan.", 'OB_CONF', True),
            ("No me importa saltarme una norma si el resultado es mejor.", 'OB_CONF', True),
            ("Creo que muchas reglas en el trabajo son innecesarias.", 'OB_CONF', True),

            # ── Orientación a autoridad (OB_AUTO) — v1: 6 ítems ──
            ("Si mi jefe me da una instrucción, la cumplo aunque no esté de acuerdo.", 'OB_AUTO', False),
            ("Prefiero que me digan exactamente qué hacer a improvisar.", 'OB_AUTO', False),
            ("Respeto la jerarquía y la cadena de mando en el trabajo.", 'OB_AUTO', False),
            ("Confío en las decisiones de mis superiores aunque no las entienda completamente.", 'OB_AUTO', False),
            ("Cuando recibo una instrucción, la ejecuto de inmediato.", 'OB_AUTO', False),
            ("Me resulta natural aceptar la autoridad de mis jefes.", 'OB_AUTO', False),
            # v2: +6 nuevos
            ("Valoro la experiencia y criterio de mis superiores.", 'OB_AUTO', False),
            ("Sigo la cadena de mando antes de tomar decisiones por mi cuenta.", 'OB_AUTO', False),
            ("Me siento cómodo/a recibiendo instrucciones directas.", 'OB_AUTO', False),
            ("Creo que la figura del jefe es necesaria para la organización.", 'OB_AUTO', False),
            ("Tiendo a cuestionar las decisiones de mis superiores abiertamente.", 'OB_AUTO', True),
            ("Prefiero tomar mis propias decisiones sin consultar a mi jefe.", 'OB_AUTO', True),
        ]

        for i, (texto, dimension, es_inversa) in enumerate(items):
            preg, created = Pregunta.objects.get_or_create(
                prueba=prueba, texto=texto,
                defaults={
                    'tipo_escala': 'LIKERT5',
                    'dimension': dimension,
                    'es_inversa': es_inversa,
                    'orden': i + 1,
                },
            )
            if created:
                self._crear_opciones_likert5(preg)

        self.stdout.write(f'  Obediencia: {len(items)} ítems')

    # ──────────────────────────────────────────────
    # 4. TEST DE MEMORIA (10 niveles — sin cambio)
    # ──────────────────────────────────────────────
    def _seed_memoria(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='MEMORIA',
            defaults={
                'nombre': 'Test de Memoria de Trabajo',
                'descripcion': 'Evalúa capacidad de retener y reproducir secuencias de información.',
                'instrucciones': (
                    'Se le presentará una secuencia de números o instrucciones. '
                    'Observe con atención y luego reprodúzcala exactamente como la vio. '
                    'La dificultad irá aumentando progresivamente.'
                ),
                'orden': 4,
                'activa': True,
                'es_proyectiva': False,
            },
        )

        niveles = [
            (1, "Repita la siguiente secuencia de 3 dígitos en el mismo orden.", [4, 7, 2]),
            (2, "Repita la siguiente secuencia de 4 dígitos en el mismo orden.", [8, 3, 1, 6]),
            (3, "Repita la siguiente secuencia de 5 dígitos en el mismo orden.", [5, 9, 2, 7, 4]),
            (4, "Repita la siguiente secuencia de 3 dígitos en orden INVERSO.", [6, 1, 8]),
            (5, "Repita la siguiente secuencia de 4 dígitos en orden INVERSO.", [3, 7, 4, 9]),
            (6, "Repita la siguiente secuencia de 5 dígitos en orden INVERSO.", [2, 5, 8, 1, 6]),
            (7, "Siga estas instrucciones en orden: Escriba el número 3, luego el 7, luego el 1.",
             [3, 7, 1]),
            (8, "Siga estas instrucciones: Primero 5, después 2, luego 8, finalmente 4.",
             [5, 2, 8, 4]),
            (9, "Siga estas instrucciones: Escriba 9, después 3, luego 6, después 1, finalmente 7.",
             [9, 3, 6, 1, 7]),
            (10, "Instrucción compleja: Escriba el 4, duplíquelo (8), reste 3 (5), "
                 "agregue el primer número (4), luego escriba la suma total (21), "
                 "y finalmente el número de pasos (6).",
             [4, 8, 5, 4, 21, 6]),
        ]

        for orden, texto, secuencia in niveles:
            Pregunta.objects.get_or_create(
                prueba=prueba, texto=texto,
                defaults={
                    'tipo_escala': 'SECUENCIA',
                    'dimension': 'GENERAL',
                    'orden': orden,
                    'secuencia_correcta': secuencia,
                },
            )

        self.stdout.write(f'  Memoria: {len(niveles)} niveles')

    # ──────────────────────────────────────────────
    # 5. MATRICES PROGRESIVAS (30 preguntas)
    # ──────────────────────────────────────────────
    def _seed_matrices(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='MATRICES',
            defaults={
                'nombre': 'Matrices Progresivas',
                'descripcion': 'Evalúa razonamiento lógico y capacidad de identificar patrones.',
                'instrucciones': (
                    'En cada pregunta verá un patrón con una pieza faltante. '
                    'Seleccione la opción que completa correctamente el patrón. '
                    'Tiene 20 minutos para completar esta sección.'
                ),
                'tiempo_limite_minutos': 20,
                'orden': 5,
                'activa': True,
                'es_proyectiva': False,
            },
        )

        matrices = [
            # v1: 20 preguntas
            (1, "Patrón: Círculo, Cuadrado, Triángulo, Círculo, Cuadrado, ?",
             [("Triángulo", 1), ("Círculo", 0), ("Pentágono", 0), ("Rombo", 0)]),
            (2, "Patrón: 2, 4, 8, 16, ?",
             [("32", 1), ("24", 0), ("20", 0), ("64", 0)]),
            (3, "Fila 1: ◼◼◻ | Fila 2: ◼◻◼ | Fila 3: ◻◼?",
             [("◼", 1), ("◻", 0), ("◼◼", 0), ("◻◻", 0)]),
            (4, "Secuencia: A1, B2, C3, D4, ?",
             [("E5", 1), ("D5", 0), ("E4", 0), ("F6", 0)]),
            (5, "Patrón de rotación: ↑ → ↓ ← ↑ → ↓ ?",
             [("←", 1), ("↑", 0), ("→", 0), ("↓", 0)]),
            (6, "Suma de filas = 15: [5,7,3] [6,4,5] [4,?]",
             [("4,7", 1), ("5,6", 0), ("3,8", 0), ("6,5", 0)]),
            (7, "Patrón: ●○○ | ○●○ | ○○● | ?",
             [("●○○", 1), ("○●○", 0), ("○○●", 0), ("●●●", 0)]),
            (8, "Serie: 1, 1, 2, 3, 5, 8, ?",
             [("13", 1), ("11", 0), ("10", 0), ("15", 0)]),
            (9, "Fila 1: ▲▼▲ | Fila 2: ▼▲▼ | Fila 3: ▲▼?",
             [("▲", 1), ("▼", 0), ("▲▼", 0), ("▼▲", 0)]),
            (10, "Patrón: 3, 6, 12, 24, ?",
             [("48", 1), ("36", 0), ("30", 0), ("96", 0)]),
            (11, "Grilla 3x3 — cada fila tiene ●, ▲, ◼. Faltante en [3,3]: [●,▲,◼][▲,◼,●][◼,●,?]",
             [("▲", 1), ("●", 0), ("◼", 0), ("◻", 0)]),
            (12, "Serie: 100, 81, 64, 49, 36, ?",
             [("25", 1), ("16", 0), ("29", 0), ("30", 0)]),
            (13, "Patrón: AB, BC, CD, DE, ?",
             [("EF", 1), ("DF", 0), ("FG", 0), ("ED", 0)]),
            (14, "Secuencia visual: + se rota 45° cada paso. Después de 4 rotaciones: +, ×, +, ×, ?",
             [("+", 1), ("×", 0), ("-", 0), ("|", 0)]),
            (15, "Patrón numérico: 2,6 | 3,9 | 4,12 | 5,?",
             [("15", 1), ("14", 0), ("16", 0), ("10", 0)]),
            (16, "Grilla: Cada celda es la suma de las dos celdas superiores. Base [3,5,2]. Fila 2 [8,7]. Fila 3 [?]",
             [("15", 1), ("12", 0), ("17", 0), ("10", 0)]),
            (17, "Serie: Z, X, V, T, R, ?",
             [("P", 1), ("Q", 0), ("O", 0), ("N", 0)]),
            (18, "Patrón: 1² + 1 = 2, 2² + 1 = 5, 3² + 1 = 10, 4² + 1 = ?",
             [("17", 1), ("15", 0), ("16", 0), ("20", 0)]),
            (19, "Grilla lógica: Fila 1 [○,△,□] Fila 2 [□,○,△] Fila 3 [△,□,?]",
             [("○", 1), ("△", 0), ("□", 0), ("◇", 0)]),
            (20, "Doble patrón: (1,2)(2,4)(3,8)(4,16)(5,?)",
             [("32", 1), ("25", 0), ("20", 0), ("64", 0)]),
            # v2: +10 preguntas progresivas más difíciles
            (21, "Serie: 1, 4, 9, 16, 25, ?",
             [("36", 1), ("30", 0), ("49", 0), ("35", 0)]),
            (22, "Patrón: AA, AB, BA, BB, ?",
             [("AA", 1), ("AB", 0), ("BA", 0), ("CC", 0)]),
            (23, "Serie: 2, 3, 5, 7, 11, 13, ?",
             [("17", 1), ("15", 0), ("14", 0), ("19", 0)]),
            (24, "Patrón: 1, 3, 7, 15, 31, ?",
             [("63", 1), ("47", 0), ("62", 0), ("45", 0)]),
            (25, "Grilla: Cada fila suma 21. [7,8,6] [9,3,?] Faltante:",
             [("9", 1), ("7", 0), ("10", 0), ("8", 0)]),
            (26, "Serie: O, T, T, F, F, S, S, ?",
             [("E", 1), ("N", 0), ("T", 0), ("O", 0)]),
            (27, "Patrón numérico: (2,8)(3,27)(4,64)(5,?)",
             [("125", 1), ("100", 0), ("80", 0), ("150", 0)]),
            (28, "Serie de letras: B, D, G, K, ?",
             [("P", 1), ("N", 0), ("O", 0), ("M", 0)]),
            (29, "Patrón: 0, 1, 1, 2, 3, 5, 8, 13, 21, ?",
             [("34", 1), ("28", 0), ("32", 0), ("42", 0)]),
            (30, "Grilla lógica: [1,2,3][3,1,2][2,3,?]",
             [("1", 1), ("2", 0), ("3", 0), ("4", 0)]),
        ]

        for orden, texto, opciones_data in matrices:
            preg, created = Pregunta.objects.get_or_create(
                prueba=prueba, texto=texto,
                defaults={
                    'tipo_escala': 'OPCION_MULTIPLE',
                    'dimension': 'GENERAL',
                    'orden': orden,
                },
            )
            if created:
                for j, (opt_texto, opt_valor) in enumerate(opciones_data):
                    Opcion.objects.get_or_create(
                        pregunta=preg, texto=opt_texto,
                        defaults={'valor': opt_valor, 'orden': j},
                    )

        self.stdout.write(f'  Matrices: {len(matrices)} preguntas')

    # ──────────────────────────────────────────────
    # 6. TEST DEL ÁRBOL (sin cambio)
    # ──────────────────────────────────────────────
    def _seed_arbol(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='ARBOL',
            defaults={
                'nombre': 'Test del Árbol (Koch)',
                'descripcion': 'Prueba proyectiva gráfica que evalúa personalidad profunda y estabilidad emocional.',
                'instrucciones': (
                    'Dibuje un árbol como usted quiera. Puede usar el mouse o la pantalla táctil. '
                    'No hay respuestas correctas o incorrectas. Tómese el tiempo que necesite.'
                ),
                'orden': 6,
                'activa': True,
                'es_proyectiva': True,
            },
        )

        Pregunta.objects.get_or_create(
            prueba=prueba,
            texto="Dibuje un árbol como usted quiera.",
            defaults={
                'tipo_escala': 'TEXTO_LIBRE',
                'dimension': 'GENERAL',
                'orden': 1,
            },
        )

        self.stdout.write('  Árbol: 1 pregunta proyectiva')

    # ──────────────────────────────────────────────
    # 7. PERSONA BAJO LA LLUVIA (sin cambio)
    # ──────────────────────────────────────────────
    def _seed_persona_lluvia(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='PERSONA_LLUVIA',
            defaults={
                'nombre': 'Persona bajo la Lluvia',
                'descripcion': 'Prueba proyectiva que evalúa la reacción ante presión y estrés.',
                'instrucciones': (
                    'Dibuje una persona bajo la lluvia. Puede usar el mouse o la pantalla táctil. '
                    'No hay respuestas correctas o incorrectas. Tómese el tiempo que necesite.'
                ),
                'orden': 7,
                'activa': True,
                'es_proyectiva': True,
            },
        )

        Pregunta.objects.get_or_create(
            prueba=prueba,
            texto="Dibuje una persona bajo la lluvia.",
            defaults={
                'tipo_escala': 'TEXTO_LIBRE',
                'dimension': 'GENERAL',
                'orden': 1,
            },
        )

        self.stdout.write('  Persona bajo la Lluvia: 1 pregunta proyectiva')

    # ──────────────────────────────────────────────
    # 8. FRASES INCOMPLETAS DE SACKS (50 frases)
    # ──────────────────────────────────────────────
    def _seed_frases(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='FRASES',
            defaults={
                'nombre': 'Frases Incompletas (Sacks)',
                'descripcion': 'Revela actitudes profundas hacia trabajo, autoridad y compromiso personal.',
                'instrucciones': (
                    'Complete cada frase con lo primero que se le venga a la mente. '
                    'No hay respuestas correctas o incorrectas. Sea espontáneo/a y sincero/a.'
                ),
                'orden': 8,
                'activa': True,
                'es_proyectiva': True,
            },
        )

        frases = [
            # ── Actitud hacia el trabajo (FR_TRAB) — v1: 10 frases ──
            ("Cuando tengo una tarea pendiente al final del día, yo...", 'FR_TRAB'),
            ("Irme a casa sin terminar mi trabajo me hace sentir...", 'FR_TRAB'),
            ("La parte que más disfruto de mi trabajo es...", 'FR_TRAB'),
            ("Cuando me asignan una tarea difícil, lo primero que pienso es...", 'FR_TRAB'),
            ("Si pudiera cambiar algo de mi forma de trabajar, sería...", 'FR_TRAB'),
            ("Mi mayor logro profesional ha sido...", 'FR_TRAB'),
            ("Trabajar bajo presión me hace...", 'FR_TRAB'),
            ("Cuando cometo un error en el trabajo, yo...", 'FR_TRAB'),
            ("Lo que más me motiva para trabajar es...", 'FR_TRAB'),
            ("Mi trabajo ideal sería aquel donde...", 'FR_TRAB'),
            # v2: +7 nuevas
            ("Cuando me dan un reconocimiento en el trabajo, yo siento...", 'FR_TRAB'),
            ("Lo más difícil de mi trabajo actual es...", 'FR_TRAB'),
            ("Si pudiera enseñarle algo a un nuevo compañero, sería...", 'FR_TRAB'),
            ("Cuando tengo mucho trabajo acumulado, yo...", 'FR_TRAB'),
            ("El mejor día de trabajo es cuando...", 'FR_TRAB'),
            ("Mis compañeros de trabajo dirían que yo soy...", 'FR_TRAB'),
            ("Lo que más me frustra en el trabajo es...", 'FR_TRAB'),

            # ── Actitud hacia la autoridad (FR_AUTO) — v1: 10 frases ──
            ("Cuando mi jefe me corrige, siento que...", 'FR_AUTO'),
            ("Si mi supervisor me pide que haga algo con lo que no estoy de acuerdo, yo...", 'FR_AUTO'),
            ("La mejor cualidad de un buen jefe es...", 'FR_AUTO'),
            ("Cuando recibo una orden que no entiendo, yo...", 'FR_AUTO'),
            ("Los jefes que he tenido generalmente han sido...", 'FR_AUTO'),
            ("Si pudiera decirle algo a mi jefe sin consecuencias, le diría...", 'FR_AUTO'),
            ("Seguir instrucciones para mí es...", 'FR_AUTO'),
            ("Las reglas en el trabajo me parecen...", 'FR_AUTO'),
            ("Cuando alguien tiene autoridad sobre mí, yo tiendo a...", 'FR_AUTO'),
            ("El tipo de líder que más respeto es aquel que...", 'FR_AUTO'),
            # v2: +6 nuevas
            ("Cuando mi jefe confía en mí, yo me siento...", 'FR_AUTO'),
            ("Lo peor que puede hacer un jefe es...", 'FR_AUTO'),
            ("Si mi jefe comete un error, yo...", 'FR_AUTO'),
            ("Cuando recibo críticas de mi superior, yo...", 'FR_AUTO'),
            ("Un buen subordinado es aquel que...", 'FR_AUTO'),
            ("La autoridad en el trabajo es necesaria porque...", 'FR_AUTO'),

            # ── Compromiso personal (FR_COMP) — v1: 10 frases ──
            ("Si me ofrecieran un trabajo con mejor sueldo en otra empresa, yo...", 'FR_COMP'),
            ("La empresa donde trabajo es para mí...", 'FR_COMP'),
            ("Me veo trabajando en mi empresa actual dentro de 5 años porque...", 'FR_COMP'),
            ("Lo que me hace sentir más comprometido/a con mi trabajo es...", 'FR_COMP'),
            ("Si mi empresa pasara por una crisis, yo...", 'FR_COMP'),
            ("Renunciar a mi trabajo actual me haría sentir...", 'FR_COMP'),
            ("Lo que más valoro de mi empresa es...", 'FR_COMP'),
            ("Para mí, la lealtad en el trabajo significa...", 'FR_COMP'),
            ("Si un compañero me propusiera irnos juntos a otra empresa, yo...", 'FR_COMP'),
            ("Mi relación con mi empresa es como...", 'FR_COMP'),
            # v2: +7 nuevas
            ("Lo que me mantiene en mi empresa actual es...", 'FR_COMP'),
            ("Si mi empresa me necesitara un fin de semana, yo...", 'FR_COMP'),
            ("Cuando pienso en el futuro de mi empresa, yo...", 'FR_COMP'),
            ("Lo que más agradezco de mi empresa es...", 'FR_COMP'),
            ("Si tuviera que describir mi compromiso laboral en una palabra, sería...", 'FR_COMP'),
            ("Mis planes profesionales a largo plazo incluyen...", 'FR_COMP'),
            ("Cuando alguien critica a mi empresa, yo...", 'FR_COMP'),
        ]

        for i, (texto, dimension) in enumerate(frases):
            Pregunta.objects.get_or_create(
                prueba=prueba, texto=texto,
                defaults={
                    'tipo_escala': 'TEXTO_LIBRE',
                    'dimension': dimension,
                    'orden': i + 1,
                },
            )

        self.stdout.write(f'  Frases: {len(frases)} frases incompletas')

    # ──────────────────────────────────────────────
    # 9. TEST DE COLORES LÜSCHER (sin cambio)
    # ──────────────────────────────────────────────
    def _seed_colores(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='COLORES',
            defaults={
                'nombre': 'Test de Colores (Lüscher simplificado)',
                'descripcion': 'Evalúa estado emocional y preferencias psicológicas mediante ordenamiento de colores.',
                'instrucciones': (
                    'Se le presentarán 8 colores. Ordénelos del que le resulte más agradable '
                    'al que le resulte menos agradable. Realizará este proceso dos veces.'
                ),
                'orden': 9,
                'activa': True,
                'es_proyectiva': True,
            },
        )

        preg, created = Pregunta.objects.get_or_create(
            prueba=prueba,
            texto="Ordene los colores del más agradable al menos agradable.",
            defaults={
                'tipo_escala': 'SELECCION_COLOR',
                'dimension': 'COL_PREF',
                'orden': 1,
            },
        )

        if created:
            colores = [
                ("Azul", 1),
                ("Verde", 2),
                ("Rojo", 3),
                ("Amarillo", 4),
                ("Violeta", 5),
                ("Marrón", 6),
                ("Negro", 7),
                ("Gris", 8),
            ]
            for i, (nombre, valor) in enumerate(colores):
                Opcion.objects.get_or_create(
                    pregunta=preg, texto=nombre,
                    defaults={'valor': valor, 'orden': i},
                )

        self.stdout.write('  Colores: 1 pregunta + 8 colores')

    # ──────────────────────────────────────────────
    # 10. PRUEBA SITUACIONAL (30 escenarios × 4 opciones)
    # ──────────────────────────────────────────────
    def _seed_situacional(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='SITUACIONAL',
            defaults={
                'nombre': 'Prueba Situacional',
                'descripcion': 'Evalúa comportamiento esperado ante escenarios laborales reales.',
                'instrucciones': (
                    'Se le presentarán situaciones laborales hipotéticas. '
                    'Seleccione la opción que mejor describe lo que usted haría en esa situación. '
                    'No hay respuestas correctas; elija la que más se acerque a su comportamiento real.'
                ),
                'orden': 10,
                'activa': True,
                'es_proyectiva': False,
            },
        )

        escenarios = [
            # ── Responsabilidad (SIT_RESP) — v1: 5 escenarios ──
            (1, "Son las 5:00 PM (hora de salida). Tiene una tarea importante que debía entregar hoy pero no la terminó. ¿Qué hace?",
             'SIT_RESP',
             [("Me quedo hasta terminarla sin importar la hora", 5),
              ("Notifico a mi jefe y pido una extensión razonable", 3),
              ("La termino mañana a primera hora", 2),
              ("La delego a un compañero que tiene menos carga", 1)]),

            (2, "Descubre un error grave en un reporte que ya fue enviado a un cliente. ¿Qué hace?",
             'SIT_RESP',
             [("Informo inmediatamente a mi jefe y propongo una solución", 5),
              ("Corrijo el error y envío una versión actualizada por mi cuenta", 3),
              ("Espero a ver si el cliente nota el error", 1),
              ("Comento el error a un compañero para decidir juntos qué hacer", 2)]),

            (3, "Le asignan un proyecto complejo con un plazo ajustado y no está seguro de poder terminarlo. ¿Qué hace?",
             'SIT_RESP',
             [("Acepto el reto y me organizo para cumplir aunque deba trabajar horas extra", 5),
              ("Acepto pero negocio un plazo más realista con mi jefe", 4),
              ("Pido que asignen a alguien más experimentado", 2),
              ("Acepto pero mentalmente ya sé que no llegaré a tiempo", 1)]),

            (4, "Un compañero le pide ayuda con su trabajo cuando usted también tiene tareas pendientes. ¿Qué hace?",
             'SIT_RESP',
             [("Termino primero mis tareas pendientes y luego le ayudo", 5),
              ("Le dedico un momento breve para orientarlo y continúo con lo mío", 4),
              ("Le ayudo inmediatamente aunque mis tareas se retrasen", 2),
              ("Le digo que no puedo porque estoy ocupado", 3)]),

            (5, "Al revisar su trabajo nota que podría mejorar significativamente un entregable, pero ya cumple con los requisitos mínimos. ¿Qué hace?",
             'SIT_RESP',
             [("Lo mejoro antes de entregarlo aunque me tome más tiempo", 5),
              ("Lo entrego como está ya que cumple los requisitos", 3),
              ("Pregunto a mi jefe si vale la pena la mejora", 4),
              ("Lo marco como pendiente de mejora para después", 2)]),

            # v2: +5 escenarios de responsabilidad
            (16, "Le asignan una tarea que no corresponde a su puesto pero es urgente. ¿Qué hace?",
             'SIT_RESP',
             [("La hago sin quejarme porque la empresa lo necesita", 5),
              ("La hago pero informo que no es parte de mis funciones", 4),
              ("Sugiero que se la asignen a quien corresponde", 2),
              ("Me niego porque no es mi responsabilidad", 1)]),

            (17, "Se da cuenta de que un proceso en su área puede optimizarse significativamente. ¿Qué hace?",
             'SIT_RESP',
             [("Preparo una propuesta detallada y la presento a mi jefe", 5),
              ("Lo comento informalmente a mi jefe", 4),
              ("Lo implemento por mi cuenta sin consultar", 2),
              ("No digo nada porque no me van a escuchar", 1)]),

            (18, "Está por entregar un proyecto y descubre que un dato clave podría estar errado. ¿Qué hace?",
             'SIT_RESP',
             [("Verifico el dato aunque eso retrase la entrega", 5),
              ("Lo marco como pendiente de verificación y entrego", 3),
              ("Lo dejo como está porque probablemente está bien", 1),
              ("Pido a un compañero que lo verifique mientras continúo", 4)]),

            (19, "Su equipo no alcanzó la meta del mes y su jefe pide una explicación. ¿Qué hace?",
             'SIT_RESP',
             [("Asumo mi parte de responsabilidad y propongo un plan de mejora", 5),
              ("Explico los factores que afectaron al equipo objetivamente", 4),
              ("Señalo las causas externas que impidieron cumplir", 2),
              ("Culpo a los compañeros que no cumplieron su parte", 1)]),

            (20, "Le entregan un proyecto con instrucciones vagas e incompletas. ¿Qué hace?",
             'SIT_RESP',
             [("Pido clarificación antes de empezar para hacer bien el trabajo", 5),
              ("Empiezo con lo que entiendo y pregunto luego", 3),
              ("Hago lo que puedo con la información disponible", 2),
              ("Espero a que me den instrucciones más claras", 1)]),

            # ── Obediencia (SIT_OBED) — v1: 5 escenarios ──
            (6, "Su jefe le pide que realice una tarea de una forma que usted cree que no es la más eficiente. ¿Qué hace?",
             'SIT_OBED',
             [("La hago como me pidió sin cuestionar", 5),
              ("La hago como me pidió pero después sugiero una alternativa", 4),
              ("Le explico mi forma antes de empezar y le pido que elija", 3),
              ("La hago a mi manera porque sé que es mejor", 1)]),

            (7, "Le cambian un procedimiento que usted dominaba y ahora debe aprender uno nuevo. ¿Qué hace?",
             'SIT_OBED',
             [("Aprendo el nuevo procedimiento sin quejarme", 5),
              ("Lo aprendo pero expreso mi preferencia por el anterior", 3),
              ("Sugiero mantener el procedimiento anterior que ya funciona", 2),
              ("Sigo usando el procedimiento anterior cuando nadie me ve", 1)]),

            (8, "Recibe instrucciones contradictorias de dos supervisores. ¿Qué hace?",
             'SIT_OBED',
             [("Consulto con mi jefe directo para aclarar cuál debo seguir", 5),
              ("Sigo la instrucción del supervisor de mayor rango", 4),
              ("Hago lo que me parezca más lógico", 2),
              ("Espero a que se pongan de acuerdo entre ellos", 1)]),

            (9, "Le piden que trabaje un sábado para cumplir con una entrega urgente. ¿Qué hace?",
             'SIT_OBED',
             [("Acepto sin dudar porque la empresa lo necesita", 5),
              ("Acepto pero pido que sea reconocido de alguna forma", 4),
              ("Negocio para buscar otra alternativa que no implique sábado", 2),
              ("Me niego porque es mi día libre", 1)]),

            (10, "Su jefe toma una decisión que usted considera un error. ¿Qué hace?",
             'SIT_OBED',
             [("Ejecuto la decisión tal como se indicó", 4),
              ("Expreso mi preocupación respetuosamente y luego acato la decisión", 5),
              ("Expreso mi desacuerdo abiertamente e insisto en cambiar la decisión", 2),
              ("Hago lo mínimo posible para cumplir esperando que se note el error", 1)]),

            # v2: +5 escenarios de obediencia
            (21, "Implementan un nuevo sistema informático que reemplaza al que usted dominaba. ¿Qué hace?",
             'SIT_OBED',
             [("Me capacito de inmediato y trato de dominarlo rápidamente", 5),
              ("Lo uso pero extraño el sistema anterior", 3),
              ("Uso el nuevo sistema solo cuando me supervisan", 2),
              ("Pido formalmente que vuelvan al sistema anterior", 1)]),

            (22, "Le asignan un turno de trabajo diferente al que usted prefiere. ¿Qué hace?",
             'SIT_OBED',
             [("Acepto el cambio sin quejarme", 5),
              ("Acepto pero pido que sea temporal", 4),
              ("Solicito formalmente mantener mi turno anterior", 2),
              ("Busco excusas para no cumplir el nuevo horario", 1)]),

            (23, "Su jefe le pide que capacite a un compañero nuevo en sus funciones, aunque eso retrase su propio trabajo. ¿Qué hace?",
             'SIT_OBED',
             [("Lo hago con gusto porque mi jefe lo considera necesario", 5),
              ("Lo hago pero pido más tiempo para mis propias tareas", 4),
              ("Le pido a otro compañero que lo capacite", 2),
              ("Me quejo porque eso no es mi responsabilidad", 1)]),

            (24, "Le prohíben usar su teléfono personal durante horas de trabajo. ¿Qué hace?",
             'SIT_OBED',
             [("Cumplo la norma sin problema", 5),
              ("Cumplo pero reviso en mis descansos", 4),
              ("Lo uso discretamente cuando no me ven", 2),
              ("Me parece excesivo y no lo cumplo", 1)]),

            (25, "Su jefe le pide que rehaga un trabajo que usted considera que estaba bien hecho. ¿Qué hace?",
             'SIT_OBED',
             [("Lo rehago tal como me pidió sin discutir", 5),
              ("Lo rehago pero le pregunto qué específicamente debo mejorar", 4),
              ("Le explico por qué creo que estaba bien", 2),
              ("Lo rehago de mala gana y a medias", 1)]),

            # ── Lealtad (SIT_LEAL) — v1: 5 escenarios ──
            (11, "Un headhunter le contacta ofreciéndole un puesto con 30% más de salario en otra empresa. ¿Qué hace?",
             'SIT_LEAL',
             [("Declino la oferta porque estoy comprometido con mi empresa actual", 5),
              ("Escucho la oferta pero al final me quedo donde estoy", 4),
              ("Uso la oferta para negociar un aumento en mi empresa actual", 2),
              ("Acepto la nueva oferta sin pensarlo mucho", 1)]),

            (12, "Un ex compañero habla mal de su empresa en redes sociales. ¿Qué hace?",
             'SIT_LEAL',
             [("Defiendo a mi empresa públicamente con hechos", 5),
              ("Ignoro los comentarios pero internamente no estoy de acuerdo", 4),
              ("Leo los comentarios con curiosidad pero no intervengo", 2),
              ("Le doy la razón porque también he tenido quejas", 1)]),

            (13, "Descubre que un compañero está buscando trabajo en otra empresa durante horario laboral. ¿Qué hace?",
             'SIT_LEAL',
             [("Se lo comento a mi supervisor de forma discreta", 4),
              ("Hablo con mi compañero y le sugiero que sea más discreto", 3),
              ("No es mi problema, cada quien con lo suyo", 2),
              ("Le pido que me pase las ofertas por si hay algo para mí también", 1)]),

            (14, "La empresa atraviesa un momento difícil y le piden paciencia con un atraso temporal en beneficios. ¿Qué hace?",
             'SIT_LEAL',
             [("Entiendo la situación y apoyo a la empresa en este momento", 5),
              ("Acepto temporalmente pero establezco un plazo límite", 4),
              ("Empiezo a buscar otras opciones por precaución", 2),
              ("Exijo que se cumplan mis beneficios tal como están acordados", 1)]),

            (15, "Le ofrecen ser parte de un nuevo proyecto ambicioso en su empresa, pero implicaría mucho más trabajo sin aumento inmediato. ¿Qué hace?",
             'SIT_LEAL',
             [("Acepto con entusiasmo porque es una oportunidad de crecimiento", 5),
              ("Acepto pero negocio una revisión salarial a mediano plazo", 4),
              ("Lo considero cuidadosamente evaluando pros y contras", 3),
              ("Rechazo porque no quiero más trabajo sin más pago", 1)]),

            # v2: +5 escenarios de lealtad
            (26, "Un competidor le ofrece duplicar su salario actual para que comparta información interna. ¿Qué hace?",
             'SIT_LEAL',
             [("Rechazo de inmediato e informo a mi empresa", 5),
              ("Rechazo sin dudarlo", 4),
              ("Escucho la oferta pero no acepto", 2),
              ("Considero la oferta si la información no es tan sensible", 1)]),

            (27, "Se entera de que la empresa planea despidos pero usted no está afectado. ¿Qué hace?",
             'SIT_LEAL',
             [("Mantengo la calma y continúo dando lo mejor de mí", 5),
              ("Me preocupo pero sigo trabajando normalmente", 4),
              ("Empiezo a actualizar mi currículum por precaución", 2),
              ("Empiezo a buscar otro empleo de inmediato", 1)]),

            (28, "En una reunión social, alguien critica duramente a su empresa. ¿Qué hace?",
             'SIT_LEAL',
             [("Defiendo a mi empresa con argumentos", 5),
              ("Corrijo la información errada pero no discuto", 4),
              ("Cambio de tema para evitar conflicto", 2),
              ("Estoy de acuerdo y agrego mis propias quejas", 1)]),

            (29, "Su empresa le pide mudarse a otra ciudad por una necesidad operativa. ¿Qué hace?",
             'SIT_LEAL',
             [("Acepto porque la empresa me necesita", 5),
              ("Lo considero seriamente y busco negociar condiciones", 4),
              ("Pido que busquen a alguien más primero", 2),
              ("Me niego rotundamente", 1)]),

            (30, "Descubre que un proveedor ofrece una comisión personal si le adjudica un contrato. ¿Qué hace?",
             'SIT_LEAL',
             [("Rechazo la oferta e informo a mi empresa inmediatamente", 5),
              ("Rechazo la oferta sin informar", 4),
              ("Lo considero si nadie se entera", 1),
              ("Acepto si la oferta del proveedor es competitiva de todas formas", 2)]),
        ]

        for orden, texto, dimension, opciones_data in escenarios:
            preg, created = Pregunta.objects.get_or_create(
                prueba=prueba, texto=texto,
                defaults={
                    'tipo_escala': 'OPCION_MULTIPLE',
                    'dimension': dimension,
                    'orden': orden,
                },
            )
            if created:
                for j, (opt_texto, opt_valor) in enumerate(opciones_data):
                    Opcion.objects.get_or_create(
                        pregunta=preg, texto=opt_texto,
                        defaults={'valor': opt_valor, 'orden': j},
                    )

        self.stdout.write(f'  Situacional: {len(escenarios)} escenarios')

    # ──────────────────────────────────────────────
    # 11. DESEABILIDAD SOCIAL (12 ítems — nueva prueba v2)
    # ──────────────────────────────────────────────
    def _seed_deseabilidad(self):
        prueba, _ = Prueba.objects.get_or_create(
            tipo='DESEABILIDAD',
            defaults={
                'nombre': 'Escala de Deseabilidad Social',
                'descripcion': 'Detecta tendencia a responder de forma socialmente deseable (falseo).',
                'instrucciones': (
                    'Indique qué tan de acuerdo está con cada afirmación. '
                    'Responda con sinceridad; no hay respuestas correctas o incorrectas.'
                ),
                'orden': 11,
                'activa': True,
                'es_proyectiva': False,
            },
        )

        items = [
            ("Nunca he dicho una mentira en mi vida.", 'DS_DESB', False),
            ("Jamás he sentido envidia por los logros de otra persona.", 'DS_DESB', False),
            ("Siempre cumplo absolutamente todas las reglas de tránsito.", 'DS_DESB', False),
            ("Nunca me he sentido irritado/a con un compañero de trabajo.", 'DS_DESB', False),
            ("Siempre soy completamente honesto/a en todas las situaciones.", 'DS_DESB', False),
            ("Nunca he hablado mal de nadie a sus espaldas.", 'DS_DESB', False),
            ("Jamás he tenido un pensamiento negativo sobre un familiar.", 'DS_DESB', False),
            ("Nunca he llegado tarde a ningún compromiso en mi vida.", 'DS_DESB', False),
            ("Siempre mantengo la calma perfecta sin importar la situación.", 'DS_DESB', False),
            ("Nunca he sentido pereza por ir al trabajo.", 'DS_DESB', False),
            ("He cometido errores de los que me arrepiento.", 'DS_DESB', True),
            ("A veces pospongo tareas que debería hacer de inmediato.", 'DS_DESB', True),
        ]

        for i, (texto, dimension, es_inversa) in enumerate(items):
            preg, created = Pregunta.objects.get_or_create(
                prueba=prueba, texto=texto,
                defaults={
                    'tipo_escala': 'LIKERT5',
                    'dimension': dimension,
                    'es_inversa': es_inversa,
                    'orden': i + 1,
                },
            )
            if created:
                self._crear_opciones_likert5(preg)

        self.stdout.write(f'  Deseabilidad Social: {len(items)} ítems')

    # ──────────────────────────────────────────────
    # VINCULAR PARES DE CONSISTENCIA (8 pares = 16 preguntas)
    # ──────────────────────────────────────────────
    def _vincular_pares_consistencia(self):
        """
        Vincula pares de preguntas que miden lo mismo con wording distinto.
        2 pares en Big Five, 2 en Compromiso, 2 en Obediencia, 2 en Situacional.
        """
        pares = [
            # Big Five: 2 pares
            (
                "Siempre termino lo que empiezo, sin importar cuánto tiempo me tome.",
                "Cuando asumo un compromiso, lo cumplo sin excusas.",
            ),
            (
                "Me preocupo genuinamente por el bienestar de mis compañeros.",
                "Cuando alguien está triste, trato de animarlo.",
            ),
            # Compromiso: 2 pares
            (
                "Siento un fuerte sentido de pertenencia hacia la empresa donde trabajo.",
                "Me identifico profundamente con la misión de mi empresa.",
            ),
            (
                "Creo que una persona debe ser leal a su organización.",
                "Creo que es mi deber dar lo mejor de mí en mi empresa.",
            ),
            # Obediencia: 2 pares
            (
                "Siempre llego puntual a mis compromisos laborales.",
                "Cuando hay un plazo, lo cumplo sin necesidad de recordatorios.",
            ),
            (
                "Las normas existen por una buena razón y deben respetarse.",
                "Me parece importante que todos cumplan las mismas reglas.",
            ),
            # Situacional: 2 pares
            (
                "Son las 5:00 PM (hora de salida). Tiene una tarea importante que debía entregar hoy pero no la terminó. ¿Qué hace?",
                "Le asignan una tarea que no corresponde a su puesto pero es urgente. ¿Qué hace?",
            ),
            (
                "Su jefe le pide que realice una tarea de una forma que usted cree que no es la más eficiente. ¿Qué hace?",
                "Su jefe le pide que rehaga un trabajo que usted considera que estaba bien hecho. ¿Qué hace?",
            ),
        ]

        vinculados = 0
        for texto_a, texto_b in pares:
            try:
                preg_a = Pregunta.objects.get(texto=texto_a)
                preg_b = Pregunta.objects.get(texto=texto_b)
            except Pregunta.DoesNotExist:
                continue

            if preg_a.par_consistencia_id != preg_b.id:
                preg_a.par_consistencia = preg_b
                preg_a.save(update_fields=['par_consistencia'])
            if preg_b.par_consistencia_id != preg_a.id:
                preg_b.par_consistencia = preg_a
                preg_b.save(update_fields=['par_consistencia'])
            vinculados += 1

        self.stdout.write(f'  Pares de consistencia: {vinculados} pares vinculados')

    # ──────────────────────────────────────────────
    # ACTUALIZAR METADATA DE BANCO
    # ──────────────────────────────────────────────
    def _actualizar_banco_metadata(self):
        """Actualiza items_banco e items_a_aplicar en cada Prueba."""
        config = {
            'BIGFIVE': (120, 50),
            'COMPROMISO': (48, 24),
            'OBEDIENCIA': (40, 20),
            'MEMORIA': (10, 0),
            'MATRICES': (30, 20),
            'ARBOL': (1, 0),
            'PERSONA_LLUVIA': (1, 0),
            'FRASES': (50, 30),
            'COLORES': (1, 0),
            'SITUACIONAL': (30, 15),
            'DESEABILIDAD': (12, 0),
        }

        for tipo, (banco, aplicar) in config.items():
            try:
                prueba = Prueba.objects.get(tipo=tipo)
                real_count = prueba.preguntas.count()
                prueba.items_banco = real_count
                prueba.items_a_aplicar = aplicar
                prueba.save(update_fields=['items_banco', 'items_a_aplicar'])
            except Prueba.DoesNotExist:
                pass

        self.stdout.write('  Metadata de banco actualizada')
