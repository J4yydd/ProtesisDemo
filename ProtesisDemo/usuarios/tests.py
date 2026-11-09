from django.db import IntegrityError
from django.db.models import ForeignKey
from django.test import TestCase

from .models import Rol, SolicitudAcceso, Usuario


class RolTests(TestCase):
    def test_se_puede_crear_un_rol(self):
        rol = Rol.objects.create(nombre="Operador")
        self.assertEqual(rol.nombre, "Operador")
        self.assertIsNotNone(rol.id_rol)


class UsuarioTests(TestCase):
    def setUp(self):
        self.rol = Rol.objects.create(nombre="Administrador")

    def test_se_puede_crear_un_usuario_asociado_a_un_rol(self):
        usuario = Usuario.objects.create(
            nombre="Ana Pérez",
            correo_electronico="ana@example.com",
            contrasena_hash="hash-placeholder",
            rol=self.rol,
            activo=True,
        )
        self.assertEqual(usuario.rol, self.rol)
        self.assertEqual(usuario.rol.id_rol, self.rol.id_rol)

    def test_no_se_pueden_crear_dos_usuarios_con_el_mismo_correo(self):
        Usuario.objects.create(
            nombre="Ana Pérez",
            correo_electronico="ana@example.com",
            contrasena_hash="hash-placeholder",
            rol=self.rol,
            activo=True,
        )
        with self.assertRaises(IntegrityError):
            Usuario.objects.create(
                nombre="Ana Otra",
                correo_electronico="ana@example.com",
                contrasena_hash="hash-placeholder",
                rol=self.rol,
                activo=False,
            )


class SolicitudAccesoTests(TestCase):
    def setUp(self):
        self.rol = Rol.objects.create(nombre="Enfermera")

    def _datos_solicitud(self, **extra):
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
            "rol": self.rol,
        }
        datos.update(extra)
        return datos

    def test_se_puede_crear_una_solicitud_acceso(self):
        solicitud = SolicitudAcceso.objects.create(**self._datos_solicitud())
        self.assertIsNotNone(solicitud.id_solicitud_acceso)

    def test_solicitud_nueva_inicia_como_pendiente(self):
        solicitud = SolicitudAcceso.objects.create(**self._datos_solicitud())
        self.assertEqual(solicitud.estado, SolicitudAcceso.Estado.PENDIENTE)
        self.assertEqual(solicitud.estado, "Pendiente")

    def test_solicitud_puede_apuntar_a_un_rol(self):
        solicitud = SolicitudAcceso.objects.create(**self._datos_solicitud())
        self.assertEqual(solicitud.rol, self.rol)
        self.assertEqual(solicitud.rol.id_rol, self.rol.id_rol)

    def test_estado_invalido_es_rechazado_por_la_base_de_datos(self):
        with self.assertRaises(IntegrityError):
            SolicitudAcceso.objects.create(
                **self._datos_solicitud(estado="Cancelada")
            )

    def test_no_existe_relacion_directa_con_usuario(self):
        solicitud = SolicitudAcceso.objects.create(**self._datos_solicitud())
        self.assertTrue(
            SolicitudAcceso.objects.filter(
                pk=solicitud.pk
            ).exists()
        )
        fks = [
            field
            for field in SolicitudAcceso._meta.get_fields()
            if isinstance(field, ForeignKey)
        ]
        modelos_relacionados = {fk.related_model for fk in fks}
        self.assertIn(Rol, modelos_relacionados)
        self.assertNotIn(Usuario, modelos_relacionados)
