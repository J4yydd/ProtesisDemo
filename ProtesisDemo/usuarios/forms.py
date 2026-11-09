from django import forms

from .models import Rol, SolicitudAcceso, Usuario

ROLES_SOLICITUD_PUBLICA = ("Enfermera", "Psicóloga")


class SolicitudAccesoForm(forms.ModelForm):
    class Meta:
        model = SolicitudAcceso
        fields = [
            "nombre_completo",
            "correo_electronico",
            "telefono",
            "curp",
            "rfc",
            "matricula_institucional",
            "cedula_profesional",
            "adscripcion_unidad",
            "categoria_puesto",
            "rol",
        ]
        labels = {
            "nombre_completo": "Nombre completo",
            "correo_electronico": "Correo electrónico",
            "telefono": "Teléfono",
            "curp": "CURP",
            "rfc": "RFC",
            "matricula_institucional": "Matrícula institucional",
            "cedula_profesional": "Cédula profesional",
            "adscripcion_unidad": "Adscripción / unidad",
            "categoria_puesto": "Categoría / puesto",
            "rol": "Rol solicitado",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rol"].queryset = Rol.objects.filter(
            nombre__in=ROLES_SOLICITUD_PUBLICA
        ).order_by("nombre")
        self.fields["rol"].empty_label = "Selecciona un rol"

    def clean_rol(self):
        rol = self.cleaned_data["rol"]
        if rol.nombre not in ROLES_SOLICITUD_PUBLICA:
            raise forms.ValidationError("El rol seleccionado no está permitido.")
        return rol

    def clean_correo_electronico(self):
        correo = self.cleaned_data["correo_electronico"].strip()
        if Usuario.objects.filter(correo_electronico__iexact=correo).exists():
            raise forms.ValidationError(
                "Este correo ya se encuentra autorizado para acceder al sistema."
            )
        if SolicitudAcceso.objects.filter(
            correo_electronico__iexact=correo,
            estado=SolicitudAcceso.Estado.PENDIENTE,
        ).exists():
            raise forms.ValidationError(
                "Ya existe una solicitud pendiente asociada a este correo."
            )
        return correo
