import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta


class PerfilObjetivo(models.Model):
    """Configuración de umbrales mínimos para considerar APTO"""
    nombre = models.CharField(max_length=100, default="Perfil Estándar")

    # Umbrales Big Five (escala 1-5)
    min_responsabilidad = models.FloatField(default=4.0,
        help_text="Conscientiousness mínimo (1-5)")
    min_amabilidad = models.FloatField(default=3.0,
        help_text="Agreeableness mínimo (1-5)")
    max_neuroticismo = models.FloatField(default=3.0,
        help_text="Neuroticism máximo (1-5)")
    min_apertura = models.FloatField(default=2.5,
        help_text="Openness mínimo (1-5)")
    min_extroversion = models.FloatField(default=2.0,
        help_text="Extraversion mínimo (1-5)")

    # Umbrales específicos
    min_compromiso_organizacional = models.FloatField(default=3.5,
        help_text="Allen & Meyer mínimo (1-5)")
    min_obediencia = models.FloatField(default=3.5,
        help_text="Escala conformidad mínimo (1-5)")
    min_memoria = models.FloatField(default=60.0,
        help_text="% mínimo en test de memoria")
    min_matrices = models.FloatField(default=50.0,
        help_text="% mínimo en matrices (inteligencia)")
    min_situacional = models.FloatField(default=60.0,
        help_text="% mínimo en prueba situacional")
    min_atencion_detalle = models.FloatField(default=60.0,
        help_text="% mínimo en atención al detalle")

    METODO_VEREDICTO_CHOICES = [
        ('CONTEO_FALLOS', 'Conteo de fallos (0=APTO, 1=REVISIÓN, 2+=NO APTO)'),
        ('ESTRICTO', 'Estricto (cualquier fallo = NO APTO)'),
    ]

    metodo_veredicto = models.CharField(
        max_length=15, choices=METODO_VEREDICTO_CHOICES,
        default='CONTEO_FALLOS',
        help_text="Método para determinar el veredicto automático")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Perfil Objetivo"
        verbose_name_plural = "Perfiles Objetivo"

    def __str__(self):
        return self.nombre


