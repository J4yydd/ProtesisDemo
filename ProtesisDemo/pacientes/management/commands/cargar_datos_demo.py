from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from pacientes.models import (
    Expediente,
    LugarCaptura,
    MedicionAntropometrica,
    Paciente,
    SolicitudProtesis,
)
from usuarios.models import Rol, Usuario


class Command(BaseCommand):
    help = "Carga pacientes, expedientes y mediciones de demostración basados en el prototipo SPMEP."

    def handle(self, *args, **options):
        self.stdout.write("Cargando datos de demostración...")

        rol_enfermera, _ = Rol.objects.get_or_create(nombre="Enfermera")
        rol_psicologa, _ = Rol.objects.get_or_create(nombre="Psicóloga")

        # Lugares de captura
        lugar_1, _ = LugarCaptura.objects.get_or_create(
            nombre="Clínica Rosa – Sala de captura 1",
            defaults={"direccion": "Av. Universidad 102, Zacatecas", "activo": True},
        )
        lugar_2, _ = LugarCaptura.objects.get_or_create(
            nombre="Hospital Regional – Consultorio 4",
            defaults={"direccion": "Calzada Solidaridad s/n, Guadalupe", "activo": True},
        )
        lugar_3, _ = LugarCaptura.objects.get_or_create(
            nombre="Centro Oncológico Norte – Sala B",
            defaults={"direccion": "Blvd. Héroes de Chapultepec 300, Zacatecas", "activo": True},
        )

        hoy = timezone.localdate()

        with transaction.atomic():
            # Limpiar solicitudes existentes para evitar violación de PROTECT al actualizar
            SolicitudProtesis.objects.all().delete()
            # Paciente 1: María Fernanda Rojas Pérez (Con expediente, medición vigente de hace 2 días)
            p1, _ = Paciente.objects.update_or_create(
                curp="ROPM850214MSLBRR05",
                defaults={
                    "nombre_completo": "María Fernanda Rojas Pérez",
                    "fecha_nacimiento": "1985-02-14",
                    "telefono": "667 123 4567",
                    "correo": "mfrojas@correo.com",
                    "nivel_estudios": "Licenciatura",
                    "ingresos_mensuales": 9500.00,
                    "estado_civil": "Casada",
                    "tiene_hijos": "Sí",
                    "trabaja_fuera_casa": "Sí",
                },
            )
            e1, _ = Expediente.objects.update_or_create(
                paciente=p1,
                defaults={
                    "fecha_diagnostico": "2024-01-10",
                    "tipo_cancer": "Carcinoma ductal",
                    "tratamiento": "Quimioterapia",
                    "fecha_mastectomia": "2024-06-18",
                    "lateralidad": "Izquierda",
                    "servicio_medico": "Oncología",
                    "cuenta_con_protesis": "No",
                    "mano_dominante": "Derecha",
                    "consentimiento_seguimiento": True,
                    "consentimiento_captura": True,
                    "observaciones": "Buena respuesta al tratamiento. Prefiere citas por la mañana.",
                },
            )
            MedicionAntropometrica.objects.filter(expediente=e1).delete()
            MedicionAntropometrica.objects.create(
                expediente=e1,
                fecha_medicion=hoy - timedelta(days=2),
                lr=18.4,
                mp=20.8,
                ir=16.9,
                mr=19.5,
                torax=89.0,
                estatura=1.62,
                peso=66.0,
                registrado_por_nombre="Enfermera Demo",
            )
            MedicionAntropometrica.objects.create(
                expediente=e1,
                fecha_medicion=hoy - timedelta(days=60),
                lr=18.4,
                mp=20.8,
                ir=17.0,
                mr=19.6,
                torax=90.0,
                estatura=1.62,
                peso=68.0,
                registrado_por_nombre="Enfermera Demo",
            )
            MedicionAntropometrica.objects.create(
                expediente=e1,
                fecha_medicion=hoy - timedelta(days=150),
                lr=18.5,
                mp=21.0,
                ir=17.2,
                mr=19.8,
                torax=92.0,
                estatura=1.62,
                peso=72.0,
                registrado_por_nombre="Enfermera Demo",
            )

            # Paciente 2: Ana Lucía López González (Con expediente, medición vencida y solicitud activa)
            p2, _ = Paciente.objects.update_or_create(
                curp="LOGA900730MSLPNN08",
                defaults={
                    "nombre_completo": "Ana Lucía López González",
                    "fecha_nacimiento": "1990-07-30",
                    "telefono": "667 555 0192",
                    "correo": "ana.lopez@example.com",
                    "nivel_estudios": "Preparatoria",
                    "estado_civil": "Soltera",
                    "tiene_hijos": "No",
                    "trabaja_fuera_casa": "Sí",
                },
            )
            e2, _ = Expediente.objects.update_or_create(
                paciente=p2,
                defaults={
                    "fecha_diagnostico": "2024-11-02",
                    "tipo_cancer": "Carcinoma lobulillar",
                    "tratamiento": "Radioterapia",
                    "fecha_mastectomia": "2025-02-10",
                    "lateralidad": "Derecha",
                    "servicio_medico": "Oncología",
                    "cuenta_con_protesis": "No",
                    "mano_dominante": "Derecha",
                    "consentimiento_seguimiento": True,
                    "consentimiento_captura": True,
                    "observaciones": "Solicitud programada.",
                },
            )
            MedicionAntropometrica.objects.filter(expediente=e2).delete()
            m2_1 = MedicionAntropometrica.objects.create(
                expediente=e2,
                fecha_medicion=hoy - timedelta(days=10),
                lr=17.9,
                mp=20.1,
                ir=16.5,
                mr=18.8,
                torax=86.0,
                estatura=1.58,
                peso=60.0,
                registrado_por_nombre="Psicóloga Demo",
            )
            SolicitudProtesis.objects.filter(paciente=p2).delete()
            SolicitudProtesis.objects.create(
                expediente=e2,
                paciente=p2,
                lugar_captura=lugar_1,
                medicion=m2_1,
                fecha_hora_cita=timezone.now() + timedelta(days=5),
                estado=SolicitudProtesis.Estado.PENDIENTE,
                solicitado_por_nombre="Psicóloga Demo",
                enviado_escritorio=True,
            )

            # Paciente 3: Carmen Martínez Hernández (Con expediente, SIN consentimiento de captura)
            p3, _ = Paciente.objects.update_or_create(
                curp="MAHC781105MSLRRL02",
                defaults={
                    "nombre_completo": "Carmen Martínez Hernández",
                    "fecha_nacimiento": "1978-11-05",
                    "telefono": "667 888 2210",
                    "estado_civil": "Casada",
                    "tiene_hijos": "Sí",
                },
            )
            e3, _ = Expediente.objects.update_or_create(
                paciente=p3,
                defaults={
                    "fecha_diagnostico": "2024-06-21",
                    "tipo_cancer": "Carcinoma ductal",
                    "tratamiento": "Quimioterapia",
                    "fecha_mastectomia": "2024-12-05",
                    "lateralidad": "Bilateral",
                    "servicio_medico": "IMSS",
                    "cuenta_con_protesis": "No",
                    "mano_dominante": "Derecha",
                    "consentimiento_seguimiento": True,
                    "consentimiento_captura": False,  # Sin consentimiento para captura (RN-21)
                    "observaciones": "Pendiente de firma de consentimiento de captura.",
                },
            )
            MedicionAntropometrica.objects.filter(expediente=e3).delete()
            MedicionAntropometrica.objects.create(
                expediente=e3,
                fecha_medicion=hoy - timedelta(days=3),
                lr=19.0,
                mp=22.0,
                ir=18.0,
                mr=20.5,
                torax=95.0,
                estatura=1.60,
                peso=74.0,
                registrado_por_nombre="Enfermera Demo",
            )

            # Paciente 4: Lucía Torres Ibarra (Medición vencida de hace 12 días)
            p4, _ = Paciente.objects.update_or_create(
                curp="TOIL880922MSLRBC04",
                defaults={
                    "nombre_completo": "Lucía Torres Ibarra",
                    "fecha_nacimiento": "1988-09-22",
                    "telefono": "667 410 7733",
                    "estado_civil": "Soltera",
                },
            )
            e4, _ = Expediente.objects.update_or_create(
                paciente=p4,
                defaults={
                    "fecha_diagnostico": "2024-09-05",
                    "tipo_cancer": "Carcinoma ductal",
                    "tratamiento": "Hormonal",
                    "fecha_mastectomia": "2025-01-15",
                    "lateralidad": "Derecha",
                    "servicio_medico": "ISSSTE",
                    "cuenta_con_protesis": "No",
                    "mano_dominante": "Derecha",
                    "consentimiento_seguimiento": True,
                    "consentimiento_captura": True,
                    "observaciones": "Requiere actualización de medición para cita.",
                },
            )
            MedicionAntropometrica.objects.filter(expediente=e4).delete()
            MedicionAntropometrica.objects.create(
                expediente=e4,
                fecha_medicion=hoy - timedelta(days=12),
                lr=18.0,
                mp=20.4,
                ir=16.7,
                mr=19.0,
                torax=87.0,
                estatura=1.65,
                peso=64.0,
                registrado_por_nombre="Enfermera Demo",
            )

            # Paciente 5: Rosa Elena García Valdez (SIN expediente clínico)
            p5, _ = Paciente.objects.update_or_create(
                curp="GAVR950318MSLRLS09",
                defaults={
                    "nombre_completo": "Rosa Elena García Valdez",
                    "fecha_nacimiento": "1995-03-18",
                    "telefono": "667 300 4411",
                    "nivel_estudios": "Secundaria",
                    "estado_civil": "Soltera",
                    "tiene_hijos": "No",
                },
            )
            # Aseguramos que no tenga expediente
            Expediente.objects.filter(paciente=p5).delete()

        self.stdout.write(self.style.SUCCESS("¡Datos de demostración cargados exitosamente!"))

