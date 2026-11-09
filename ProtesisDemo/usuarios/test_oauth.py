from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from django.urls import reverse

from .views import OAUTH_CODE_VERIFIER_SESSION_KEY, OAUTH_STATE_SESSION_KEY

GOOGLE_SETTINGS = {
    "GOOGLE_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
    "GOOGLE_CLIENT_SECRET": "test-client-secret",
    "GOOGLE_REDIRECT_URI": "http://localhost:8000/auth/google/callback/",
    "GOOGLE_OAUTH_SCOPES": [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
}

CODE_VERIFIER_PRUEBA = "code-verifier-de-prueba"


@override_settings(**GOOGLE_SETTINGS)
class LoginOAuthTests(TestCase):
    def _guardar_sesion_oauth(self, state="state-valido", code_verifier=CODE_VERIFIER_PRUEBA):
        sesion = self.client.session
        sesion[OAUTH_STATE_SESSION_KEY] = state
        if code_verifier is not None:
            sesion[OAUTH_CODE_VERIFIER_SESSION_KEY] = code_verifier
        sesion.save()

    def test_login_responde_correctamente(self):
        respuesta = self.client.get(reverse("usuarios:login"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Iniciar sesión con Google")

    def test_iniciar_oauth_redirige_hacia_google(self):
        respuesta = self.client.get(reverse("usuarios:google_login"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("accounts.google.com", respuesta["Location"])

    def test_iniciar_oauth_guarda_state_en_sesion(self):
        respuesta = self.client.get(reverse("usuarios:google_login"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self.client.session.get(OAUTH_STATE_SESSION_KEY))

    def test_iniciar_oauth_usa_scopes_canonicos(self):
        respuesta = self.client.get(reverse("usuarios:google_login"))
        self.assertEqual(respuesta.status_code, 302)
        scopes = parse_qs(urlparse(respuesta["Location"]).query).get("scope", [""])[0].split()
        self.assertEqual(
            set(scopes),
            {
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            },
        )

    def test_iniciar_oauth_guarda_code_verifier_en_sesion(self):
        respuesta = self.client.get(reverse("usuarios:google_login"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self.client.session.get(OAUTH_CODE_VERIFIER_SESSION_KEY))

    def test_callback_sin_state_valido_es_rechazado(self):
        respuesta = self.client.get(
            reverse("usuarios:google_callback"),
            {"code": "codigo-falso"},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertNotIn("id_usuario", self.client.session)
        self.assertNotIn("id_rol", self.client.session)

    def test_callback_sin_code_verifier_es_rechazado(self):
        self._guardar_sesion_oauth(code_verifier=None)

        with patch("usuarios.views.Flow.from_client_config") as mock_flow:
            respuesta = self.client.get(
                reverse("usuarios:google_callback"),
                {"state": "state-valido", "code": "codigo-autorizacion-valido"},
                follow=True,
            )

        mock_flow.assert_not_called()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertNotIn("id_usuario", self.client.session)
        self.assertNotIn("id_rol", self.client.session)
        self.assertNotIn("rol", self.client.session)

    def test_callback_reconstruye_flow_con_el_mismo_code_verifier(self):
        self._guardar_sesion_oauth()
        flujo = MagicMock()
        flujo.credentials.id_token = "id-token-simulado"

        with (
            patch("usuarios.views.Flow.from_client_config", return_value=flujo) as mock_flow,
            patch(
                "usuarios.views.id_token.verify_oauth2_token",
                return_value={"email": "persona@example.com", "email_verified": True},
            ),
        ):
            self.client.get(
                reverse("usuarios:google_callback"),
                {"state": "state-valido", "code": "codigo-autorizacion-valido"},
            )

        mock_flow.assert_called_once()
        self.assertEqual(
            mock_flow.call_args.kwargs["code_verifier"],
            CODE_VERIFIER_PRUEBA,
        )

    def test_callback_con_error_google_no_crea_autorizacion_interna(self):
        self._guardar_sesion_oauth(state="state-de-prueba")

        with patch("usuarios.views.Flow.from_client_config") as mock_flow:
            respuesta = self.client.get(
                reverse("usuarios:google_callback"),
                {"state": "state-de-prueba", "error": "access_denied"},
                follow=True,
            )

        mock_flow.assert_not_called()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertNotIn("id_usuario", self.client.session)
        self.assertNotIn("id_rol", self.client.session)
        self.assertNotIn(OAUTH_STATE_SESSION_KEY, self.client.session)
        self.assertNotIn(OAUTH_CODE_VERIFIER_SESSION_KEY, self.client.session)

    def test_callback_exitoso_muestra_correo_sin_autorizacion_interna(self):
        self._guardar_sesion_oauth()

        flujo = MagicMock()
        flujo.credentials.id_token = "id-token-simulado"
        payload = {
            "email": "persona@example.com",
            "email_verified": True,
        }

        with (
            patch("usuarios.views.Flow.from_client_config", return_value=flujo),
            patch(
                "usuarios.views.id_token.verify_oauth2_token",
                return_value=payload,
            ) as mock_verify,
        ):
            respuesta = self.client.get(
                reverse("usuarios:google_callback"),
                {"state": "state-valido", "code": "codigo-autorizacion-valido"},
                follow=True,
            )

        flujo.fetch_token.assert_called_once_with(code="codigo-autorizacion-valido")
        mock_verify.assert_called_once()
        self.assertEqual(
            mock_verify.call_args.kwargs["audience"],
            GOOGLE_SETTINGS["GOOGLE_CLIENT_ID"],
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertTemplateNotUsed(respuesta, "usuarios/oauth_ok.html")
        self.assertContains(
            respuesta,
            "No existe una solicitud de acceso asociada a este correo.",
        )
        self.assertNotIn("id_usuario", self.client.session)
        self.assertNotIn("id_rol", self.client.session)
        self.assertNotIn("rol", self.client.session)
        self.assertNotIn(OAUTH_STATE_SESSION_KEY, self.client.session)
        self.assertNotIn(OAUTH_CODE_VERIFIER_SESSION_KEY, self.client.session)

    def test_callback_correo_no_verificado_es_rechazado(self):
        self._guardar_sesion_oauth()

        flujo = MagicMock()
        flujo.credentials.id_token = "id-token-simulado"
        payload = {
            "email": "no-verificado@example.com",
            "email_verified": False,
        }

        with (
            patch("usuarios.views.Flow.from_client_config", return_value=flujo),
            patch(
                "usuarios.views.id_token.verify_oauth2_token",
                return_value=payload,
            ),
        ):
            respuesta = self.client.get(
                reverse("usuarios:google_callback"),
                {"state": "state-valido", "code": "codigo-autorizacion-valido"},
                follow=True,
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.resolver_match.url_name, "login")
        self.assertTemplateNotUsed(respuesta, "usuarios/oauth_ok.html")
        self.assertNotContains(respuesta, "Autenticación con Google correcta")
        self.assertContains(respuesta, "Tu correo de Google no está verificado")
        self.assertEqual(respuesta.request["PATH_INFO"], "/login/")
        self.assertNotIn("id_usuario", self.client.session)
        self.assertNotIn("id_rol", self.client.session)
        self.assertNotIn("rol", self.client.session)
        self.assertNotIn(OAUTH_STATE_SESSION_KEY, self.client.session)
        self.assertNotIn(OAUTH_CODE_VERIFIER_SESSION_KEY, self.client.session)
