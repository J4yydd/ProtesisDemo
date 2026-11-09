from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .email_service import (
    enviar_notificacion_aprobacion,
    enviar_notificacion_rechazo,
)
from .models import Rol, SolicitudAcceso, Usuario
from .views import (
    SESION_CORREO,
    SESION_ID_ROL,
    SESION_ID_USUARIO,
    SESION_NOMBRE,
    SESION_ROL,
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="protesis@example.com",
)
class NotificacionesSolicitudTests(TestCase):
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

    def _sesion_admin(self):
        sesion = self.client.session
        sesion[SESION_ID_USUARIO] = self.admin.id_usuario
        sesion[SESION_ID_ROL] = self.admin.rol.id_rol
        sesion[SESION_ROL] = self.admin.rol.nombre
        sesion[SESION_CORREO] = self.admin.correo_electronico
        sesion[SESION_NOMBRE] = self.admin.nombre
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

    def _cuerpo(self, mensaje):
        html = mensaje.alternatives[0][0] if mensaje.alternatives else ""
        return f"{mensaje.body}\n{html}"

    def test_aprobacion_exitosa_muestra_aviso_de_correo(self):
        solicitud = self._crear_solicitud()
        self._sesion_admin()
        respuesta = self.client.post(
            reverse("usuarios:confirmar_aprobacion", args=[solicitud.id_solicitud_acceso]),
            follow=True,
        )
        self.assertContains(respuesta, "La solicitud fue aprobada correctamente.")
        self.assertContains(respuesta, "El correo electrónico se envió correctamente.")

    def test_rechazo_exitoso_muestra_aviso_de_correo(self):
        solicitud = self._crear_solicitud()
        self._sesion_admin()
        respuesta = self.client.post(
            reverse("usuarios:confirmar_rechazo", args=[solicitud.id_solicitud_acceso]),
            follow=True,
        )
        self.assertContains(respuesta, "La solicitud fue rechazada correctamente.")
        self.assertContains(respuesta, "El correo electrónico se envió correctamente.")

    def test_fallo_email_muestra_aviso_de_correo_no_enviado(self):
        solicitud = self._crear_solicitud()
        self._sesion_admin()
        with patch(
            "usuarios.email_service.EmailMultiAlternatives.send",
            side_effect=OSError("fallo de correo"),
        ):
            respuesta = self.client.post(
                reverse(
                    "usuarios:confirmar_rechazo",
                    args=[solicitud.id_solicitud_acceso],
                ),
                follow=True,
            )
        self.assertContains(respuesta, "La solicitud fue rechazada correctamente.")
        self.assertContains(respuesta, "No fue posible enviar el correo electrónico.")
        self.assertNotContains(
            respuesta, "El correo electrónico se envió correctamente."
        )

    def test_aprobacion_exitosa_envia_correo_correcto(self):
        solicitud = self._crear_solicitud()
        self._sesion_admin()
        self.client.post(
            reverse("usuarios:confirmar_aprobacion", args=[solicitud.id_solicitud_acceso])
        )
        self.assertEqual(len(mail.outbox), 1)
        enviado = mail.outbox[0]
        self.assertEqual(enviado.to, ["maria@example.com"])
        self.assertEqual(enviado.subject, "Solicitud de acceso aprobada")
        cuerpo = self._cuerpo(enviado)
        self.assertIn("Enfermera", cuerpo)
        self.assertIn("Google", cuerpo)
        self.assertIn("maria@example.com", cuerpo)
        self.assertNotIn("LOPM800101MDFXXX01", cuerpo)
        self.assertNotIn("LOPM800101XXX", cuerpo)
        self.assertEqual(enviado.alternatives[0][1], "text/html")
        self.assertTrue(enviado.body.strip())

    def test_rechazo_exitoso_envia_correo_correcto(self):
        solicitud = self._crear_solicitud()
        self._sesion_admin()
        self.client.post(
            reverse("usuarios:confirmar_rechazo", args=[solicitud.id_solicitud_acceso])
        )
        self.assertEqual(len(mail.outbox), 1)
        enviado = mail.outbox[0]
        self.assertEqual(enviado.to, ["maria@example.com"])
        self.assertEqual(enviado.subject, "Resultado de tu solicitud de acceso")
        cuerpo = self._cuerpo(enviado)
        self.assertIn("rechazada", cuerpo.lower())
        self.assertNotIn("motivo", cuerpo.lower())
        self.assertNotIn("LOPM800101MDFXXX01", cuerpo)
        self.assertNotIn("LOPM800101XXX", cuerpo)

    def test_fallo_email_tras_aprobacion_no_revierte_negocio(self):
        solicitud = self._crear_solicitud()
        self._sesion_admin()
        with patch(
            "usuarios.email_service.EmailMultiAlternatives.send",
            side_effect=OSError("fallo de correo"),
        ):
            self.client.post(
                reverse(
                    "usuarios:confirmar_aprobacion",
                    args=[solicitud.id_solicitud_acceso],
                )
            )
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.APROBADA)
        self.assertTrue(
            Usuario.objects.filter(correo_electronico="maria@example.com").exists()
        )

    def test_fallo_email_tras_rechazo_conserva_rechazo_y_no_crea_usuario(self):
        solicitud = self._crear_solicitud()
        self._sesion_admin()
        with patch(
            "usuarios.email_service.EmailMultiAlternatives.send",
            side_effect=OSError("fallo de correo"),
        ):
            self.client.post(
                reverse(
                    "usuarios:confirmar_rechazo",
                    args=[solicitud.id_solicitud_acceso],
                )
            )
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.RECHAZADA)
        self.assertFalse(
            Usuario.objects.filter(correo_electronico="maria@example.com").exists()
        )

    def test_solicitud_ya_procesada_no_envia_correo(self):
        solicitud = self._crear_solicitud(estado=SolicitudAcceso.Estado.APROBADA)
        self._sesion_admin()
        self.client.post(
            reverse("usuarios:confirmar_aprobacion", args=[solicitud.id_solicitud_acceso])
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_correo_duplicado_no_envia_email(self):
        self._crear_solicitud(correo="admin@example.com")
        solicitud = SolicitudAcceso.objects.get(correo_electronico="admin@example.com")
        self._sesion_admin()
        self.client.post(
            reverse("usuarios:confirmar_aprobacion", args=[solicitud.id_solicitud_acceso])
        )
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertEqual(len(mail.outbox), 0)

    def test_plantillas_html_y_texto_se_generan(self):
        solicitud = self._crear_solicitud()
        self.assertTrue(enviar_notificacion_aprobacion(solicitud))
        self.assertTrue(enviar_notificacion_rechazo(solicitud))
        self.assertEqual(len(mail.outbox), 2)
        for enviado in mail.outbox:
            self.assertTrue(enviado.body.strip())
            self.assertEqual(len(enviado.alternatives), 1)
            self.assertEqual(enviado.alternatives[0][1], "text/html")
            self.assertTrue(enviado.alternatives[0][0].strip())
