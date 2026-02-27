# Especificaciones Técnicas: Módulo de Evaluación Psicológica de Talento Humano

## Proyecto: PsicoEval - Módulo integrado al sistema `employees-overtime`

**Versión:** 1.0  
**Fecha:** 2026-02-26  
**Repositorio base:** https://github.com/bambinounos/employees-overtime  
**Stack:** Django + PostgreSQL (integrado al proyecto existente)  
**Idioma de interfaz:** Español  

---

## 1. Objetivo del Sistema

Evaluar candidatos a empleo mediante una batería de pruebas psicológicas y cognitivas para identificar perfiles con las siguientes competencias clave:

| Competencia | Descripción | Prioridad |
|---|---|---|
| **Responsabilidad extrema** | Persona que no puede irse sin completar sus tareas pendientes | CRÍTICA |
| **Obediencia y disciplina** | Seguimiento estricto de instrucciones y cadena de mando | ALTA |
| **Memoria operativa** | Capacidad de retener y ejecutar instrucciones complejas | ALTA |
| **Lealtad organizacional** | Baja tendencia a cambiar de trabajo frecuentemente | ALTA |
| **Inteligencia general** | Capacidad de razonamiento lógico y resolución de problemas | MEDIA |

---

## 2. Integración con el Proyecto Existente

### 2.1 Estructura actual del proyecto `employees-overtime`

```
employees-overtime/
├── employees/          # App principal de empleados
├── salary_management/  # Settings del proyecto Django
├── caldav/             # Integración CalDAV
├── dolibarr_module/    # Integración con Dolibarr
├── scripts/
├── locale/es/
├── manage.py
└── requirements.txt
```

### 2.2 Nueva app Django a crear

```
employees-overtime/
├── ...apps existentes...
├── psicoevaluacion/                # NUEVA APP
│   ├── __init__.py
│   ├── apps.py
│   ├── admin.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── serializers.py              # API REST
│   ├── scoring.py                  # Motor de puntuación
│   ├── utils.py                    # Generación de tokens, emails
│   ├── migrations/
│   ├── management/
│   │   └── commands/
│   │       ├── limpiar_evaluaciones_expiradas.py
│   │       └── seed_pruebas.py     # Carga inicial de preguntas
│   ├── static/
│   │   └── psicoevaluacion/
│   │       ├── css/
│   │       │   └── evaluacion.css
│   │       ├── js/
│   │       │   ├── canvas_dibujo.js      # Motor de dibujo para proyectivas
│   │       │   ├── temporizador.js        # Control de tiempo por sección
│   │       │   ├── evaluacion_flow.js     # Navegación entre pruebas
│   │       │   └── memoria_test.js        # Interacción test de memoria
│   │       └── img/
│   │           └── matrices/              # Imágenes para test tipo Raven
│   ├── templates/
│   │   └── psicoevaluacion/
│   │       ├── base_evaluacion.html       # Layout para candidatos (sin nav admin)
│   │       ├── inicio_candidato.html      # Página de bienvenida + datos
│   │       ├── instrucciones.html         # Instrucciones antes de cada prueba
│   │       ├── prueba_bigfive.html        # Test Big Five
│   │       ├── prueba_compromiso.html     # Test Allen & Meyer
│   │       ├── prueba_obediencia.html     # Escala de conformidad
│   │       ├── prueba_memoria.html        # Test de memoria de trabajo
│   │       ├── prueba_matrices.html       # Matrices progresivas (tipo Raven)
│   │       ├── prueba_arbol.html          # Test del Árbol (canvas)
│   │       ├── prueba_persona_lluvia.html # Persona bajo la lluvia (canvas)
│   │       ├── prueba_frases.html         # Frases incompletas de Sacks
│   │       ├── prueba_colores.html        # Test de Lüscher simplificado
│   │       ├── prueba_situacional.html    # Escenarios laborales
│   │       ├── finalizacion.html          # Pantalla de fin
│   │       ├── admin/
│   │       │   ├── dashboard.html         # Panel del evaluador
│   │       │   ├── detalle_candidato.html # Resultados detallados
│   │       │   ├── crear_evaluacion.html  # Formulario para generar link
│   │       │   └── revisar_proyectivas.html # Revisión manual de dibujos
│   │       └── reportes/
│   │           ├── reporte_individual.html # Reporte PDF individual
│   │           └── comparativo.html       # Tabla comparativa
│   └── tests/
│       ├── test_models.py
│       ├── test_scoring.py
│       └── test_views.py
```

