from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from employees.models import Employee
from .models import (
    PerfilObjetivo, Prueba, Pregunta, Opcion, Evaluacion,
    RespuestaPsicometrica, RespuestaProyectiva, RespuestaMemoria,
    RespuestaMatriz, RespuestaSituacional, ResultadoFinal,
    ConfiguracionIA,
)


class PreguntaInline(admin.TabularInline):
    model = Pregunta
    extra = 1
    fields = ('texto', 'tipo_escala', 'dimension', 'es_inversa', 'orden')


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 2
    fields = ('texto', 'valor', 'orden')


@admin.register(PerfilObjetivo)
class PerfilObjetivoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'metodo_veredicto', 'min_responsabilidad',
                    'min_compromiso_organizacional',
                    'min_obediencia', 'min_memoria', 'min_matrices')
    list_editable = ('activo', 'metodo_veredicto', 'min_responsabilidad',
                     'min_compromiso_organizacional',
                     'min_obediencia', 'min_memoria', 'min_matrices')


@admin.register(Prueba)
class PruebaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'nombre', 'activa', 'es_proyectiva', 'orden',
                    'tiempo_limite_minutos', 'num_preguntas',
                    'items_banco', 'items_a_aplicar')
    list_filter = ('activa', 'es_proyectiva', 'tipo')
    list_editable = ('activa', 'orden')
    inlines = [PreguntaInline]

    @admin.display(description='# Preguntas')
    def num_preguntas(self, obj):
        return obj.preguntas.count()


@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ('texto_corto', 'prueba', 'dimension', 'tipo_escala',
                    'es_inversa', 'orden')
    list_filter = ('prueba', 'dimension', 'tipo_escala', 'es_inversa')
    search_fields = ('texto',)
    inlines = [OpcionInline]

    @admin.display(description='Texto')
    def texto_corto(self, obj):
        return obj.texto[:80] + '...' if len(obj.texto) > 80 else obj.texto


@admin.register(Evaluacion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'cedula', 'cargo_postulado', 'estado_color',
                    'fecha_creacion', 'fecha_expiracion', 'acciones_proyectivas')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('nombres', 'cedula', 'correo')
    readonly_fields = ('uuid', 'token', 'fecha_creacion', 'link_evaluacion',
                       'acciones_proyectivas_detail')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "empleado":
            kwargs["queryset"] = Employee.objects.filter(end_date__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='Estado')
    def estado_color(self, obj):
        colores = {
            'PENDIENTE': '#ffc107',
            'EN_CURSO': '#17a2b8',
            'COMPLETADA': '#28a745',
            'REVISADA': '#6f42c1',
            'EXPIRADA': '#6c757d',
            'CANCELADA': '#dc3545',
        }
        color = colores.get(obj.estado, '#000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_estado_display()
        )

    @admin.display(description='Link de evaluación')
    def link_evaluacion(self, obj):
        if not obj.token:
            return '-'
        url = f"/psicoevaluacion/evaluar/{obj.token}/"
        return format_html(
            '<a href="{}" target="_blank" style="font-size: 14px;">{}</a>'
            '&nbsp;&nbsp;'
            '<button type="button" onclick="'
            'var u=window.location.origin+&quot;{}&quot;;'
            'navigator.clipboard.writeText(u);'
            'this.innerText=&quot;Copiado!&quot;;'
            'setTimeout(function(){{this.innerText=&quot;Copiar&quot;}}.bind(this),2000);"'
            ' style="cursor:pointer; padding: 2px 8px;">Copiar</button>',
            url, url, url
        )

    @admin.display(description='Acciones')
    def acciones_proyectivas(self, obj):
        if obj.estado not in ('COMPLETADA', 'REVISADA'):
            return '-'
        revisar_url = reverse('psicoevaluacion:revisar_proyectivas', args=[obj.pk])
        descargar_url = reverse('psicoevaluacion:descargar_proyectivas', args=[obj.pk])
        reporte_url = reverse('psicoevaluacion:generar_reporte', args=[obj.pk])
        return format_html(
            '<a href="{}" style="margin-right:8px;">Revisar/IA</a>'
            '<a href="{}" style="margin-right:8px;">ZIP</a>'
            '<a href="{}">PDF</a>',
            revisar_url, descargar_url, reporte_url
        )

    @admin.display(description='Acciones proyectivas')
    def acciones_proyectivas_detail(self, obj):
        if not obj.pk:
            return '-'
        revisar_url = reverse('psicoevaluacion:revisar_proyectivas', args=[obj.pk])
        descargar_url = reverse('psicoevaluacion:descargar_proyectivas', args=[obj.pk])
        reporte_url = reverse('psicoevaluacion:generar_reporte', args=[obj.pk])
        return format_html(
            '<a href="{}" style="font-size:14px; margin-right:12px;">'
            'Revisar y Calificar con IA</a>'
            '<a href="{}" style="font-size:14px; margin-right:12px;">'
            'Descargar ZIP</a>'
            '<a href="{}" style="font-size:14px;">'
            'Descargar Informe PDF</a>',
            revisar_url, descargar_url, reporte_url
        )


