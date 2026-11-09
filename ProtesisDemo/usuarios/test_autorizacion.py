from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Rol, SolicitudAcceso, Usuario
from .test_oauth import CODE_VERIFIER_PRUEBA, GOOGLE_SETTINGS
from .views import (
    OAUTH_CODE_VERIFIER_SESSION_KEY,
    OAUTH_STATE_SESSION_KEY,
    SESION_CORREO,
    SESION_ID_ROL,
    SESION_ID_USUARIO,
    SESION_NOMBRE,
    SESION_ROL,
)


@override_settings(**GOOGLE_SETTINGS)
class AutorizacionInternaTests(TestCase):
    def setUp(self):
        self.rol = Rol.objects.get(nombre="Enfermera")

    def _guardar_sesion_oauth(self):
        sesion = self.client.session
        sesion[OAUTH_STATE_SESSION_KEY] = "state-valido"
        sesion[OAUTH_CODE_VERIFIER_SESSION_KEY] = CODE_VERIFIER_PRUEBA
        sesion.save()

    def _callback_google(self, correo, follow=True):
        self._guardar_sesion_oauth()
        flujo = MagicMock()
        flujo.credentials.id_token = "id-token-simulado"
        with (
            patch("usuarios.views.Flow.from_client_config", return_value=flujo),
            patch(
                "usuarios.views.id_token.verify_oauth2_token",
                return_value={"email": correo, "email_verified": True},
            ),
        ):
            return self.client.get(
                reverse("usuarios:google_callback"),
                {"state": "state-valido", "code": "codigo-autorizacion-valido"},
                follow=follow,
            )

    def _crear_usuario(self, correo="ana@example.com", activo=True):
        return Usuario.objects.create(
            nombre="Ana Pérez",
            correo_electronico=correo,
            contrasena_hash="hash-placeholder",
            rol=self.rol,
            activo=activo,
        )

    def _crear_solicitud(self, correo="maria@example.com", estado=None):
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
            rol=self.rol,
            estado=estado or SolicitudAcceso.Estado.PENDIENTE,
        )

    def _guardar_sesion_interna(self, usuario):
        sesion = self.client.session
        sesion[SESION_ID_USUARIO] = usuario.id_usuario
        sesion[SESION_ID_ROL] = usuario.rol.id_rol
        sesion[SESION_ROL] = usuario.rol.nombre
        sesion[SESION_CORREO] = usuario.correo_electronico
        sesion[SESION_NOMBRE] = usuario.nombre
        sesion.save()

    def test_usuario_activo_crea_sesion_interna(self):
        usuario = self._crear_usuario()
        self._callback_google("ANA@example.com")
        self.assertEqual(self.client.session.get(SESION_ID_USUARIO), usuario.id_usuario)
        self.assertEqual(self.client.session.get(SESION_ID_ROL), usuario.rol.id_rol)
        self.assertEqual(self.client.session.get(SESION_ROL), usuario.rol.nombre)
        self.assertEqual(
            self.client.session.get(SESION_CORREO),
            usuario.correo_electronico,
        )

    def test_usuario_activo_redirige_al_panel(self):
        self._crear_usuario()
        respuesta = self._callback_google("ana@example.com")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.resolver_match.url_name, "panel")
        self.assertContains(respuesta, "Ana Pérez")
        self.assertContains(respuesta, "ana@example.com")
        self.assertContains(respuesta, "Enfermera")

    def test_usuario_inactivo_no_entra(self):
        self._crear_usuario(activo=False)
        respuesta = self._callback_google("ana@example.com")
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertContains(respuesta, "Tu cuenta no se encuentra activa.")
        self.assertNotIn(SESION_ID_USUARIO, self.client.session)
        self.assertNotIn(SESION_ID_ROL, self.client.session)
        self.assertNotIn(SESION_ROL, self.client.session)

    def test_sin_usuario_solicitud_pendiente(self):
        self._crear_solicitud(estado=SolicitudAcceso.Estado.PENDIENTE)
        respuesta = self._callback_google("maria@example.com")
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertContains(
            respuesta,
            "Tu solicitud de acceso aún se encuentra pendiente de revisión.",
        )
        self.assertNotIn(SESION_ID_USUARIO, self.client.session)

    def test_sin_usuario_solicitud_rechazada(self):
        self._crear_solicitud(estado=SolicitudAcceso.Estado.RECHAZADA)
        respuesta = self._callback_google("maria@example.com")
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertContains(respuesta, "Tu solicitud de acceso fue rechazada.")
        self.assertNotIn(SESION_ID_USUARIO, self.client.session)

    def test_sin_usuario_ni_solicitud(self):
        respuesta = self._callback_google("nadie@example.com")
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertContains(
            respuesta,
            "No existe una solicitud de acceso asociada a este correo.",
        )
        self.assertNotIn(SESION_ID_USUARIO, self.client.session)

    def test_varias_solicitudes_usa_mayor_id(self):
        self._crear_solicitud(estado=SolicitudAcceso.Estado.PENDIENTE)
        self._crear_solicitud(estado=SolicitudAcceso.Estado.RECHAZADA)
        respuesta = self._callback_google("maria@example.com")
        self.assertContains(respuesta, "Tu solicitud de acceso fue rechazada.")
        self.assertNotContains(
            respuesta,
            "Tu solicitud de acceso aún se encuentra pendiente de revisión.",
        )
        self.assertNotIn(SESION_ID_USUARIO, self.client.session)

    def test_solicitud_aprobada_sin_usuario_no_autoriza(self):
        self._crear_solicitud(estado=SolicitudAcceso.Estado.APROBADA)
        respuesta = self._callback_google("maria@example.com")
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertContains(
            respuesta,
            "Tu acceso no está disponible actualmente. Contacta al administrador.",
        )
        self.assertNotIn(SESION_ID_USUARIO, self.client.session)

    def test_panel_sin_sesion_redirige_a_login(self):
        respuesta = self.client.get(reverse("usuarios:panel"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("usuarios:login"))

    def test_panel_con_sesion_valida_responde(self):
        usuario = self._crear_usuario()
        self._guardar_sesion_interna(usuario)
        respuesta = self.client.get(reverse("usuarios:panel"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, usuario.nombre)
        self.assertContains(respuesta, usuario.correo_electronico)
        self.assertContains(respuesta, usuario.rol.nombre)

    def test_logout_limpia_la_sesion(self):
        usuario = self._crear_usuario()
        self._guardar_sesion_interna(usuario)
        respuesta = self.client.get(reverse("usuarios:logout"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("usuarios:login"))
        self.assertNotIn(SESION_ID_USUARIO, self.client.session)
        self.assertNotIn(SESION_ID_ROL, self.client.session)
        self.assertNotIn(SESION_ROL, self.client.session)
        self.assertNotIn(SESION_CORREO, self.client.session)

    def test_login_con_sesion_interna_redirige_al_panel(self):
        usuario = self._crear_usuario()
        self._guardar_sesion_interna(usuario)
        respuesta = self.client.get(reverse("usuarios:login"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("usuarios:panel"))
