from django.urls import path

from .views import (
    ExpedienteCreateView,
    MedicionCreateView,
    PacienteCreateView,
    PacienteDetailView,
    PacienteListView,
    SolicitudCreateView,
)

app_name = "pacientes"

urlpatterns = [
    path("pacientes/", PacienteListView.as_view(), name="lista"),
    path("pacientes/nuevo/", PacienteCreateView.as_view(), name="nuevo_paciente"),
    path("pacientes/<str:curp>/", PacienteDetailView.as_view(), name="detalle"),
    path(
        "pacientes/<str:curp>/expediente/nuevo/",
        ExpedienteCreateView.as_view(),
        name="nuevo_expediente",
    ),
    path(
        "expedientes/<int:id_expediente>/mediciones/nueva/",
        MedicionCreateView.as_view(),
        name="nueva_medicion",
    ),
    path(
        "expedientes/<int:id_expediente>/solicitar/",
        SolicitudCreateView.as_view(),
        name="solicitar_protesis",
    ),
]