### 2.3 Configuración en `settings.py`

Agregar a `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...apps existentes...
    'psicoevaluacion',
]
```

Agregar a `salary_management/urls.py`:

```python
urlpatterns = [
    # ...rutas existentes...
    path('psicoevaluacion/', include('psicoevaluacion.urls')),
]
```

---

## 3. Modelos de Base de Datos (PostgreSQL)

### 3.1 Diagrama de relaciones

```
Evaluacion (1) ──── (N) RespuestaPsicometrica
    │
    ├──── (N) RespuestaProyectiva
    │
    ├──── (N) RespuestaMemoria
    │
    ├──── (N) RespuestaMatriz
    │
    ├──── (N) RespuestaSituacional
    │
    └──── (1) ResultadoFinal

Prueba (1) ──── (N) Pregunta
                      │
                      └──── (N) Opcion

PerfilObjetivo (configuración global de umbrales)
```

### 3.2 Definición de modelos

```python
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
    
    # Proyectivas (evaluación manual)
    puntaje_arbol = models.FloatField(null=True)
    puntaje_persona_lluvia = models.FloatField(null=True)
    puntaje_frases = models.FloatField(null=True)
    puntaje_colores = models.JSONField(null=True, blank=True,
        help_text="Interpretación de secuencia de colores")
    
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
```

---

## 4. Batería de Pruebas - Detalle

### 4.1 Test Big Five / OCEAN (Psicométrica)

**Objetivo:** Medir los 5 grandes rasgos de personalidad.  
**Foco principal:** Responsabilidad (Conscientiousness) ≥ 4.0/5.0  
**Método:** 50 ítems, escala Likert 1-5 (Totalmente en desacuerdo → Totalmente de acuerdo)  
**Tiempo:** Sin límite (registrar tiempo por respuesta)  
**Distribución:** 10 ítems por dimensión, mezclados aleatoriamente  

**Ejemplos de ítems de Responsabilidad:**
- "Siempre termino lo que empiezo, sin importar cuánto tiempo me tome"
- "Me resulta imposible ir a dormir si tengo tareas pendientes"
- "Soy muy organizado/a con mi agenda y mis compromisos"
- "Prefiero quedarme hasta tarde trabajando que dejar algo incompleto"
- (ítems inversos): "A veces dejo las cosas para el último momento"

**Scoring:**
```python
# scoring.py
def calcular_bigfive(respuestas):
    dimensiones = {
        'BF_RESP': [], 'BF_AMAB': [], 'BF_NEUR': [],
        'BF_APER': [], 'BF_EXTR': []
    }
    for r in respuestas:
        valor = r.valor
        if r.pregunta.es_inversa:
            valor = 6 - valor  # Invertir escala 1-5
        dimensiones[r.pregunta.dimension].append(valor)
    
    return {
        'responsabilidad': mean(dimensiones['BF_RESP']),
        'amabilidad': mean(dimensiones['BF_AMAB']),
        'neuroticismo': mean(dimensiones['BF_NEUR']),
        'apertura': mean(dimensiones['BF_APER']),
        'extroversion': mean(dimensiones['BF_EXTR']),
    }
```

### 4.2 Test de Compromiso Organizacional - Allen & Meyer (Psicométrica)

**Objetivo:** Medir tendencia a permanecer en una organización.  
**Foco:** Compromiso afectivo + normativo altos = persona leal.  
**Método:** 24 ítems, escala Likert 1-5  
**Subdimensiones:**
- Compromiso Afectivo (8 ítems): Apego emocional a la organización
- Compromiso de Continuidad (8 ítems): Percepción del costo de irse
- Compromiso Normativo (8 ítems): Sentido de obligación moral

