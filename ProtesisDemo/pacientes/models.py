from datetime import timedelta
from django.db import models
from django.utils import timezone


class Paciente(models.Model):
    curp = models.CharField(
        max_length=18,
        primary_key=True,
        verbose_name="CURP",
    )
    nombre_completo = models.CharField(
        max_length=255,
        verbose_name="Nombre completo",
    )
    fecha_nacimiento = models.DateField(
        verbose_name="Fecha de nacimiento",
    )
    telefono = models.CharField(
        max_length=50,
        verbose_name="Teléfono de contacto",
    )
    correo = models.EmailField(
        blank=True,
        null=True,
        verbose_name="Correo electrónico",
    )
    nivel_estudios = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Nivel de estudios",
    )
    ingresos_mensuales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Ingresos mensuales (MXN)",
    )
    estado_civil = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Estado civil",
    )
    tiene_hijos = models.CharField(
        max_length=10,
        blank=True,
        default="",
        verbose_name="¿Tiene hijos?",
    )
    trabaja_fuera_casa = models.CharField(
        max_length=10,
        blank=True,
        default="",
        verbose_name="¿Trabaja fuera de casa?",
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro",
    )

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        ordering = ["-fecha_registro"]

    def __str__(self):
        return f"{self.nombre_completo} ({self.curp})"

    def tiene_expediente(self):
        return hasattr(self, "expediente") and self.expediente is not None

    def tiene_solicitud_activa(self):
        return self.solicitudes.filter(
            estado__in=[
                SolicitudProtesis.Estado.PENDIENTE,
                SolicitudProtesis.Estado.EN_PROCESO,
            ]
        ).exists()

    def solicitud_activa(self):
        return (
            self.solicitudes.filter(
                estado__in=[
                    SolicitudProtesis.Estado.PENDIENTE,
                    SolicitudProtesis.Estado.EN_PROCESO,
                ]
            )
            .order_by("-id_solicitud")
            .first()
        )


class Expediente(models.Model):
    class Lateralidad(models.TextChoices):
        IZQUIERDA = "Izquierda", "Izquierda"
        DERECHA = "Derecha", "Derecha"
        BILATERAL = "Bilateral", "Bilateral"

    class ManoDominante(models.TextChoices):
        DERECHA = "Derecha", "Derecha"
        IZQUIERDA = "Izquierda", "Izquierda"
        AMBIDIESTRA = "Ambidiestra", "Ambidiestra"

    id_expediente = models.AutoField(primary_key=True)
    paciente = models.OneToOneField(
        Paciente,
        on_delete=models.CASCADE,
        related_name="expediente",
        db_column="curp",
        verbose_name="Paciente",
    )
    fecha_diagnostico = models.DateField(
        verbose_name="Fecha de diagnóstico",
    )
    tipo_cancer = models.CharField(
        max_length=150,
        verbose_name="Tipo de cáncer",
    )
    tratamiento = models.CharField(
        max_length=150,
        verbose_name="Tratamiento",
    )
    fecha_mastectomia = models.DateField(
        verbose_name="Fecha de mastectomía",
    )
    lateralidad = models.CharField(
        max_length=20,
        choices=Lateralidad.choices,
        verbose_name="Lateralidad",
    )
    servicio_medico = models.CharField(
        max_length=150,
        verbose_name="Servicio médico",
    )
    cuenta_con_protesis = models.CharField(
        max_length=10,
        choices=[("Sí", "Sí"), ("No", "No")],
        default="No",
        verbose_name="¿Ya se cuenta con una prótesis?",
    )
    mano_dominante = models.CharField(
        max_length=20,
        choices=ManoDominante.choices,
        verbose_name="Mano dominante",
    )
    consentimiento_seguimiento = models.BooleanField(
        default=False,
        verbose_name="Consentimiento para seguimiento y uso de datos",
    )
    consentimiento_captura = models.BooleanField(
        default=False,
        verbose_name="Consentimiento para la captura",
    )
    observaciones = models.TextField(
        blank=True,
        default="",
        verbose_name="Observaciones",
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro",
    )

    class Meta:
        verbose_name = "Expediente"
        verbose_name_plural = "Expedientes"
        ordering = ["-fecha_registro"]

    def __str__(self):
        return f"Expediente #{self.id_expediente} - {self.paciente.nombre_completo}"

    def captura_aprobada(self):
        return bool(self.consentimiento_captura)

    def ultima_medicion(self):
        return self.mediciones.order_by("-fecha_medicion", "-id_medicion").first()

    def obtener_medicion_vigente(self, dias=7):
        ultima = self.ultima_medicion()
        if not ultima:
            return None
        hoy = timezone.localdate()
        if (hoy - ultima.fecha_medicion).days <= dias:
            return ultima
        return None