@admin.register(ResultadoFinal)
class ResultadoFinalAdmin(admin.ModelAdmin):
    list_display = ('evaluacion', 'veredicto_automatico', 'veredicto_final',
                    'puntaje_responsabilidad', 'puntaje_compromiso_total',
                    'puntaje_obediencia', 'puntaje_memoria', 'puntaje_matrices',
                    'evaluacion_confiable', 'link_proyectivas')
    list_filter = ('veredicto_automatico', 'veredicto_final', 'evaluacion_confiable')
    readonly_fields = (
        'puntaje_responsabilidad', 'puntaje_amabilidad', 'puntaje_neuroticismo',
        'puntaje_apertura', 'puntaje_extroversion',
        'puntaje_compromiso_afectivo', 'puntaje_compromiso_continuidad',
        'puntaje_compromiso_normativo', 'puntaje_compromiso_total',
        'puntaje_obediencia', 'puntaje_memoria', 'max_secuencia_memoria',
        'puntaje_matrices', 'puntaje_situacional',
        'puntaje_arbol', 'puntaje_persona_lluvia', 'puntaje_frases', 'puntaje_colores',
        'puntaje_deseabilidad_social', 'indice_consistencia', 'evaluacion_confiable',
        'indice_responsabilidad_total', 'indice_lealtad', 'indice_obediencia_total',
        'veredicto_automatico', 'fecha_calculo',
        'link_proyectivas_detail',
    )

    @admin.display(description='Acciones')
    def link_proyectivas(self, obj):
        revisar_url = reverse('psicoevaluacion:revisar_proyectivas', args=[obj.evaluacion_id])
        reporte_url = reverse('psicoevaluacion:generar_reporte', args=[obj.evaluacion_id])
        return format_html(
            '<a href="{}" style="margin-right:8px;">Revisar/IA</a>'
            '<a href="{}">PDF</a>',
            revisar_url, reporte_url
        )

    @admin.display(description='Acciones')
    def link_proyectivas_detail(self, obj):
        revisar_url = reverse('psicoevaluacion:revisar_proyectivas', args=[obj.evaluacion_id])
        descargar_url = reverse('psicoevaluacion:descargar_proyectivas', args=[obj.evaluacion_id])
        reporte_url = reverse('psicoevaluacion:generar_reporte', args=[obj.evaluacion_id])
        return format_html(
            '<a href="{}" style="font-size:14px; margin-right:12px;">'
            'Revisar y Calificar con IA</a>'
            '<a href="{}" style="font-size:14px; margin-right:12px;">'
            'Descargar ZIP</a>'
            '<a href="{}" style="font-size:14px;">'
            'Descargar Informe PDF</a>',
            revisar_url, descargar_url, reporte_url
        )


@admin.register(RespuestaPsicometrica)
class RespuestaPsicometricaAdmin(admin.ModelAdmin):
    list_display = ('evaluacion', 'pregunta', 'valor', 'fecha_respuesta')
    list_filter = ('pregunta__prueba',)


@admin.register(RespuestaProyectiva)
class RespuestaProyectivaAdmin(admin.ModelAdmin):
    list_display = ('evaluacion', 'prueba', 'tipo', 'revisado', 'puntuacion_manual')
    list_filter = ('revisado', 'tipo', 'prueba')


@admin.register(RespuestaMemoria)
class RespuestaMemoriaAdmin(admin.ModelAdmin):
    list_display = ('evaluacion', 'longitud_secuencia', 'es_correcta', 'fecha_respuesta')
    list_filter = ('es_correcta',)


@admin.register(RespuestaMatriz)
class RespuestaMatrizAdmin(admin.ModelAdmin):
    list_display = ('evaluacion', 'pregunta', 'es_correcta', 'fecha_respuesta')
    list_filter = ('es_correcta',)


@admin.register(RespuestaSituacional)
class RespuestaSituacionalAdmin(admin.ModelAdmin):
    list_display = ('evaluacion', 'pregunta', 'valor', 'fecha_respuesta')
    list_filter = ('pregunta__dimension',)


@admin.register(ConfiguracionIA)
class ConfiguracionIAAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Proveedor activo', {
            'fields': ('proveedor_activo',),
        }),
        ('Anthropic (Claude)', {
            'fields': ('anthropic_api_key', 'anthropic_model'),
            'classes': ('collapse',),
        }),
        ('Google (Gemini)', {
            'fields': ('google_api_key', 'google_model'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        return not ConfiguracionIA.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