**Ejemplos:**
- Afectivo: "Me sentiría culpable si dejara mi empresa ahora"
- Continuidad: "Cambiar de trabajo significaría un gran sacrificio personal"
- Normativo: "Creo que una persona debe ser leal a su organización"

### 4.3 Escala de Obediencia y Conformidad (Psicométrica)

**Objetivo:** Medir disposición a seguir instrucciones y cadena de mando.  
**Método:** 20 ítems, escala Likert 1-5  
**Subdimensiones:**
- Disciplina (7 ítems)
- Conformidad normativa (7 ítems)  
- Orientación a la autoridad (6 ítems)

**Ejemplos:**
- "Si mi jefe me da una instrucción, la cumplo aunque no esté de acuerdo"
- "Seguir las reglas es más importante que ser creativo"
- "Prefiero que me digan exactamente qué hacer a improvisar"

### 4.4 Test de Memoria de Trabajo (Cognitiva)

**Objetivo:** Evaluar capacidad de retener y reproducir instrucciones.  
**Método:** Secuencias progresivas de dígitos, palabras e instrucciones  
**Implementación:** JavaScript interactivo  

**Estructura:**
1. **Nivel 1-3:** Secuencias de dígitos (3→4→5 dígitos)
2. **Nivel 4-6:** Secuencias de dígitos inversa (3→4→5)
3. **Nivel 7-9:** Instrucciones encadenadas ("Primero haz A, luego B, después C")
4. **Nivel 10:** Instrucción compleja con 5-6 pasos

**Flujo JavaScript:**
```javascript
// memoria_test.js
// 1. Mostrar secuencia en pantalla (1 segundo por elemento)
// 2. Pantalla de espera (3 segundos)
// 3. Candidato ingresa la secuencia recordada
// 4. Verificar coincidencia
// 5. Si acierta, subir dificultad; si falla 2 veces seguidas, terminar
```

**Scoring:**
- % de secuencias correctas
- Longitud máxima de secuencia recordada (span)
- Tiempo de respuesta promedio

### 4.5 Matrices Progresivas (Cognitiva - tipo Raven)

**Objetivo:** Medir inteligencia no verbal / razonamiento lógico.  
**Método:** 20 matrices con patrón a completar, 4 opciones de respuesta  
**Tiempo:** 20 minutos máximo  
**Implementación:** Imágenes estáticas con opciones clickeables  

**Nota:** Las imágenes de las matrices deben ser creadas como SVG o PNG originales para evitar problemas de copyright. Se deben generar patrones geométricos propios (no copiar las matrices de Raven exactas).

**Scoring:** % de aciertos, ponderado por dificultad progresiva.

### 4.6 Test del Árbol - Karl Koch (Proyectiva)

**Objetivo:** Evaluar personalidad profunda, estabilidad emocional, arraigo.  
**Método:** Canvas digital para dibujar un árbol  
**Instrucción al candidato:** "Dibuje un árbol como usted quiera. Puede usar el mouse o pantalla táctil. No hay respuestas correctas o incorrectas."  
**Datos capturados:**
- Imagen final (Base64 PNG)
- Datos de trazos (coordenadas x,y, timestamp, velocidad)
- Tiempo total
- Cantidad de trazos
- Uso del borrador (veces que borró)

**Revisión:** Manual por el evaluador. Guía de interpretación básica:
- Tamaño del árbol (autoestima)
- Posición en la hoja (orientación temporal)
- Presencia de raíces (arraigo, estabilidad)
- Copa del árbol (relaciones sociales)
- Tronco (fortaleza del yo)
- Frutos (productividad, logros)

### 4.7 Persona bajo la Lluvia (Proyectiva)

**Objetivo:** Evaluar reacción ante presión y estrés.  
**Método:** Canvas digital  
**Instrucción:** "Dibuje una persona bajo la lluvia"  
**Datos capturados:** Mismos que Test del Árbol  

