from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Rol, SolicitudAcceso, Usuario
from .views import (
    CONTRASENA_HASH_GOOGLE,
    SESION_CORREO,
    SESION_ID_ROL,
    SESION_ID_USUARIO,
    SESION_NOMBRE,
    SESION_ROL,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ProcesarSolicitudesTests(TestCase):
    def setUp(self):
        self.rol_admin = Rol.objects.get(nombre="Administrador")
        self.rol_enfermera = Rol.objects.get(nombre="Enfermera")
        self.admin = Usuario.objects.create(
            nombre="Admin Prueba",
            correo_electronico="admin@example.com",
            contrasena_hash="hash-placeholder",
            rol=self.rol_admin,
            activo=True,
        )
        self.enfermera = Usuario.objects.create(
            nombre="Ana Pérez",
            correo_electronico="ana@example.com",
            contrasena_hash="hash-placeholder",
            rol=self.rol_enfermera,
            activo=True,
        )

    def _sesion(self, usuario):
        sesion = self.client.session
        sesion[SESION_ID_USUARIO] = usuario.id_usuario
        sesion[SESION_ID_ROL] = usuario.rol.id_rol
        sesion[SESION_ROL] = usuario.rol.nombre
        sesion[SESION_CORREO] = usuario.correo_electronico
        sesion[SESION_NOMBRE] = usuario.nombre
        sesion.save()

    def _crear_solicitud(self, estado=SolicitudAcceso.Estado.PENDIENTE, correo="maria@example.com"):
        return SolicitudAcceso.objects.create(
            nombre_completo="María López",
            correo_electronico=correo,
            telefono="5512345678",
            curp="LOPM800101MDFXXX01",
            rfc="LOPM800101XXX",
            matricula_institucional="MAT-001",
            cedula_profesional="CED-001",
            adscripcion_unidad="Unidad 1",
            categoria_puesto="Enfermera",
            rol=self.rol_enfermera,
            estado=estado,
        )

    def _url_aprobar(self, solicitud):
        return reverse("usuarios:confirmar_aprobacion", args=[solicitud.id_solicitud_acceso])

    def _url_rechazar(self, solicitud):
        return reverse("usuarios:confirmar_rechazo", args=[solicitud.id_solicitud_acceso])

    def test_pendiente_muestra_botones_aprobar_y_rechazar(self):
        solicitud = self._crear_solicitud()
        self._sesion(self.admin)
        respuesta = self.client.get(
            reverse("usuarios:detalle_solicitud", args=[solicitud.id_solicitud_acceso])
        )
        self.assertContains(respuesta, "Aprobar")
        self.assertContains(respuesta, "Rechazar")

    def test_solicitud_procesada_no_muestra_botones(self):
        solicitud = self._crear_solicitud(estado=SolicitudAcceso.Estado.APROBADA)
        self._sesion(self.admin)
        respuesta = self.client.get(
            reverse("usuarios:detalle_solicitud", args=[solicitud.id_solicitud_acceso])
        )
        self.assertContains(respuesta, "Esta solicitud ya fue procesada.")
        self.assertNotContains(respuesta, f'href="{self._url_aprobar(solicitud)}"')
        self.assertNotContains(respuesta, f'href="{self._url_rechazar(solicitud)}"')

    def test_aprobar_post_crea_usuario_y_aprueba(self):
        solicitud = self._crear_solicitud()
        self._sesion(self.admin)
        respuesta = self.client.post(self._url_aprobar(solicitud))
        self.assertEqual(respuesta.status_code, 302)

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.APROBADA)

        creados = Usuario.objects.filter(correo_electronico="maria@example.com")
        self.assertEqual(creados.count(), 1)
        usuario = creados.get()
        self.assertEqual(usuario.nombre, "María López")
        self.assertEqual(usuario.correo_electronico, "maria@example.com")
        self.assertEqual(usuario.rol, self.rol_enfermera)
        self.assertTrue(usuario.activo)
        self.assertEqual(usuario.contrasena_hash, CONTRASENA_HASH_GOOGLE)

    def test_rechazar_post_cambia_estado_y_no_crea_usuario(self):
        solicitud = self._crear_solicitud()
        self._sesion(self.admin)
        self.client.post(self._url_rechazar(solicitud))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.RECHAZADA)
        self.assertFalse(
            Usuario.objects.filter(correo_electronico="maria@example.com").exists()
        )

    def test_sin_sesion_no_puede_aprobar(self):
        solicitud = self._crear_solicitud()
        respuesta = self.client.post(self._url_aprobar(solicitud))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("usuarios:login"))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)

    def test_no_administrador_no_puede_aprobar(self):
        solicitud = self._crear_solicitud()
        self._sesion(self.enfermera)
        respuesta = self.client.post(self._url_aprobar(solicitud))
        self.assertEqual(respuesta.status_code, 403)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)

    def test_no_administrador_no_puede_rechazar(self):
        solicitud = self._crear_solicitud()
        self._sesion(self.enfermera)
        respuesta = self.client.post(self._url_rechazar(solicitud))
        self.assertEqual(respuesta.status_code, 403)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)

    def test_aprobada_no_se_puede_aprobar_nuevamente(self):
        solicitud = self._crear_solicitud(estado=SolicitudAcceso.Estado.APROBADA)
        self._sesion(self.admin)
        self.client.post(self._url_aprobar(solicitud))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.APROBADA)
        self.assertFalse(
            Usuario.objects.filter(correo_electronico="maria@example.com").exists()
        )

    def test_rechazada_no_se_puede_aprobar(self):
        solicitud = self._crear_solicitud(estado=SolicitudAcceso.Estado.RECHAZADA)
        self._sesion(self.admin)
        self.client.post(self._url_aprobar(solicitud))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.RECHAZADA)
        self.assertFalse(
            Usuario.objects.filter(correo_electronico="maria@example.com").exists()
        )

    def test_aprobada_no_se_puede_rechazar(self):
        solicitud = self._crear_solicitud(estado=SolicitudAcceso.Estado.APROBADA)
        self._sesion(self.admin)
        self.client.post(self._url_rechazar(solicitud))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.APROBADA)

    def test_rechazada_no_se_puede_rechazar_nuevamente(self):
        solicitud = self._crear_solicitud(estado=SolicitudAcceso.Estado.RECHAZADA)
        self._sesion(self.admin)
        self.client.post(self._url_rechazar(solicitud))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.RECHAZADA)

    def test_correo_ya_autorizado_impide_aprobacion_y_sigue_pendiente(self):
        self._crear_solicitud(correo="ana@example.com")
        solicitud = SolicitudAcceso.objects.get(correo_electronico="ana@example.com")
        self._sesion(self.admin)
        self.client.post(self._url_aprobar(solicitud), follow=True)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertEqual(
            Usuario.objects.filter(correo_electronico__iexact="ana@example.com").count(),
            1,
        )

    def test_cancelar_confirmacion_no_modifica_solicitud(self):
        solicitud = self._crear_solicitud()
        self._sesion(self.admin)
        respuesta = self.client.get(self._url_aprobar(solicitud))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cancelar")
        self.client.get(
            reverse("usuarios:detalle_solicitud", args=[solicitud.id_solicitud_acceso])
        )
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertFalse(
            Usuario.objects.filter(correo_electronico="maria@example.com").exists()
        )

    def test_aprobar_por_get_no_modifica_datos(self):
        solicitud = self._crear_solicitud()
        self._sesion(self.admin)
        self.client.get(self._url_aprobar(solicitud))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertFalse(
            Usuario.objects.filter(correo_electronico="maria@example.com").exists()
        )

    def test_rechazar_por_get_no_modifica_datos(self):
        solicitud = self._crear_solicitud()
        self._sesion(self.admin)
        self.client.get(self._url_rechazar(solicitud))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)

    def test_error_al_crear_usuario_hace_rollback_y_sigue_pendiente(self):
        solicitud = self._crear_solicitud()
        self._sesion(self.admin)
        with patch(
            "usuarios.views.Usuario.objects.create",
            side_effect=IntegrityError(),
        ):
            self.client.post(self._url_aprobar(solicitud))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertFalse(
            Usuario.objects.filter(correo_electronico="maria@example.com").exists()
        )
