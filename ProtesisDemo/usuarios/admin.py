from django.contrib import admin

from .models import Rol, SolicitudAcceso, Usuario


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("id_rol", "nombre")


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("id_usuario", "nombre", "correo_electronico", "rol", "activo")


@admin.register(SolicitudAcceso)
class SolicitudAccesoAdmin(admin.ModelAdmin):
    list_display = (
        "id_solicitud_acceso",
        "nombre_completo",
        "correo_electronico",
        "rol",
        "estado",
    )