class MedicionAntropometrica(models.Model):
    id_medicion = models.AutoField(primary_key=True)
    expediente = models.ForeignKey(
        Expediente,
        on_delete=models.CASCADE,
        related_name="mediciones",
        db_column="id_expediente",
        verbose_name="Expediente",
    )
    fecha_medicion = models.DateField(
        verbose_name="Fecha de medición",
    )
    lr = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="LR (cm)",
    )
    mp = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="MP (cm)",
    )
    ir = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="IR (cm)",
    )
    mr = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="MR (cm)",
    )
    torax = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="Tórax (cm)",
    )
    estatura = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="Estatura (m)",
    )
    peso = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="Peso (kg)",
    )
    observaciones = models.TextField(
        blank=True,
        default="",
        verbose_name="Observaciones de la medición",
    )
    registrado_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        db_column="id_usuario",
        null=True,
        blank=True,
        verbose_name="Registrado por (Usuario)",
    )
    registrado_por_nombre = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Registrado por (Nombre)",
    )
    es_vigente = models.BooleanField(
        default=True,
        verbose_name="¿Es vigente?",
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro",
    )

    class Meta:
        verbose_name = "Medición Antropométrica"
        verbose_name_plural = "Mediciones Antropométricas"
        ordering = ["-fecha_medicion", "-id_medicion"]

    def __str__(self):
        return f"Medición #{self.id_medicion} ({self.fecha_medicion}) - Exp #{self.expediente_id}"

    def esta_vigente(self, dias=7):
        hoy = timezone.localdate()
        return (hoy - self.fecha_medicion).days <= dias

    def dias_desde_medicion(self):
        hoy = timezone.localdate()
        return (hoy - self.fecha_medicion).days

    def fecha_vencimiento(self, dias=7):
        return self.fecha_medicion + timedelta(days=dias)


class LugarCaptura(models.Model):
    id_lugar = models.AutoField(primary_key=True)
    nombre = models.CharField(
        max_length=255,
        verbose_name="Nombre del lugar",
    )
    direccion = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Dirección",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="¿Activo?",
    )

    class Meta:
        verbose_name = "Lugar de Captura"
        verbose_name_plural = "Lugares de Captura"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class SolicitudProtesis(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        EN_PROCESO = "En proceso", "En proceso"
        ATENDIDA = "Atendida", "Atendida"
        CANCELADA = "Cancelada", "Cancelada"

    id_solicitud = models.AutoField(primary_key=True)
    expediente = models.ForeignKey(
        Expediente,
        on_delete=models.CASCADE,
        related_name="solicitudes",
        db_column="id_expediente",
        verbose_name="Expediente",
    )
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name="solicitudes",
        db_column="curp",
        verbose_name="Paciente",
    )
    lugar_captura = models.ForeignKey(
        LugarCaptura,
        on_delete=models.PROTECT,
        db_column="id_lugar",
        verbose_name="Lugar de captura",
    )
    medicion = models.ForeignKey(
        MedicionAntropometrica,
        on_delete=models.PROTECT,
        db_column="id_medicion",
        verbose_name="Medición de referencia",
    )
    fecha_hora_cita = models.DateTimeField(
        verbose_name="Fecha y hora de la cita",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        verbose_name="Estado de la solicitud",
    )
    solicitado_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        db_column="id_usuario",
        null=True,
        blank=True,
        verbose_name="Solicitado por (Usuario)",
    )
    solicitado_por_nombre = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Solicitado por (Nombre)",
    )
    enviado_escritorio = models.BooleanField(
        default=False,
        verbose_name="Enviado al sistema SCPMEP Escritorio",
    )
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de solicitud",
    )

    class Meta:
        verbose_name = "Solicitud de Prótesis"
        verbose_name_plural = "Solicitudes de Prótesis"
        ordering = ["-fecha_solicitud"]

    def __str__(self):
        return f"Solicitud #{self.id_solicitud} - {self.paciente.nombre_completo} ({self.estado})"

    def marcar_pendiente(self):
        self.estado = self.Estado.PENDIENTE
