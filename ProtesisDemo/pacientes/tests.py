from datetime import timedelta
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Rol, Usuario
from usuarios.views import (
    SESION_CORREO,
    SESION_ID_ROL,
    SESION_ID_USUARIO,
    SESION_NOMBRE,
    SESION_ROL,
)

from .models import (
    Expediente,
    LugarCaptura,
    MedicionAntropometrica,
    Paciente,
    SolicitudProtesis,
)
from .services import EnvioCapturaService


class PacientesBaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.rol_enfermera, _ = Rol.objects.get_or_create(nombre="Enfermera")
        self.rol_psicologa, _ = Rol.objects.get_or_create(nombre="Psicóloga")
        self.rol_admin, _ = Rol.objects.get_or_create(nombre="Administrador")

        self.usuario_enfermera = Usuario.objects.create(
            nombre="Enfermera Demo",
            correo_electronico="enfermera@example.com",
            contrasena_hash="HASH",
            rol=self.rol_enfermera,
            activo=True,
        )

        self.usuario_admin = Usuario.objects.create(
            nombre="Admin Demo",
            correo_electronico="admin@example.com",
            contrasena_hash="HASH",
            rol=self.rol_admin,
            activo=True,
        )

        self.lugar_1, _ = LugarCaptura.objects.get_or_create(
            nombre="Clínica Rosa – Sala de captura 1",
            defaults={"direccion": "Zacatecas Centro", "activo": True},
        )
        self.lugar_2, _ = LugarCaptura.objects.get_or_create(
            nombre="Hospital Regional – Consultorio 4",
            defaults={"direccion": "Guadalupe", "activo": True},
        )

    def login_como(self, usuario):
        session = self.client.session
        session[SESION_ID_USUARIO] = usuario.id_usuario
        session[SESION_ID_ROL] = usuario.rol.id_rol
        session[SESION_ROL] = usuario.rol.nombre
        session[SESION_CORREO] = usuario.correo_electronico
        session[SESION_NOMBRE] = usuario.nombre
        session.save()


