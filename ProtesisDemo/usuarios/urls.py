from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("login/", views.login, name="login"),
    path("solicitar-acceso/", views.solicitar_acceso, name="solicitar_acceso"),
    path("solicitar-acceso/enviada/", views.solicitud_enviada, name="solicitud_enviada"),
    path("auth/google/", views.google_login, name="google_login"),
    path("auth/google/callback/", views.google_callback, name="google_callback"),
    path("panel/", views.panel, name="panel"),
    path("logout/", views.logout, name="logout"),
    path("administrar-usuarios/", views.administrar_usuarios, name="administrar_usuarios"),
    path(
        "administrar-usuarios/solicitud/<int:id_solicitud_acceso>/",
        views.detalle_solicitud,
        name="detalle_solicitud",
    ),
    path(
        "administrar-usuarios/solicitud/<int:id_solicitud_acceso>/aprobar/",
        views.confirmar_aprobacion,
        name="confirmar_aprobacion",
    ),
    path(
        "administrar-usuarios/solicitud/<int:id_solicitud_acceso>/rechazar/",
        views.confirmar_rechazo,
        name="confirmar_rechazo",
    ),
]
