from django.contrib import admin

from .models import (
    Expediente,
    LugarCaptura,
    MedicionAntropometrica,
    Paciente,
    SolicitudProtesis,
)


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("curp", "nombre_completo", "telefono", "fecha_nacimiento", "fecha_registro")
    search_fields = ("curp", "nombre_completo", "telefono")


class MedicionInline(admin.TabularInline):
    model = MedicionAntropometrica
    extra = 0
    readonly_fields = ("fecha_registro",)


@admin.register(Expediente)
class ExpedienteAdmin(admin.ModelAdmin):
    list_display = ("id_expediente", "paciente", "lateralidad", "tipo_cancer", "consentimiento_captura", "fecha_registro")
    list_filter = ("lateralidad", "consentimiento_captura")
    inlines = [MedicionInline]


@admin.register(MedicionAntropometrica)
class MedicionAntropometricaAdmin(admin.ModelAdmin):
    list_display = ("id_medicion", "expediente", "fecha_medicion", "es_vigente", "registrado_por_nombre")
    list_filter = ("es_vigente", "fecha_medicion")


@admin.register(LugarCaptura)
class LugarCapturaAdmin(admin.ModelAdmin):
    list_display = ("id_lugar", "nombre", "activo")
    list_filter = ("activo",)


@admin.register(SolicitudProtesis)
class SolicitudProtesisAdmin(admin.ModelAdmin):
    list_display = ("id_solicitud", "paciente", "lugar_captura", "fecha_hora_cita", "estado", "enviado_escritorio")
    list_filter = ("estado", "enviado_escritorio", "lugar_captura")
