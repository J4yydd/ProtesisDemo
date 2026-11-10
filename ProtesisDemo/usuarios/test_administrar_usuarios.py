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


class AdministrarUsuariosTests(TestCase):
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

    def _crear_solicitud(self, estado, nombre="María López", correo="maria@example.com"):
        return SolicitudAcceso.objects.create(
            nombre_completo=nombre,
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

    def test_administrador_accede_al_listado(self):
        self._sesion(self.admin)
        respuesta = self.client.get(reverse("usuarios:administrar_usuarios"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Administrar usuarios")

    def test_sin_sesion_no_accede_al_listado(self):
        respuesta = self.client.get(reverse("usuarios:administrar_usuarios"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("usuarios:login"))

    def test_otro_rol_no_accede_al_listado(self):
        self._sesion(self.enfermera)
        respuesta = self.client.get(reverse("usuarios:administrar_usuarios"))
        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, "Acceso denegado", status_code=403)

    def test_listado_muestra_solicitudes_y_estado(self):
        pendiente = self._crear_solicitud(SolicitudAcceso.Estado.PENDIENTE)
        self._sesion(self.admin)
        respuesta = self.client.get(reverse("usuarios:administrar_usuarios"))
        self.assertContains(respuesta, pendiente.nombre_completo)
        self.assertContains(respuesta, pendiente.correo_electronico)
        self.assertContains(respuesta, "Pendiente")
        self.assertContains(respuesta, str(pendiente.id_solicitud_acceso))

    def test_administrador_abre_detalle_con_datos(self):
        solicitud = self._crear_solicitud(SolicitudAcceso.Estado.PENDIENTE)
        self._sesion(self.admin)
        respuesta = self.client.get(
            reverse("usuarios:detalle_solicitud", args=[solicitud.id_solicitud_acceso])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, solicitud.nombre_completo)
        self.assertContains(respuesta, solicitud.correo_electronico)
        self.assertContains(respuesta, solicitud.telefono)
        self.assertContains(respuesta, solicitud.curp)
        self.assertContains(respuesta, solicitud.rfc)
        self.assertContains(respuesta, solicitud.matricula_institucional)
        self.assertContains(respuesta, solicitud.cedula_profesional)
        self.assertContains(respuesta, solicitud.adscripcion_unidad)
        self.assertContains(respuesta, solicitud.categoria_puesto)
        self.assertContains(respuesta, "Enfermera")

    def test_solicitud_inexistente_devuelve_404(self):
        self._sesion(self.admin)
        respuesta = self.client.get(
            reverse("usuarios:detalle_solicitud", args=[999999])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_solicitud_aprobada_se_muestra_como_procesada(self):
        solicitud = self._crear_solicitud(SolicitudAcceso.Estado.APROBADA)
        self._sesion(self.admin)
        respuesta = self.client.get(
            reverse("usuarios:detalle_solicitud", args=[solicitud.id_solicitud_acceso])
        )
        self.assertContains(respuesta, "Esta solicitud ya fue procesada.")
        self.assertContains(respuesta, "Aprobada")
        self.assertNotContains(respuesta, "pendiente de revisión")

    def test_solicitud_rechazada_se_muestra_como_procesada(self):
        solicitud = self._crear_solicitud(SolicitudAcceso.Estado.RECHAZADA)
        self._sesion(self.admin)
        respuesta = self.client.get(
            reverse("usuarios:detalle_solicitud", args=[solicitud.id_solicitud_acceso])
        )
        self.assertContains(respuesta, "Esta solicitud ya fue procesada.")
        self.assertContains(respuesta, "Rechazada")

    def test_solicitud_pendiente_se_muestra_como_pendiente(self):
        solicitud = self._crear_solicitud(SolicitudAcceso.Estado.PENDIENTE)
        self._sesion(self.admin)
        respuesta = self.client.get(
            reverse("usuarios:detalle_solicitud", args=[solicitud.id_solicitud_acceso])
        )
        self.assertContains(respuesta, "Esta solicitud está pendiente de revisión.")
        self.assertNotContains(respuesta, "ya fue procesada")

    def test_administrador_tiene_acceso_a_administrar_usuarios(self):
        self._sesion(self.admin)
        respuesta = self.client.get(reverse("usuarios:administrar_usuarios"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Administrar usuarios")

    def test_otro_rol_no_tiene_acceso_a_administrar_usuarios(self):
        self._sesion(self.enfermera)
        respuesta = self.client.get(reverse("usuarios:administrar_usuarios"))
        self.assertEqual(respuesta.status_code, 403)