**Interpretación manual:**
- Presencia de paraguas (mecanismos de defensa)
- Tamaño de la persona vs lluvia (proporción yo vs presión)
- Dirección de la lluvia (fuente de presión percibida)
- Expresión facial (actitud ante adversidad)

### 4.8 Frases Incompletas de Sacks (Proyectiva)

**Objetivo:** Revelar actitudes profundas hacia trabajo, autoridad y compromiso.  
**Método:** 30 frases incompletas que el candidato debe completar por escrito  
**Tiempo:** Sin límite  

**Ejemplos por dimensión:**
- **Trabajo:** "Cuando tengo una tarea pendiente al final del día, yo..."
- **Autoridad:** "Cuando mi jefe me corrige, siento que..."
- **Compromiso:** "Si me ofrecieran un trabajo con mejor sueldo, yo..."
- **Responsabilidad:** "Irme a casa sin terminar mi trabajo me hace sentir..."
- **Lealtad:** "La empresa donde trabajo es para mí..."

**Revisión:** Manual. Se califican las respuestas en escala 1-10 por dimensión.

### 4.9 Test de Colores - Lüscher Simplificado (Proyectiva)

**Objetivo:** Evaluar estado emocional y preferencias psicológicas.  
**Método:** Se presentan 8 colores. El candidato los ordena de más agradable a menos agradable, dos veces.  
**Implementación:** Drag & Drop en JavaScript  

**Colores:** Azul, Verde, Rojo, Amarillo, Violeta, Marrón, Negro, Gris  
**Datos:** Orden de selección (primera y segunda vez)  

**Scoring:** Automático parcial basado en interpretación estándar de Lüscher + revisión manual.

### 4.10 Prueba Situacional (Psicométrica)

**Objetivo:** Evaluar reacción real ante escenarios laborales específicos.  
**Método:** 15 escenarios con 4 opciones de respuesta cada uno  
**Cada opción tiene valor diferente según la competencia que refleja**  

**Ejemplo:**
> "Son las 5:00 PM (hora de salida). Tiene una tarea importante que debía entregar hoy pero no la terminó. ¿Qué hace?"
>
> a) Me quedo hasta terminarla sin importar la hora (Responsabilidad: 5)  
> b) Notifico a mi jefe y pido más tiempo (Responsabilidad: 3, Obediencia: 4)  
> c) La termino mañana temprano (Responsabilidad: 2)  
> d) La delego a un compañero (Responsabilidad: 1)

**Dimensiones medidas:** Responsabilidad, Obediencia, Lealtad

---

## 5. Motor de Scoring (`scoring.py`)

### 5.1 Cálculo automático de puntajes