class Prueba(models.Model):
    """Catálogo de pruebas disponibles"""
    TIPO_CHOICES = [
        ('BIGFIVE', 'Big Five (OCEAN)'),
        ('COMPROMISO', 'Compromiso Organizacional (Allen & Meyer)'),
        ('OBEDIENCIA', 'Escala de Obediencia/Conformidad'),
        ('MEMORIA', 'Test de Memoria de Trabajo'),
        ('MATRICES', 'Matrices Progresivas'),
        ('ARBOL', 'Test del Árbol (Koch)'),
        ('PERSONA_LLUVIA', 'Persona bajo la Lluvia'),
        ('FRASES', 'Frases Incompletas (Sacks)'),
        ('COLORES', 'Test de Colores (Lüscher)'),
        ('SITUACIONAL', 'Prueba Situacional'),
        ('DESEABILIDAD', 'Escala de Deseabilidad Social'),
        ('ATENCION', 'Atención al Detalle'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, unique=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    instrucciones = models.TextField(
        help_text="Texto que verá el candidato antes de iniciar")
    tiempo_limite_minutos = models.IntegerField(null=True, blank=True,
        help_text="Nulo = sin límite")
    orden = models.IntegerField(default=0,
        help_text="Orden de presentación")
    activa = models.BooleanField(default=True)
    es_proyectiva = models.BooleanField(default=False,
        help_text="True si requiere revisión manual")
    items_banco = models.IntegerField(default=0,
        help_text="Total de preguntas disponibles en el banco")
    items_a_aplicar = models.IntegerField(default=0,
        help_text="Preguntas a seleccionar por evaluación (0 = aplicar todas)")

    class Meta:
        ordering = ['orden']
        verbose_name = "Prueba"

    def __str__(self):
        return self.nombre


class Pregunta(models.Model):
    """Preguntas para pruebas psicométricas y situacionales"""
    ESCALA_CHOICES = [
        ('LIKERT5', 'Likert 1-5'),
        ('LIKERT7', 'Likert 1-7'),
        ('OPCION_MULTIPLE', 'Opción múltiple'),
        ('TEXTO_LIBRE', 'Texto libre (frases incompletas)'),
        ('SECUENCIA', 'Secuencia (memoria)'),
        ('SELECCION_COLOR', 'Selección de color'),
    ]

    DIMENSION_CHOICES = [
        # Big Five
        ('BF_RESP', 'Big Five: Responsabilidad'),
        ('BF_AMAB', 'Big Five: Amabilidad'),
        ('BF_NEUR', 'Big Five: Neuroticismo'),
        ('BF_APER', 'Big Five: Apertura'),
        ('BF_EXTR', 'Big Five: Extroversión'),
        # Compromiso
        ('CO_AFEC', 'Compromiso: Afectivo'),
        ('CO_CONT', 'Compromiso: Continuidad'),
        ('CO_NORM', 'Compromiso: Normativo'),
        # Obediencia
        ('OB_DISC', 'Obediencia: Disciplina'),
        ('OB_CONF', 'Obediencia: Conformidad normativa'),
        ('OB_AUTO', 'Obediencia: Orientación a autoridad'),
        # Situacional
        ('SIT_RESP', 'Situacional: Responsabilidad'),
        ('SIT_OBED', 'Situacional: Obediencia'),
        ('SIT_LEAL', 'Situacional: Lealtad'),
        # Frases incompletas
        ('FR_TRAB', 'Frases: Actitud hacia el trabajo'),
        ('FR_AUTO', 'Frases: Actitud hacia la autoridad'),
        ('FR_COMP', 'Frases: Compromiso personal'),
        # Colores
        ('COL_PREF', 'Colores: Preferencia'),
        # Deseabilidad Social
        ('DS_DESB', 'Deseabilidad Social'),
        # Atención al Detalle
        ('AT_COMP', 'Atención: Comparación de documentos'),
        ('AT_VERI', 'Atención: Verificación de datos'),
        ('AT_SECU', 'Atención: Secuencias con error'),
        # Otros
        ('GENERAL', 'General'),
    ]

    prueba = models.ForeignKey(Prueba, on_delete=models.CASCADE,
        related_name='preguntas')
    texto = models.TextField()
    tipo_escala = models.CharField(max_length=20, choices=ESCALA_CHOICES)
    dimension = models.CharField(max_length=10, choices=DIMENSION_CHOICES,
        default='GENERAL')
    es_inversa = models.BooleanField(default=False,
        help_text="Si True, puntaje se invierte (6 - valor)")
    orden = models.IntegerField(default=0)
    imagen = models.ImageField(upload_to='psicoevaluacion/preguntas/',
        null=True, blank=True,
        help_text="Para matrices progresivas")
    par_consistencia = models.ForeignKey('self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='par_vinculado',
        help_text="Par duplicado para control de consistencia")

    # Campos específicos para test de memoria
    secuencia_correcta = models.JSONField(null=True, blank=True,
        help_text="Para memoria: [3,7,2,9,1] secuencia a recordar")

    class Meta:
        ordering = ['prueba', 'orden']
        verbose_name = "Pregunta"

    def __str__(self):
        return f"{self.prueba.tipo} - {self.texto[:50]}"


class Opcion(models.Model):
    """Opciones de respuesta para preguntas de opción múltiple"""
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE,
        related_name='opciones')
    texto = models.CharField(max_length=500)
    valor = models.IntegerField(help_text="Valor numérico de esta opción")
    imagen = models.ImageField(upload_to='psicoevaluacion/opciones/',
        null=True, blank=True,
        help_text="Para opciones visuales (matrices, colores)")
    orden = models.IntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.texto[:30]} (val={self.valor})"


