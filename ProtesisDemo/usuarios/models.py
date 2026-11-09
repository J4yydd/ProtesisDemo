from django.db import models


class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255)

    def __str__(self):
        return self.nombre


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255)
    correo_electronico = models.EmailField(unique=True)
    contrasena_hash = models.CharField(max_length=255)
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column="id_rol",
        related_name="usuarios",
    )
    activo = models.BooleanField()

    def __str__(self):
        return self.correo_electronico


class SolicitudAcceso(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        APROBADA = "Aprobada", "Aprobada"
        RECHAZADA = "Rechazada", "Rechazada"

    id_solicitud_acceso = models.AutoField(primary_key=True)
    nombre_completo = models.CharField(max_length=255)
    correo_electronico = models.EmailField()
    telefono = models.CharField(max_length=255)
    curp = models.CharField(max_length=255)
    rfc = models.CharField(max_length=255)
    matricula_institucional = models.CharField(max_length=255)
    cedula_profesional = models.CharField(max_length=255)
    adscripcion_unidad = models.CharField(max_length=255)
    categoria_puesto = models.CharField(max_length=255)
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column="id_rol",
        related_name="solicitudes_acceso",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    estado__in=["Pendiente", "Aprobada", "Rechazada"]
                ),
                name="solicitudacceso_estado_valido",
            ),
        ]

    def __str__(self):
        return self.correo_electronico