```python
# Pseudocódigo del motor de scoring

def calcular_resultado_final(evaluacion):
    resultado = ResultadoFinal(evaluacion=evaluacion)
    
    # 1. Big Five
    bf = calcular_bigfive(evaluacion.respuestas_psicometricas.filter(
        pregunta__prueba__tipo='BIGFIVE'))
    resultado.puntaje_responsabilidad = bf['responsabilidad']
    resultado.puntaje_amabilidad = bf['amabilidad']
    resultado.puntaje_neuroticismo = bf['neuroticismo']
    resultado.puntaje_apertura = bf['apertura']
    resultado.puntaje_extroversion = bf['extroversion']
    
    # 2. Compromiso Allen & Meyer
    co = calcular_compromiso(evaluacion.respuestas_psicometricas.filter(
        pregunta__prueba__tipo='COMPROMISO'))
    resultado.puntaje_compromiso_afectivo = co['afectivo']
    resultado.puntaje_compromiso_continuidad = co['continuidad']
    resultado.puntaje_compromiso_normativo = co['normativo']
    resultado.puntaje_compromiso_total = mean([co['afectivo'], co['normativo']])
    
    # 3. Obediencia
    resultado.puntaje_obediencia = calcular_obediencia(
        evaluacion.respuestas_psicometricas.filter(
            pregunta__prueba__tipo='OBEDIENCIA'))
    
    # 4. Memoria
    mem = calcular_memoria(evaluacion.respuestas_memoria.all())
    resultado.puntaje_memoria = mem['porcentaje']
    resultado.max_secuencia_memoria = mem['max_span']
    
    # 5. Matrices
    resultado.puntaje_matrices = calcular_matrices(
        evaluacion.respuestas_matrices.all())
    
    # 6. Situacional
    resultado.puntaje_situacional = calcular_situacional(
        evaluacion.respuestas_situacionales.all())
    
    # 7. Índices combinados
    resultado.indice_responsabilidad_total = (
        resultado.puntaje_responsabilidad * 0.5 +
        (resultado.puntaje_situacional / 20) * 0.3 +  # normalizar a 5
        (resultado.puntaje_memoria / 20) * 0.2
    )
    
    resultado.indice_lealtad = (
        resultado.puntaje_compromiso_total * 0.6 +
        resultado.puntaje_responsabilidad * 0.2 +
        resultado.puntaje_obediencia * 0.2
    )
    
    resultado.indice_obediencia_total = (
        resultado.puntaje_obediencia * 0.6 +
        (resultado.puntaje_situacional / 20) * 0.4
    )
    
    # 8. Veredicto automático
    perfil = evaluacion.perfil_objetivo or PerfilObjetivo.objects.filter(activo=True).first()
    resultado.veredicto_automatico = determinar_veredicto(resultado, perfil)
    
    resultado.save()
    return resultado


def determinar_veredicto(resultado, perfil):
    """
    APTO: Cumple TODOS los umbrales mínimos en pruebas psicométricas
    NO APTO: Falla en 2+ criterios críticos
    REVISION: Falla en 1 criterio o tiene proyectivas pendientes
    """
    fallos = 0
    
    if resultado.puntaje_responsabilidad < perfil.min_responsabilidad:
        fallos += 1
    if resultado.puntaje_compromiso_total < perfil.min_compromiso_organizacional:
        fallos += 1
    if resultado.puntaje_obediencia < perfil.min_obediencia:
        fallos += 1
    if resultado.puntaje_memoria < perfil.min_memoria:
        fallos += 1
    if resultado.puntaje_matrices < perfil.min_matrices:
        fallos += 1
    if resultado.puntaje_neuroticismo > perfil.max_neuroticismo:
        fallos += 1
    
    # Verificar si hay proyectivas sin revisar
    proyectivas_pendientes = resultado.evaluacion.respuestas_proyectivas.filter(
        revisado=False).exists()
    
    if fallos == 0 and not proyectivas_pendientes:
        return 'APTO'
    elif fallos >= 2:
        return 'NO_APTO'
    else:
        return 'REVISION'
```

---

## 6. Flujo del Candidato

### 6.1 Secuencia de navegación

```
[Admin genera link] 
    → Candidato recibe email con URL
    → GET /psicoevaluacion/evaluar/{token}/
    → Verificar token válido y no expirado
    → Pantalla de bienvenida + verificar datos (nombre, cédula)
    → Instrucciones generales
    
    → PRUEBA 1: Big Five (50 preguntas Likert)
    → PRUEBA 2: Compromiso Organizacional (24 preguntas Likert)
    → PRUEBA 3: Obediencia (20 preguntas Likert)
    → PRUEBA 4: Test de Memoria (interactivo JS, progresivo)
    → PRUEBA 5: Matrices Progresivas (20 min, imágenes)
    → PRUEBA 6: Test del Árbol (canvas digital)
    → PRUEBA 7: Persona bajo la lluvia (canvas digital)
    → PRUEBA 8: Frases incompletas de Sacks (30 frases)
    → PRUEBA 9: Test de Colores (drag & drop)
    → PRUEBA 10: Prueba Situacional (15 escenarios)
    
    → Pantalla de finalización ("Gracias, sus resultados serán revisados")
    → Token se invalida
```

### 6.2 Reglas de navegación

- El candidato NO puede retroceder a pruebas anteriores
- Cada prueba guarda respuestas inmediatamente al servidor (AJAX)
- Si cierra el navegador, puede retomar donde se quedó (mientras el token sea válido)
- Tiempo máximo total: configurable (por defecto 3 horas)
- Cada prueba tiene su pantalla de instrucciones antes de iniciar