class Evaluacion(models.Model):
    """Sesión de evaluación de un candidato"""
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente - Link generado'),
        ('EN_CURSO', 'En curso - Candidato realizando pruebas'),
        ('COMPLETADA', 'Completada - Pendiente revisión'),
        ('REVISADA', 'Revisada - Con resultados finales'),
        ('EXPIRADA', 'Expirada'),
        ('CANCELADA', 'Cancelada'),
    ]

    # Identificación
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    token = models.CharField(max_length=64, unique=True, editable=False,
        help_text="Token para URL de acceso")

    # Datos del candidato
    nombres = models.CharField(max_length=200, verbose_name="Nombres completos")
    cedula = models.CharField(max_length=13, verbose_name="Número de cédula")
    correo = models.EmailField(verbose_name="Correo electrónico")
    telefono = models.CharField(max_length=20, blank=True)
    cargo_postulado = models.CharField(max_length=200, blank=True,
        verbose_name="Cargo al que postula")

    # Relación opcional con Employee existente
    empleado = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Si ya existe como empleado en el sistema")

    # Perfil objetivo contra el que se evalúa
    perfil_objetivo = models.ForeignKey(PerfilObjetivo, on_delete=models.SET_NULL,
        null=True, blank=True)

    # Control de sesión
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES,
        default='PENDIENTE')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_expiracion = models.DateTimeField(
        help_text="Después de esta fecha el link deja de funcionar")
    fecha_inicio = models.DateTimeField(null=True, blank=True,
        help_text="Cuando el candidato comenzó la evaluación")
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)
    prueba_actual = models.ForeignKey(Prueba, on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Última prueba en la que está el candidato")

    # Selección aleatoria v2
    preguntas_seleccionadas = models.JSONField(null=True, blank=True,
        help_text="IDs de preguntas seleccionadas para esta evaluación")

    # Metadatos
    ip_acceso = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    creado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
        null=True, blank=True)
    notas_evaluador = models.TextField(blank=True,
        verbose_name="Notas del evaluador")

    class Meta:
        verbose_name = "Evaluación"
        verbose_name_plural = "Evaluaciones"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.nombres} - {self.cedula} ({self.estado})"

    def esta_expirada(self):
        return timezone.now() > self.fecha_expiracion

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex + uuid.uuid4().hex[:32]
        if not self.fecha_expiracion:
            self.fecha_expiracion = timezone.now() + timedelta(hours=48)
        super().save(*args, **kwargs)


class RespuestaPsicometrica(models.Model):
    """Respuestas a preguntas tipo Likert y opción múltiple"""
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE,
        related_name='respuestas_psicometricas')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    valor = models.IntegerField(
        help_text="Valor numérico seleccionado")
    opcion_seleccionada = models.ForeignKey(Opcion, on_delete=models.SET_NULL,
        null=True, blank=True)
    tiempo_respuesta_seg = models.IntegerField(null=True, blank=True,
        help_text="Segundos que tardó en responder")
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['evaluacion', 'pregunta']
        verbose_name = "Respuesta Psicométrica"


class RespuestaProyectiva(models.Model):
    """Respuestas a pruebas proyectivas (dibujos y texto libre)"""
    TIPO_CHOICES = [
        ('DIBUJO', 'Dibujo en canvas'),
        ('TEXTO', 'Texto libre (frases incompletas)'),
    ]

    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE,
        related_name='respuestas_proyectivas')
    prueba = models.ForeignKey(Prueba, on_delete=models.CASCADE)
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE,
        null=True, blank=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)

    # Para dibujos
    imagen_canvas = models.TextField(blank=True,
        help_text="Base64 del dibujo en canvas")
    datos_trazo = models.JSONField(null=True, blank=True,
        help_text="Datos de trazos: coordenadas, presión, velocidad, orden")

    # Para texto libre
    texto_respuesta = models.TextField(blank=True)

    # Evaluación manual del evaluador
    puntuacion_manual = models.IntegerField(null=True, blank=True,
        help_text="Puntuación asignada manualmente (1-10)")
    observaciones_evaluador = models.TextField(blank=True)
    revisado = models.BooleanField(default=False)
    fecha_revision = models.DateTimeField(null=True, blank=True)

    # Metadatos
    tiempo_total_seg = models.IntegerField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Respuesta Proyectiva"