class CUW01RegistrarPacienteTests(PacientesBaseTestCase):
    def test_acceso_denegado_sin_sesion(self):
        url = reverse("pacientes:nuevo_paciente")
        response = self.client.get(url)
        self.assertRedirects(response, reverse("usuarios:login"))

    def test_acceso_denegado_para_rol_no_autorizado(self):
        self.login_como(self.usuario_admin)
        url = reverse("pacientes:nuevo_paciente")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_acceso_permitido_para_enfermera(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:nuevo_paciente")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registrar paciente")

    def test_registro_exitoso_con_campos_obligatorios_y_opcionales(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:nuevo_paciente")
        data = {
            "nombre_completo": "María Fernanda Rojas Pérez",
            "fecha_nacimiento": "1985-02-14",
            "telefono": "667 123 4567",
            "curp": "ROPM850214MSLBRR05",
            "correo": "mfrojas@correo.com",
            "nivel_estudios": "Licenciatura",
            "ingresos_mensuales": "8500.00",
            "estado_civil": "Casada",
            "tiene_hijos": "Sí",
            "trabaja_fuera_casa": "Sí",
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse("pacientes:detalle", kwargs={"curp": "ROPM850214MSLBRR05"}))

        paciente = Paciente.objects.get(curp="ROPM850214MSLBRR05")
        self.assertEqual(paciente.nombre_completo, "María Fernanda Rojas Pérez")
        self.assertEqual(str(paciente.fecha_nacimiento), "1985-02-14")
        self.assertEqual(paciente.telefono, "667 123 4567")
        self.assertEqual(paciente.correo, "mfrojas@correo.com")
        self.assertEqual(paciente.nivel_estudios, "Licenciatura")

    def test_error_curp_invalida_longitud(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:nuevo_paciente")
        data = {
            "nombre_completo": "Rosa García",
            "fecha_nacimiento": "1990-01-01",
            "telefono": "667 000 0000",
            "curp": "CURP_CORTA",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La CURP debe tener exactamente 18 caracteres alfanuméricos.")
        self.assertFalse(Paciente.objects.filter(nombre_completo="Rosa García").exists())

    def test_error_curp_duplicada_rn04(self):
        Paciente.objects.create(
            curp="ROPM850214MSLBRR05",
            nombre_completo="Paciente Uno",
            fecha_nacimiento="1985-02-14",
            telefono="667 123 4567",
        )
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:nuevo_paciente")
        data = {
            "nombre_completo": "Paciente Dos",
            "fecha_nacimiento": "1990-05-10",
            "telefono": "667 999 8888",
            "curp": "ROPM850214MSLBRR05",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe un paciente con la CURP ROPM850214MSLBRR05")

    def test_error_fecha_nacimiento_futura_rn06(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:nuevo_paciente")
        manana = timezone.localdate() + timedelta(days=1)
        data = {
            "nombre_completo": "Paciente Futura",
            "fecha_nacimiento": str(manana),
            "telefono": "667 123 4567",
            "curp": "ABCD850214MSLBRR01",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La fecha de nacimiento no puede ser futura.")

    def test_error_paciente_menor_de_edad_rn07(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:nuevo_paciente")
        hace_17_anos = timezone.localdate() - timedelta(days=365 * 17)
        data = {
            "nombre_completo": "Paciente Menor",
            "fecha_nacimiento": str(hace_17_anos),
            "telefono": "667 123 4567",
            "curp": "ABCD080214MSLBRR01",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No se pueden registrar pacientes menores de edad.")


class CUW02RegistrarExpedienteTests(PacientesBaseTestCase):
    def setUp(self):
        super().setUp()
        self.paciente = Paciente.objects.create(
            curp="ROPM850214MSLBRR05",
            nombre_completo="María Fernanda Rojas Pérez",
            fecha_nacimiento="1985-02-14",
            telefono="667 123 4567",
        )

    def test_creacion_exitosa_expediente_y_primera_medicion(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:nuevo_expediente", kwargs={"curp": self.paciente.curp})
        data = {
            # Antecedentes oncológicos (RN-12)
            "fecha_diagnostico": "2024-01-10",
            "tipo_cancer": "Carcinoma ductal",
            "tratamiento": "Quimioterapia",
            "fecha_mastectomia": "2024-06-18",
            "lateralidad": "Izquierda",
            "servicio_medico": "Oncología",
            "cuenta_con_protesis": "No",
            "mano_dominante": "Derecha",
            "observaciones": "Paciente tolera bien tratamiento.",
            "consentimiento_seguimiento": True,
            "consentimiento_captura": True,
            # Primera medición (RN-13)
            "fecha_medicion": str(timezone.localdate()),
            "lr": "18.40",
            "mp": "20.80",
            "ir": "16.90",
            "mr": "19.50",
            "torax": "89.00",
            "estatura": "1.62",
            "peso": "66.00",
            "observaciones_medicion": "Medición inicial de control",
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse("pacientes:detalle", kwargs={"curp": self.paciente.curp}))

        self.paciente.refresh_from_db()
        self.assertTrue(self.paciente.tiene_expediente())
        exp = self.paciente.expediente
        self.assertEqual(exp.lateralidad, "Izquierda")
        self.assertTrue(exp.consentimiento_seguimiento)
        self.assertTrue(exp.consentimiento_captura)
        self.assertEqual(exp.mediciones.count(), 1)

        primera_med = exp.mediciones.first()
        self.assertEqual(float(primera_med.lr), 18.40)
        self.assertTrue(primera_med.esta_vigente())
        self.assertEqual(exp.obtener_medicion_vigente(), primera_med)

    def test_falla_si_no_se_acepta_consentimiento_seguimiento(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:nuevo_expediente", kwargs={"curp": self.paciente.curp})
        data = {
            "fecha_diagnostico": "2024-01-10",
            "tipo_cancer": "Carcinoma ductal",
            "tratamiento": "Quimioterapia",
            "fecha_mastectomia": "2024-06-18",
            "lateralidad": "Izquierda",
            "servicio_medico": "Oncología",
            "cuenta_con_protesis": "No",
            "mano_dominante": "Derecha",
            "consentimiento_seguimiento": False,
            "consentimiento_captura": True,
            "fecha_medicion": str(timezone.localdate()),
            "lr": "18.40",
            "mp": "20.80",
            "ir": "16.90",
            "mr": "19.50",
            "torax": "89.00",
            "estatura": "1.62",
            "peso": "66.00",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Debes registrar el consentimiento para el seguimiento y uso de datos para poder guardar el expediente.",
        )
        self.assertFalse(self.paciente.tiene_expediente())

    def test_falla_fecha_mastectomia_anterior_a_diagnostico(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:nuevo_expediente", kwargs={"curp": self.paciente.curp})
        data = {
            "fecha_diagnostico": "2025-05-10",
            "fecha_mastectomia": "2024-01-10",  # Anterior a diagnóstico
            "tipo_cancer": "Carcinoma ductal",
            "tratamiento": "Quimioterapia",
            "lateralidad": "Izquierda",
            "servicio_medico": "Oncología",
            "cuenta_con_protesis": "No",
            "mano_dominante": "Derecha",
            "consentimiento_seguimiento": True,
            "fecha_medicion": str(timezone.localdate()),
            "lr": "18.40",
            "mp": "20.80",
            "ir": "16.90",
            "mr": "19.50",
            "torax": "89.00",
            "estatura": "1.62",
            "peso": "66.00",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "La fecha de mastectomía no puede ser anterior a la de diagnóstico.",
        )

    def test_registrar_nueva_medicion_adicional(self):
        self.login_como(self.usuario_enfermera)
        # Crear expediente con primera medición vencida (hace 10 días)
        exp = Expediente.objects.create(
            paciente=self.paciente,
            fecha_diagnostico="2024-01-10",
            tipo_cancer="Carcinoma ductal",
            tratamiento="Quimioterapia",
            fecha_mastectomia="2024-06-18",
            lateralidad="Izquierda",
            servicio_medico="Oncología",
            cuenta_con_protesis="No",
            mano_dominante="Derecha",
            consentimiento_seguimiento=True,
            consentimiento_captura=True,
        )
        med_antigua = MedicionAntropometrica.objects.create(
            expediente=exp,
            fecha_medicion=timezone.localdate() - timedelta(days=10),
            lr=18.0,
            mp=20.0,
            ir=16.0,
            mr=19.0,
            torax=88.0,
            estatura=1.62,
            peso=65.0,
        )
        self.assertFalse(med_antigua.esta_vigente())
        self.assertIsNone(exp.obtener_medicion_vigente())

        # Registrar nueva medición hoy
        url_nueva_med = reverse("pacientes:nueva_medicion", kwargs={"id_expediente": exp.id_expediente})
        data = {
            "fecha_medicion": str(timezone.localdate()),
            "lr": "18.20",
            "mp": "20.50",
            "ir": "16.80",
            "mr": "19.20",
            "torax": "89.00",
            "estatura": "1.62",
            "peso": "66.00",
            "observaciones": "Control posterior a 10 días",
        }
        response = self.client.post(url_nueva_med, data)
        self.assertRedirects(response, reverse("pacientes:detalle", kwargs={"curp": self.paciente.curp}))

        self.assertEqual(exp.mediciones.count(), 2)
        nueva_med = exp.obtener_medicion_vigente()
        self.assertIsNotNone(nueva_med)
        self.assertEqual(float(nueva_med.lr), 18.20)


class CUW11SolicitarProtesisTests(PacientesBaseTestCase):
    def setUp(self):
        super().setUp()
        self.paciente = Paciente.objects.create(
            curp="ROPM850214MSLBRR05",
            nombre_completo="María Fernanda Rojas Pérez",
            fecha_nacimiento="1985-02-14",
            telefono="667 123 4567",
        )
        self.expediente = Expediente.objects.create(
            paciente=self.paciente,
            fecha_diagnostico="2024-01-10",
            tipo_cancer="Carcinoma ductal",
            tratamiento="Quimioterapia",
            fecha_mastectomia="2024-06-18",
            lateralidad="Izquierda",
            servicio_medico="Oncología",
            cuenta_con_protesis="No",
            mano_dominante="Derecha",
            consentimiento_seguimiento=True,
            consentimiento_captura=True,
        )
        self.medicion = MedicionAntropometrica.objects.create(
            expediente=self.expediente,
            fecha_medicion=timezone.localdate(),
            lr=18.4,
            mp=20.8,
            ir=16.9,
            mr=19.5,
            torax=89.0,
            estatura=1.62,
            peso=66.0,
        )

    def test_solicitud_exitosa_flujo_normal(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:solicitar_protesis", kwargs={"id_expediente": self.expediente.id_expediente})
        cita = timezone.now() + timedelta(days=2)
        data = {
            "lugar_captura": self.lugar_1.id_lugar,
            "fecha_hora_cita": cita.strftime("%Y-%m-%dT%H:%M"),
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse("pacientes:detalle", kwargs={"curp": self.paciente.curp}))

        solicitud = SolicitudProtesis.objects.filter(paciente=self.paciente).first()
        self.assertIsNotNone(solicitud)
        self.assertEqual(solicitud.estado, SolicitudProtesis.Estado.PENDIENTE)
        self.assertEqual(solicitud.lugar_captura, self.lugar_1)
        self.assertEqual(solicitud.medicion, self.medicion)
        self.assertTrue(solicitud.enviado_escritorio)

    def test_bloqueo_si_consentimiento_captura_no_aprobado_rn21(self):
        self.expediente.consentimiento_captura = False
        self.expediente.save()

        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:solicitar_protesis", kwargs={"id_expediente": self.expediente.id_expediente})
        response = self.client.get(url, follow=True)
        self.assertContains(response, "El paciente no tiene aprobado el consentimiento para la captura.")
        self.assertFalse(SolicitudProtesis.objects.filter(paciente=self.paciente).exists())

    def test_bloqueo_si_ya_existe_solicitud_activa_rn22(self):
        # Crear una solicitud activa previa
        SolicitudProtesis.objects.create(
            expediente=self.expediente,
            paciente=self.paciente,
            lugar_captura=self.lugar_1,
            medicion=self.medicion,
            fecha_hora_cita=timezone.now() + timedelta(days=1),
            estado=SolicitudProtesis.Estado.PENDIENTE,
        )

        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:solicitar_protesis", kwargs={"id_expediente": self.expediente.id_expediente})
        response = self.client.get(url, follow=True)
        self.assertContains(response, "El paciente ya tiene una solicitud activa")

    def test_bloqueo_si_medicion_no_esta_vigente_mas_de_7_dias(self):
        # Cambiamos fecha de medición a hace 8 días
        self.medicion.fecha_medicion = timezone.localdate() - timedelta(days=8)
        self.medicion.save()

        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:solicitar_protesis", kwargs={"id_expediente": self.expediente.id_expediente})
        response = self.client.get(url, follow=True)
        self.assertContains(response, "No hay una medición antropométrica vigente")
        self.assertContains(response, "supera los 7 días de vigencia")

    def test_error_fecha_cita_pasada_rn24(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:solicitar_protesis", kwargs={"id_expediente": self.expediente.id_expediente})
        cita_pasada = timezone.localtime(timezone.now()) - timedelta(days=1)
        data = {
            "lugar_captura": self.lugar_1.id_lugar,
            "fecha_hora_cita": cita_pasada.strftime("%Y-%m-%dT%H:%M"),
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "La fecha y hora de la cita no pueden ser anteriores a la actual.",
        )

    @override_settings(SIMULAR_ERROR_ENVIO_CAPTURA=True)
    def test_excepcion_error_al_enviar_a_captura_1_0_e2(self):
        self.login_como(self.usuario_enfermera)
        url = reverse("pacientes:solicitar_protesis", kwargs={"id_expediente": self.expediente.id_expediente})
        cita = timezone.now() + timedelta(days=3)
        data = {
            "lugar_captura": self.lugar_2.id_lugar,
            "fecha_hora_cita": cita.strftime("%Y-%m-%dT%H:%M"),
        }
        response = self.client.post(url, data, follow=True)
        self.assertContains(
            response,
            "La solicitud se guardó, pero no pudo enviarse al sistema de captura. Se reintentará el envío.",
        )

        solicitud = SolicitudProtesis.objects.filter(paciente=self.paciente).first()
        self.assertIsNotNone(solicitud)
        self.assertEqual(solicitud.estado, SolicitudProtesis.Estado.PENDIENTE)
        self.assertFalse(solicitud.enviado_escritorio)