### 6.3 URLs

```python
# psicoevaluacion/urls.py

urlpatterns = [
    # --- Candidato (público, con token) ---
    path('evaluar/<str:token>/', views.inicio_evaluacion, name='inicio_evaluacion'),
    path('evaluar/<str:token>/verificar/', views.verificar_candidato, name='verificar_candidato'),
    path('evaluar/<str:token>/prueba/<str:tipo_prueba>/', views.realizar_prueba, name='realizar_prueba'),
    path('evaluar/<str:token>/finalizar/', views.finalizar_evaluacion, name='finalizar_evaluacion'),
    
    # --- API para guardar respuestas (AJAX) ---
    path('api/respuesta/psicometrica/', views.api_guardar_psicometrica, name='api_psicometrica'),
    path('api/respuesta/memoria/', views.api_guardar_memoria, name='api_memoria'),
    path('api/respuesta/matriz/', views.api_guardar_matriz, name='api_matriz'),
    path('api/respuesta/proyectiva/', views.api_guardar_proyectiva, name='api_proyectiva'),
    path('api/respuesta/situacional/', views.api_guardar_situacional, name='api_situacional'),
    
    # --- Panel del evaluador (requiere login) ---
    path('admin/dashboard/', views.dashboard_evaluador, name='dashboard_evaluador'),
    path('admin/crear/', views.crear_evaluacion, name='crear_evaluacion'),
    path('admin/evaluacion/<int:pk>/', views.detalle_evaluacion, name='detalle_evaluacion'),
    path('admin/evaluacion/<int:pk>/revisar-proyectivas/', views.revisar_proyectivas, name='revisar_proyectivas'),
    path('admin/evaluacion/<int:pk>/calcular/', views.calcular_resultados, name='calcular_resultados'),
    path('admin/evaluacion/<int:pk>/reporte/', views.generar_reporte, name='generar_reporte'),
    path('admin/evaluacion/<int:pk>/veredicto/', views.asignar_veredicto, name='asignar_veredicto'),
    path('admin/comparativo/', views.comparativo, name='comparativo'),
]
```

---

## 7. Panel del Evaluador (Admin)

### 7.1 Dashboard

- Lista de evaluaciones recientes con estado (color coded)
- Conteo: Pendientes, En curso, Completadas, Revisadas
- Acceso rápido a crear nueva evaluación
- Alertas de evaluaciones por revisar (proyectivas pendientes)

### 7.2 Crear Evaluación

Formulario:
- Nombres completos (requerido)
- Número de cédula (requerido, validar formato ecuatoriano)
- Correo electrónico (requerido)
- Teléfono (opcional)
- Cargo al que postula (opcional)
- Perfil objetivo a usar (select)
- Tiempo de expiración del link (por defecto 48 horas)

Al guardar:
1. Genera token único
2. Crea URL: `https://dominio/psicoevaluacion/evaluar/{token}/`
3. Envía email al candidato con el link (usando configuración SMTP de Django)
4. Muestra el link en pantalla también para copiar

### 7.3 Detalle de Evaluación

- Datos del candidato
- Estado actual
- Progreso por prueba (barra de progreso)
- Resultados por dimensión (gráfico radar)
- Puntajes detallados con indicador vs umbral
- Botón para revisar proyectivas
- Veredicto automático + campo para veredicto manual
- Botón generar reporte PDF

### 7.4 Revisión de Proyectivas

- Muestra imagen del dibujo en grande
- Metadatos (tiempo, trazos, borrados)
- Campo de puntuación (1-10)
- Campo de observaciones
- Guía rápida de interpretación al lado
- Botón "Revisado" para marcar como completado

---

## 8. Componentes JavaScript Clave

### 8.1 Canvas de Dibujo (`canvas_dibujo.js`)

```javascript
// Funcionalidades requeridas:
// - Dibujo libre con mouse o touch
// - Grosor de línea configurable
// - Color negro (lápiz) + borrador
// - Botón deshacer último trazo
// - Botón limpiar todo
// - Captura de datos de trazo (coordenadas, timestamps)
// - Exportar como Base64 PNG
// - Responsive (adaptarse a pantalla)
// - Prevenir zoom/scroll accidental en móviles
```

