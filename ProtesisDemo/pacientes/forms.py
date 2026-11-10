import re
from datetime import date
from django import forms
from django.utils import timezone

from .models import (
    Expediente,
    LugarCaptura,
    MedicionAntropometrica,
    Paciente,
    SolicitudProtesis,
)

CURP_REGEX = re.compile(r"^[A-Z0-9]{18}$")

OPCIONES_NIVEL_ESTUDIOS = [
    ("", "Selecciona…"),
    ("Primaria", "Primaria"),
    ("Secundaria", "Secundaria"),
    ("Preparatoria", "Preparatoria"),
    ("Licenciatura", "Licenciatura"),
    ("Posgrado", "Posgrado"),
]

OPCIONES_ESTADO_CIVIL = [
    ("", "Selecciona…"),
    ("Soltera", "Soltera"),
    ("Casada", "Casada"),
    ("Unión libre", "Unión libre"),
    ("Divorciada", "Divorciada"),
    ("Viuda", "Viuda"),
]

OPCIONES_SI_NO = [
    ("", "Selecciona…"),
    ("Sí", "Sí"),
    ("No", "No"),
]

OPCIONES_TIPO_CANCER = [
    ("", "Selecciona…"),
    ("Carcinoma ductal", "Carcinoma ductal"),
    ("Carcinoma lobulillar", "Carcinoma lobulillar"),
    ("Otro", "Otro"),
]

OPCIONES_TRATAMIENTO = [
    ("", "Selecciona…"),
    ("Quimioterapia", "Quimioterapia"),
    ("Radioterapia", "Radioterapia"),
    ("Hormonal", "Hormonal"),
    ("Combinado", "Combinado"),
]


class PacienteForm(forms.ModelForm):
    nivel_estudios = forms.ChoiceField(
        choices=OPCIONES_NIVEL_ESTUDIOS,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Nivel de estudios",
    )
    estado_civil = forms.ChoiceField(
        choices=OPCIONES_ESTADO_CIVIL,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Estado civil",
    )
    tiene_hijos = forms.ChoiceField(
        choices=OPCIONES_SI_NO,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="¿Tiene hijos?",
    )
    trabaja_fuera_casa = forms.ChoiceField(
        choices=OPCIONES_SI_NO,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="¿Trabaja fuera de casa?",
    )

    class Meta:
        model = Paciente
        fields = [
            "nombre_completo",
            "fecha_nacimiento",
            "telefono",
            "curp",
            "correo",
            "nivel_estudios",
            "ingresos_mensuales",
            "estado_civil",
            "tiene_hijos",
            "trabaja_fuera_casa",
        ]
        widgets = {
            "nombre_completo": forms.TextInput(
                attrs={"placeholder": "Nombre(s) y apellidos"}
            ),
            "fecha_nacimiento": forms.DateInput(
                attrs={"type": "date"}
            ),
            "telefono": forms.TextInput(
                attrs={"type": "tel", "placeholder": "Ej. 667 123 4567"}
            ),
            "curp": forms.TextInput(
                attrs={"placeholder": "18 caracteres alfanuméricos", "maxlength": "18"}
            ),
            "correo": forms.EmailInput(
                attrs={"placeholder": "ejemplo@correo.com"}
            ),
            "ingresos_mensuales": forms.NumberInput(
                attrs={"placeholder": "Ej. 8500.00", "step": "100", "min": "0"}
            ),
        }

    def clean_curp(self):
        curp = self.cleaned_data.get("curp", "").strip().upper()
        if not curp:
            raise forms.ValidationError("La CURP es obligatoria.")
        if not CURP_REGEX.match(curp):
            raise forms.ValidationError("La CURP debe tener exactamente 18 caracteres alfanuméricos.")
        # Verificamos si ya existe el paciente (si es nuevo registro)
        if self.instance.pk != curp and Paciente.objects.filter(curp=curp).exists():
            raise forms.ValidationError("Ya existe un paciente registrado con esta CURP.")
        return curp

    def clean_nombre_completo(self):
        nombre = self.cleaned_data.get("nombre_completo", "").strip()
        if not nombre:
            raise forms.ValidationError("El nombre completo es obligatorio.")
        return nombre

    def clean_telefono(self):
        tel = self.cleaned_data.get("telefono", "").strip()
        if not tel:
            raise forms.ValidationError("El teléfono de contacto es obligatorio.")
        return tel

    def clean_fecha_nacimiento(self):
        fn = self.cleaned_data.get("fecha_nacimiento")
        if not fn:
            raise forms.ValidationError("La fecha de nacimiento es obligatoria.")
        hoy = timezone.localdate()
        if fn > hoy:
            raise forms.ValidationError("La fecha de nacimiento no puede ser futura.")
        # Calcular edad
        edad = hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
        if edad < 18:
            raise forms.ValidationError("No se pueden registrar pacientes menores de edad.")
        return fn


