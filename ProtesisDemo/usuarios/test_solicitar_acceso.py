from django.test import TestCase
from django.urls import reverse

from .models import Rol, SolicitudAcceso, Usuario
from .views import (
    SESION_CORREO,
    SESION_ID_ROL,
    SESION_ID_USUARIO,
    SESION_NOMBRE,
    SESION_ROL,
)


class SolicitarAccesoTests(TestCase):
    def setUp(self):
        self.rol_enfermera = Rol.objects.get(nombre="Enfermera")
        self.rol_psicologa = Rol.objects.get(nombre="Psicóloga")
        self.rol_admin = Rol.objects.get(nombre="Administrador")
        self.rol_doctor = Rol.objects.get(nombre="Doctor")
        self.admin = Usuario.objects.create(
            nombre="Admin Prueba",
            correo_electronico="admin@example.com",
            contrasena_hash="hash-placeholder",
            rol=self.rol_admin,
            activo=True,
        )

    def _datos(self, **extra):
        datos = {
            "nombre_completo": "María López",
            "correo_electronico": "maria@example.com",
            "telefono": "5512345678",
            "curp": "LOPM800101MDFXXX01",
            "rfc": "LOPM800101XXX",
            "matricula_institucional": "MAT-001",
            "cedula_profesional": "CED-001",
            "adscripcion_unidad": "Unidad 1",
            "categoria_puesto": "Enfermera",
            "rol": self.rol_enfermera.id_rol,
        }
        datos.update(extra)
        return datos

    def _sesion_admin(self):
        sesion = self.client.session
        sesion[SESION_ID_USUARIO] = self.admin.id_usuario
        sesion[SESION_ID_ROL] = self.admin.rol.id_rol
        sesion[SESION_ROL] = self.admin.rol.nombre
        sesion[SESION_CORREO] = self.admin.correo_electronico
        sesion[SESION_NOMBRE] = self.admin.nombre
        sesion.save()

    def test_solicitar_acceso_es_publico_y_muestra_formulario(self):
        respuesta = self.client.get(reverse("usuarios:solicitar_acceso"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Solicitar acceso")
        self.assertContains(respuesta, "nombre_completo")
        self.assertContains(respuesta, "Enfermera")
        self.assertContains(respuesta, "Psicóloga")
        self.assertNotContains(respuesta, f'value="{self.rol_admin.id_rol}"')
        self.assertNotContains(respuesta, f'value="{self.rol_doctor.id_rol}"')

    def test_post_valido_crea_solicitud_pendiente(self):
        respuesta = self.client.post(
            reverse("usuarios:solicitar_acceso"),
            self._datos(),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("usuarios:solicitud_enviada"))
        solicitud = SolicitudAcceso.objects.get(correo_electronico="maria@example.com")
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertEqual(solicitud.rol, self.rol_enfermera)
        self.assertFalse(
            Usuario.objects.filter(correo_electronico="maria@example.com").exists()
        )
        self.assertNotIn(SESION_ID_USUARIO, self.client.session)

    def test_post_no_permite_controlar_estado(self):
        self.client.post(
            reverse("usuarios:solicitar_acceso"),
            self._datos(estado=SolicitudAcceso.Estado.APROBADA),
        )
        solicitud = SolicitudAcceso.objects.get(correo_electronico="maria@example.com")
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)

    def test_psicologa_es_opcion_valida(self):
        self.client.post(
            reverse("usuarios:solicitar_acceso"),
            self._datos(rol=self.rol_psicologa.id_rol),
        )
        solicitud = SolicitudAcceso.objects.get(correo_electronico="maria@example.com")
        self.assertEqual(solicitud.rol, self.rol_psicologa)

    def test_administrador_y_doctor_no_pueden_solicitarse(self):
        for rol in (self.rol_admin, self.rol_doctor):
            with self.subTest(rol=rol.nombre):
                respuesta = self.client.post(
                    reverse("usuarios:solicitar_acceso"),
                    self._datos(rol=rol.id_rol),
                )
                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(
                    SolicitudAcceso.objects.filter(
                        correo_electronico="maria@example.com"
                    ).exists()
                )

    def test_correo_invalido_y_campos_obligatorios(self):
        respuesta = self.client.post(
            reverse("usuarios:solicitar_acceso"),
            self._datos(correo_electronico="no-es-correo", nombre_completo=""),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(SolicitudAcceso.objects.exists())
        self.assertContains(respuesta, "correo electrónico")

    def test_correo_con_usuario_existente_no_crea_solicitud(self):
        respuesta = self.client.post(
            reverse("usuarios:solicitar_acceso"),
            self._datos(correo_electronico="admin@example.com"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Este correo ya se encuentra autorizado para acceder al sistema.",
        )
        self.assertFalse(
            SolicitudAcceso.objects.filter(
                correo_electronico="admin@example.com"
            ).exists()
        )

    def test_correo_con_pendiente_existente_no_crea_otra(self):
        self.client.post(reverse("usuarios:solicitar_acceso"), self._datos())
        respuesta = self.client.post(
            reverse("usuarios:solicitar_acceso"),
            self._datos(nombre_completo="Otra Persona"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Ya existe una solicitud pendiente asociada a este correo.",
        )
        self.assertEqual(
            SolicitudAcceso.objects.filter(
                correo_electronico="maria@example.com"
            ).count(),
            1,
        )

    def test_correo_con_rechazada_puede_crear_nueva(self):
        SolicitudAcceso.objects.create(
            nombre_completo="María López",
            correo_electronico="maria@example.com",
            telefono="5512345678",
            curp="LOPM800101MDFXXX01",
            rfc="LOPM800101XXX",
            matricula_institucional="MAT-001",
            cedula_profesional="CED-001",
            adscripcion_unidad="Unidad 1",
            categoria_puesto="Enfermera",
            rol=self.rol_enfermera,
            estado=SolicitudAcceso.Estado.RECHAZADA,
        )
        self.client.post(reverse("usuarios:solicitar_acceso"), self._datos())
        self.assertEqual(
            SolicitudAcceso.objects.filter(
                correo_electronico="maria@example.com"
            ).count(),
            2,
        )
        self.assertTrue(
            SolicitudAcceso.objects.filter(
                correo_electronico="maria@example.com",
                estado=SolicitudAcceso.Estado.PENDIENTE,
            ).exists()
        )

    def test_aprobada_historica_sin_usuario_puede_crear_nueva(self):
        SolicitudAcceso.objects.create(
            nombre_completo="María López",
            correo_electronico="maria@example.com",
            telefono="5512345678",
            curp="LOPM800101MDFXXX01",
            rfc="LOPM800101XXX",
            matricula_institucional="MAT-001",
            cedula_profesional="CED-001",
            adscripcion_unidad="Unidad 1",
            categoria_puesto="Enfermera",
            rol=self.rol_enfermera,
            estado=SolicitudAcceso.Estado.APROBADA,
        )
        self.client.post(reverse("usuarios:solicitar_acceso"), self._datos())
        self.assertEqual(
            SolicitudAcceso.objects.filter(
                correo_electronico="maria@example.com"
            ).count(),
            2,
        )

    def test_solicitud_aparece_en_listado_admin(self):
        self.client.post(reverse("usuarios:solicitar_acceso"), self._datos())
        self._sesion_admin()
        respuesta = self.client.get(reverse("usuarios:administrar_usuarios"))
        self.assertContains(respuesta, "María López")
        self.assertContains(respuesta, "maria@example.com")
        self.assertContains(respuesta, "Pendiente")

    def test_login_muestra_enlace_solicitar_acceso(self):
        respuesta = self.client.get(reverse("usuarios:login"))
        self.assertContains(respuesta, "Solicitar acceso")
        self.assertContains(respuesta, reverse("usuarios:solicitar_acceso"))

    def test_confirmacion_exitosa_se_muestra(self):
        respuesta = self.client.post(
            reverse("usuarios:solicitar_acceso"),
            self._datos(),
            follow=True,
        )
        self.assertEqual(respuesta.resolver_match.url_name, "solicitud_enviada")
        self.assertContains(
            respuesta,
            "Tu solicitud fue enviada correctamente y está pendiente de revisión.",
        )