class RespuestaMemoria(models.Model):
    """Respuestas al test de memoria de trabajo"""
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE,
        related_name='respuestas_memoria')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE)

    secuencia_presentada = models.JSONField(
        help_text="Secuencia que se le mostró")
    secuencia_respondida = models.JSONField(
        help_text="Secuencia que el candidato ingresó")
    es_correcta = models.BooleanField(default=False)
    longitud_secuencia = models.IntegerField(
        help_text="Largo de la secuencia (dificultad)")
    tiempo_respuesta_seg = models.IntegerField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Respuesta de Memoria"


class RespuestaMatriz(models.Model):
    """Respuestas a matrices progresivas (inteligencia)"""
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE,
        related_name='respuestas_matrices')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    opcion_seleccionada = models.ForeignKey(Opcion, on_delete=models.SET_NULL,
        null=True)
    es_correcta = models.BooleanField(default=False)
    tiempo_respuesta_seg = models.IntegerField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Respuesta de Matriz"


class RespuestaSituacional(models.Model):
    """Respuestas a escenarios situacionales"""
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE,
        related_name='respuestas_situacionales')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    opcion_seleccionada = models.ForeignKey(Opcion, on_delete=models.SET_NULL,
        null=True)
    valor = models.IntegerField()
    justificacion = models.TextField(blank=True,
        help_text="Texto opcional del candidato explicando su elección")
    tiempo_respuesta_seg = models.IntegerField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Respuesta Situacional"


class RespuestaAtencion(models.Model):
    """Respuestas al test de atención al detalle (3 subsecciones)."""
    SUBTIPO_CHOICES = [
        ('COMPARACION', 'Comparación de documentos'),
        ('VERIFICACION', 'Verificación de datos cruzados'),
        ('SECUENCIA', 'Secuencias con error'),
    ]

    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE,
        related_name='respuestas_atencion')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE)
    subtipo = models.CharField(max_length=15, choices=SUBTIPO_CHOICES)

    # For COMPARACION: JSON list of differences found [{campo, original, copia}]
    # For VERIFICACION: JSON list of inconsistencies found [{campo, valor_encontrado, valor_esperado}]
    # For SECUENCIA: the value the candidate identified as the error
    respuesta_json = models.JSONField(null=True, blank=True,
        help_text="Respuesta estructurada del candidato")

    # Correctness fields
    es_correcta = models.BooleanField(default=False,
        help_text="True si la respuesta es completamente correcta")
    puntaje_parcial = models.FloatField(default=0,
        help_text="Puntaje parcial (0-1) para respuestas parcialmente correctas")

    tiempo_respuesta_seg = models.IntegerField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['evaluacion', 'pregunta']
        verbose_name = "Respuesta Atención al Detalle"


