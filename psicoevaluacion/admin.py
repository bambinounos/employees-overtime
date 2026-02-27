from django.contrib import admin
from django.utils.html import format_html

from .models import (
    PerfilObjetivo, Prueba, Pregunta, Opcion, Evaluacion,
    RespuestaPsicometrica, RespuestaProyectiva, RespuestaMemoria,
    RespuestaMatriz, RespuestaSituacional, ResultadoFinal,
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
    list_display = ('nombre', 'activo', 'min_responsabilidad', 'min_compromiso_organizacional',
                    'min_obediencia', 'min_memoria', 'min_matrices')
    list_editable = ('activo', 'min_responsabilidad', 'min_compromiso_organizacional',
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
                    'fecha_creacion', 'fecha_expiracion')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('nombres', 'cedula', 'correo')
    readonly_fields = ('uuid', 'token', 'fecha_creacion', 'link_evaluacion')

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


@admin.register(ResultadoFinal)
class ResultadoFinalAdmin(admin.ModelAdmin):
    list_display = ('evaluacion', 'veredicto_automatico', 'veredicto_final',
                    'puntaje_responsabilidad', 'puntaje_compromiso_total',
                    'puntaje_obediencia', 'puntaje_memoria', 'puntaje_matrices',
                    'evaluacion_confiable')
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