### 8.2 Test de Memoria (`memoria_test.js`)

```javascript
// Flujo:
// 1. Mostrar "Prepárese..." (2 seg)
// 2. Mostrar elementos uno a uno (1 seg c/u)
// 3. Pantalla "Ahora ingrese la secuencia" (aparecer después de 2 seg de pausa)
// 4. Input para ingresar respuesta (campos individuales o teclado numérico)
// 5. Validar y enviar al servidor
// 6. Siguiente nivel o fin
```

### 8.3 Test de Colores (`evaluacion_flow.js`)

```javascript
// Drag & Drop:
// - 8 rectángulos de colores
// - Arrastrar para ordenar de más agradable a menos
// - Hacer el proceso dos veces (segunda ronda después de 2 minutos)
// - Enviar ambas secuencias al servidor
```

---

## 9. Dependencias Adicionales (requirements.txt)

```
# Agregar a requirements.txt existente:
Pillow>=10.0          # Para ImageField
reportlab>=4.0        # Para generar reportes PDF
weasyprint>=60.0      # Alternativa para PDF desde HTML (opcional)
```

---

## 10. Seguridad

- Tokens criptográficamente seguros (64 caracteres hex)
- Link caduca después del tiempo configurado
- Una vez completada, el token se invalida permanentemente
- No se puede retroceder ni re-enviar respuestas ya guardadas
- Rate limiting en endpoints de API
- CSRF protection en todos los formularios
- Las respuestas se guardan con IP y User-Agent para auditoría
- Los dibujos (Base64) pueden ser grandes; configurar `DATA_UPLOAD_MAX_MEMORY_SIZE`

---

## 11. Plan de Implementación Sugerido (para Claude Code)

### Fase 1: Estructura base
1. Crear app `psicoevaluacion`
2. Implementar todos los modelos
3. Migraciones
4. Admin Django básico
5. Management command `seed_pruebas` con las preguntas iniciales

### Fase 2: Flujo del candidato
1. Vista de inicio y verificación de token
2. Implementar pruebas psicométricas (Likert) - reutilizar template
3. Test de memoria (JavaScript interactivo)
4. Canvas de dibujo para proyectivas
5. Test de colores (drag & drop)
6. Prueba situacional
7. Pantalla de finalización

### Fase 3: Panel del evaluador
1. Dashboard
2. Crear evaluación + envío de email
3. Detalle con resultados
4. Revisión de proyectivas
5. Veredicto manual

### Fase 4: Scoring y reportes
1. Motor de scoring automático
2. Generación de reportes PDF
3. Vista comparativa de candidatos

### Fase 5: Pruebas y refinamiento
1. Tests unitarios del scoring
2. Test end-to-end del flujo
3. Ajuste de umbrales basado en pruebas reales

---

## 12. Consideraciones Importantes

### 12.1 Validez psicológica
Las pruebas implementadas son adaptaciones simplificadas de instrumentos estandarizados. Para uso formal en procesos de selección, se recomienda validarlas con un profesional en psicología organizacional. Los resultados deben considerarse como una herramienta de apoyo, no como un diagnóstico definitivo.

### 12.2 Protección de datos
Dado que se manejan datos personales sensibles (cédula, resultados psicológicos), cumplir con la Ley Orgánica de Protección de Datos Personales de Ecuador (LOPD). Incluir consentimiento informado antes de iniciar la evaluación.

### 12.3 Matrices propias
No usar imágenes de las Matrices Progresivas de Raven (copyright). Generar patrones geométricos propios con SVG que sigan la misma lógica de razonamiento abstracto.

### 12.4 Escalabilidad
Con 10-20 candidatos/mes, PostgreSQL y Django son más que suficientes. Los datos de canvas (Base64) pueden llegar a 1-3 MB por dibujo; considerar compresión o almacenamiento en filesystem con referencia en DB.