class ResultadoFinal(models.Model):
    """Resultado consolidado de la evaluación"""
    VEREDICTO_CHOICES = [
        ('APTO', 'APTO'),
        ('NO_APTO', 'NO APTO'),
        ('REVISION', 'Requiere revisión adicional'),
    ]

    evaluacion = models.OneToOneField(Evaluacion, on_delete=models.CASCADE,
        related_name='resultado')

    # Puntajes por dimensión (escala 1-5 o porcentaje según prueba)
    puntaje_responsabilidad = models.FloatField(null=True)
    puntaje_amabilidad = models.FloatField(null=True)
    puntaje_neuroticismo = models.FloatField(null=True)
    puntaje_apertura = models.FloatField(null=True)
    puntaje_extroversion = models.FloatField(null=True)

    puntaje_compromiso_afectivo = models.FloatField(null=True)
    puntaje_compromiso_continuidad = models.FloatField(null=True)
    puntaje_compromiso_normativo = models.FloatField(null=True)
    puntaje_compromiso_total = models.FloatField(null=True)

    puntaje_obediencia = models.FloatField(null=True)
    puntaje_memoria = models.FloatField(null=True,
        help_text="Porcentaje de aciertos")
    max_secuencia_memoria = models.IntegerField(null=True,
        help_text="Longitud máxima de secuencia recordada")
    puntaje_matrices = models.FloatField(null=True,
        help_text="Porcentaje de aciertos")
    puntaje_situacional = models.FloatField(null=True)

    # Atención al Detalle
    puntaje_atencion_detalle = models.FloatField(null=True, blank=True,
        help_text="Puntaje compuesto atención al detalle (0-100%)")
    puntaje_atencion_comparacion = models.FloatField(null=True, blank=True,
        help_text="F1 score comparación de documentos (0-100%)")
    puntaje_atencion_verificacion = models.FloatField(null=True, blank=True,
        help_text="% aciertos verificación de datos (0-100%)")
    puntaje_atencion_secuencias = models.FloatField(null=True, blank=True,
        help_text="% aciertos en secuencias con error (0-100%)")

    # Proyectivas (evaluación manual)
    puntaje_arbol = models.FloatField(null=True)
    puntaje_persona_lluvia = models.FloatField(null=True)
    puntaje_frases = models.FloatField(null=True)
    puntaje_colores = models.JSONField(null=True, blank=True,
        help_text="Interpretación de secuencia de colores")

    # Confiabilidad v2
    puntaje_deseabilidad_social = models.FloatField(null=True, blank=True,
        help_text="Promedio escala deseabilidad social (1-5)")
    indice_consistencia = models.FloatField(null=True, blank=True,
        help_text="Concordancia entre pares duplicados (0-100%)")
    evaluacion_confiable = models.BooleanField(default=True,
        help_text="False si deseabilidad alta o consistencia baja")

    # Indicadores derivados
    indice_responsabilidad_total = models.FloatField(null=True,
        help_text="Índice ponderado combinando Big Five + situacional")
    indice_lealtad = models.FloatField(null=True,
        help_text="Índice ponderado de compromiso + situacional lealtad")
    indice_obediencia_total = models.FloatField(null=True,
        help_text="Índice combinado obediencia + situacional")

    # Veredicto
    veredicto_automatico = models.CharField(max_length=10,
        choices=VEREDICTO_CHOICES, default='REVISION')
    veredicto_manual = models.CharField(max_length=10,
        choices=VEREDICTO_CHOICES, null=True, blank=True)
    veredicto_final = models.CharField(max_length=10,
        choices=VEREDICTO_CHOICES, null=True, blank=True,
        help_text="El evaluador puede sobrescribir el veredicto automático")

    observaciones = models.TextField(blank=True)
    fecha_calculo = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Resultado Final"
        verbose_name_plural = "Resultados Finales"

    def __str__(self):
        return f"{self.evaluacion.nombres} - {self.veredicto_final or self.veredicto_automatico}"


class ConfiguracionIA(models.Model):
    """Singleton: configuración de proveedores de IA para calificación proyectiva."""
    PROVEEDOR_CHOICES = [
        ('ANTHROPIC', 'Anthropic (Claude)'),
        ('GOOGLE', 'Google (Gemini)'),
    ]

    proveedor_activo = models.CharField(
        max_length=10, choices=PROVEEDOR_CHOICES, default='ANTHROPIC')

    # Anthropic
    anthropic_api_key = models.CharField(
        max_length=200, blank=True,
        help_text="API key de Anthropic")
    anthropic_model = models.CharField(
        max_length=100, default='claude-sonnet-4-20250514',
        help_text="Modelo Anthropic a usar")

    # Google
    google_api_key = models.CharField(
        max_length=200, blank=True,
        help_text="API key de Google AI")
    google_model = models.CharField(
        max_length=100, default='gemini-2.0-flash',
        help_text="Modelo Gemini a usar")

    class Meta:
        verbose_name = "Configuración IA"
        verbose_name_plural = "Configuración IA"

    def __str__(self):
        return f"Configuración IA ({self.get_proveedor_activo_display()})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def is_configured(self):
        if self.proveedor_activo == 'ANTHROPIC':
            return bool(self.anthropic_api_key)
        return bool(self.google_api_key)

    def get_active_key(self):
        if self.proveedor_activo == 'ANTHROPIC':
            return self.anthropic_api_key
        return self.google_api_key

    def get_active_model(self):
        if self.proveedor_activo == 'ANTHROPIC':
            return self.anthropic_model
        return self.google_model