class ExpedienteForm(forms.ModelForm):
    tipo_cancer = forms.ChoiceField(
        choices=OPCIONES_TIPO_CANCER,
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Tipo de cáncer",
    )
    tratamiento = forms.ChoiceField(
        choices=OPCIONES_TRATAMIENTO,
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Tratamiento",
    )
    consentimiento_seguimiento = forms.BooleanField(
        required=False,
        label="El paciente consiente el seguimiento y uso de sus datos",
    )
    consentimiento_captura = forms.BooleanField(
        required=False,
        label="El paciente consiente la captura para la prótesis",
    )

    class Meta:
        model = Expediente
        fields = [
            "fecha_diagnostico",
            "tipo_cancer",
            "tratamiento",
            "fecha_mastectomia",
            "lateralidad",
            "servicio_medico",
            "cuenta_con_protesis",
            "mano_dominante",
            "observaciones",
            "consentimiento_seguimiento",
            "consentimiento_captura",
        ]
        widgets = {
            "fecha_diagnostico": forms.DateInput(attrs={"type": "date"}),
            "fecha_mastectomia": forms.DateInput(attrs={"type": "date"}),
            "lateralidad": forms.Select(attrs={"class": "form-control"}),
            "servicio_medico": forms.TextInput(attrs={"placeholder": "Ej. Oncología / IMSS / ISSSTE"}),
            "cuenta_con_protesis": forms.Select(attrs={"class": "form-control"}),
            "mano_dominante": forms.Select(attrs={"class": "form-control"}),
            "observaciones": forms.Textarea(
                attrs={"placeholder": "Notas relevantes del caso clínico (opcional)", "rows": 3}
            ),
        }

    def clean_consentimiento_seguimiento(self):
        cs = self.cleaned_data.get("consentimiento_seguimiento")
        if not cs:
            raise forms.ValidationError(
                "Debes registrar el consentimiento para el seguimiento y uso de datos para poder guardar el expediente."
            )
        return cs

    def clean(self):
        cleaned_data = super().clean()
        fd = cleaned_data.get("fecha_diagnostico")
        fm = cleaned_data.get("fecha_mastectomia")
        hoy = timezone.localdate()

        if fd and fd > hoy:
            self.add_error("fecha_diagnostico", "La fecha de diagnóstico no puede ser futura.")
        if fm and fm > hoy:
            self.add_error("fecha_mastectomia", "La fecha de mastectomía no puede ser futura.")

        if fd and fm and fm < fd:
            self.add_error("fecha_mastectomia", "La fecha de mastectomía no puede ser anterior a la de diagnóstico.")

        return cleaned_data


class MedicionForm(forms.ModelForm):
    class Meta:
        model = MedicionAntropometrica
        fields = [
            "fecha_medicion",
            "lr",
            "mp",
            "ir",
            "mr",
            "torax",
            "estatura",
            "peso",
            "observaciones",
        ]
        widgets = {
            "fecha_medicion": forms.DateInput(attrs={"type": "date"}),
            "lr": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "placeholder": "Ej. 18.40"}),
            "mp": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "placeholder": "Ej. 20.80"}),
            "ir": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "placeholder": "Ej. 16.90"}),
            "mr": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "placeholder": "Ej. 19.50"}),
            "torax": forms.NumberInput(attrs={"step": "0.1", "min": "0.01", "placeholder": "Ej. 89.0"}),
            "estatura": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "placeholder": "Ej. 1.62"}),
            "peso": forms.NumberInput(attrs={"step": "0.1", "min": "0.01", "placeholder": "Ej. 66.0"}),
            "observaciones": forms.Textarea(
                attrs={"placeholder": "Observaciones de la medición (opcional)", "rows": 2}
            ),
        }

    def __init__(self, *args, ultima_fecha=None, **kwargs):
        self.ultima_fecha = ultima_fecha
        super().__init__(*args, **kwargs)
        if not self.initial.get("fecha_medicion"):
            self.initial["fecha_medicion"] = timezone.localdate()

    def clean_fecha_medicion(self):
        fm = self.cleaned_data.get("fecha_medicion")
        if not fm:
            raise forms.ValidationError("La fecha de medición es obligatoria.")
        hoy = timezone.localdate()
        if fm > hoy:
            raise forms.ValidationError("La fecha de medición no puede ser futura.")
        if self.ultima_fecha and fm < self.ultima_fecha:
            raise forms.ValidationError(
                f"La fecha de medición no puede ser anterior a la última medición registrada ({self.ultima_fecha.strftime('%d/%m/%Y')})."
            )
        return fm

    def clean(self):
        cleaned_data = super().clean()
        campos_numericos = ["lr", "mp", "ir", "mr", "torax", "estatura", "peso"]
        for campo in campos_numericos:
            valor = cleaned_data.get(campo)
            if valor is not None and valor <= 0:
                self.add_error(campo, "Ingresa un valor numérico mayor a 0.")
        return cleaned_data


class SolicitudProtesisForm(forms.ModelForm):
    lugar_captura = forms.ModelChoiceField(
        queryset=LugarCaptura.objects.filter(activo=True),
        empty_label="Selecciona un lugar de captura…",
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Lugar de captura",
    )

    class Meta:
        model = SolicitudProtesis
        fields = [
            "lugar_captura",
            "fecha_hora_cita",
        ]
        widgets = {
            "fecha_hora_cita": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
        }

    def clean_fecha_hora_cita(self):
        fh = self.cleaned_data.get("fecha_hora_cita")
        if not fh:
            raise forms.ValidationError("La fecha y hora de la cita son obligatorias.")
        if timezone.is_naive(fh):
            fh = timezone.make_aware(fh, timezone.get_current_timezone())
        ahora = timezone.now()
        if fh < ahora:
            raise forms.ValidationError("La fecha y hora de la cita no pueden ser anteriores a la actual.")
        return fh
