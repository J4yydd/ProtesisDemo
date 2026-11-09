# SPMEP · ProtesisDemo

Sistema de Prótesis Mamarias Externas Personalizadas.

Este repositorio es la base Django del proyecto. Hoy el módulo de **usuarios** ya cubre:

- solicitud pública de acceso;
- inicio de sesión con Google;
- autorización interna (solo correos dados de alta);
- panel según rol;
- administración de solicitudes (aprobar / rechazar);
- correo de notificación al solicitante.

Python recomendado: **3.12** o **3.13** (Django 5.2).

## Estructura

```
ProtesisDemo/                 ← raíz del repositorio (aquí está este README)
  .env.example
  README.md
  ProtesisDemo/               ← proyecto Django (aquí está manage.py)
    manage.py
    requirements.txt
    db.sqlite3                ← se crea al migrar; no se sube
    .env                      ← secretos locales; no se sube
    usuarios/                 ← app de autenticación y solicitudes
    templates/
    static/
```

Todos los comandos `manage.py` se ejecutan **dentro de la carpeta Django**, no en la raíz del repo.

## Cómo levantarlo en local

### 1. Clonar

```bash
git clone <url-del-repositorio>
cd ProtesisDemo
cd ProtesisDemo
```

### 2. Entorno virtual

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows**

```bat
python -m venv .venv
.venv\Scripts\activate
```

### 3. Dependencias

```bash
pip install -r requirements.txt
```

### 4. Variables de entorno

Copia el ejemplo desde la raíz del repositorio hacia la carpeta de `manage.py`:

```bash
cp ../.env.example .env
```

**Windows**

```bat
copy ..\.env.example .env
```

Edita `.env` y pon al menos un `SECRET_KEY` propio.

```
SECRET_KEY=cambia-esta-clave-en-local
DEBUG=True
DATABASE_URL=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback/
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=protesis@example.com
```

Si `DATABASE_URL` queda vacío, Django usa SQLite (`db.sqlite3`). No hace falta PostgreSQL para desarrollar.

`.env` no se versiona. Nunca subas Client Secret, App Passwords ni la base local.

### 5. Migraciones y servidor

```bash
python manage.py migrate
python manage.py runserver localhost:8000
```

Abre:

- [http://localhost:8000/](http://localhost:8000/) — página de comprobación
- [http://localhost:8000/login/](http://localhost:8000/login/) — inicio de sesión
- [http://localhost:8000/solicitar-acceso/](http://localhost:8000/solicitar-acceso/) — formulario público

Para Google OAuth el servidor **tiene que** escucharse en `localhost:8000` (no uses otro puerto ni `127.0.0.1` si la URI de Google está registrada con `localhost`).

## Google OAuth (obligatorio para entrar)

El login no usa usuario/contraseña de Django. Autentica con Google y después autoriza contra la tabla `Usuario`.

1. En [Google Cloud Console](https://console.cloud.google.com/) crea (o usa) un proyecto.
2. APIs y servicios → Credenciales → **ID de cliente de OAuth** tipo **Aplicación web**.
3. Orígenes JavaScript autorizados:
   - `http://localhost:8000`
4. URI de redirección autorizada (tiene que coincidir con `.env`):
   - `http://localhost:8000/auth/google/callback/`
5. Copia el Client ID y el Client Secret a `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`.

El correo de Google debe estar **verificado**. Scopes usados: `openid`, correo y perfil.

## Primer administrador

Google solo deja entrar si ya existe un `Usuario` activo con ese correo.

Después de `migrate`, crea el administrador con el **mismo Gmail** que vas a usar para entrar:

```bash
python manage.py shell
```

```python
from usuarios.models import Rol, Usuario
from usuarios.views import CONTRASENA_HASH_GOOGLE

rol = Rol.objects.get(nombre="Administrador")
Usuario.objects.create(
    nombre="Admin local",
    correo_electronico="tu.correo@gmail.com",
    contrasena_hash=CONTRASENA_HASH_GOOGLE,
    rol=rol,
    activo=True,
)
```

Luego ve a `/login/`, entra con Google y deberías llegar al panel. Si el rol es Administrador verás **Administrar usuarios**.

Opcional: `python manage.py createsuperuser` solo sirve para `/admin/` de Django (inspección de datos). Esa cuenta **no** es la sesión del SPMEP.

## Cómo usar el sistema

### Roles

Tras migrar existen: Operador, Administrador, Doctor, Enfermera, Psicóloga, Modelador, Investigador.

El formulario público solo permite pedir **Enfermera** o **Psicóloga**.

El resto de roles se dan de alta por un administrador (o por shell / admin de Django), no por el formulario público.

### Flujo de un solicitante

1. Abre `/solicitar-acceso/` (también hay enlace en el login).
2. Llena el formulario con el **mismo correo de Google** con el que va a entrar después.
3. La solicitud nace en estado **Pendiente**.
4. Hasta que un administrador la apruebe, el login con Google muestra que la solicitud sigue pendiente.
5. Si se rechaza, el login informa el rechazo. Puede volver a solicitar con el mismo correo.
6. Si se aprueba, ya puede entrar y llega al panel con su rol.

No se puede crear otra solicitud Pendiente con el mismo correo, ni solicitar si ese correo ya está autorizado como `Usuario`.

### Flujo del administrador

1. Entra con Google (usuario Administrador activo).
2. Panel → **Administrar usuarios**.
3. Elige una solicitud en la lista.
4. **Aprobar solicitud** o **Rechazar solicitud** (hay confirmación).
5. Al aprobar se crea el `Usuario` y la solicitud pasa a **Aprobada**.
6. Al rechazar solo cambia el estado; no se crea usuario.
7. Después del commit se intenta enviar el correo al solicitante. En pantalla verás:
   - que la solicitud se procesó;
   - que el correo se envió, o que no se pudo enviar.
8. Si el correo falla, **la aprobación o el rechazo no se deshacen**.

### Sesión y permisos

- La sesión interna guarda `id_usuario`, rol, correo y nombre. No usa `AUTH_USER_MODEL` del SPMEP.
- Sin sesión, panel y administración redirigen a login.
- Un rol que no sea Administrador recibe **Acceso denegado** (403) en administrar solicitudes.
- `activo=False` impide el login aunque el correo exista.
- **Cerrar sesión** limpia la sesión y vuelve al login.

## Correos

Por defecto `EMAIL_BACKEND` es consola: el mensaje se imprime en la terminal del `runserver`. Sirve para desarrollar sin Gmail.

Para Gmail SMTP, en `.env`:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu.cuenta@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=tu.cuenta@gmail.com
```

La cuenta necesita 2FA. `EMAIL_HOST_PASSWORD` es una **contraseña de aplicación**, no la contraseña de Gmail.

Asuntos:

- aprobación: `Solicitud de acceso aprobada`
- rechazo: `Resultado de tu solicitud de acceso`

## Rutas útiles

| Ruta | Quién | Qué hace |
| --- | --- | --- |
| `/login/` | público | Google Login y enlace a solicitar acceso |
| `/solicitar-acceso/` | público | formulario de solicitud |
| `/panel/` | usuario con sesión | datos de sesión y, si es admin, enlace a solicitudes |
| `/logout/` | usuario con sesión | cierra sesión |
| `/administrar-usuarios/` | Administrador | listado y detalle de solicitudes |
| `/admin/` | superuser Django | inspección de Rol, Usuario, SolicitudAcceso |

## Tests

Desde la carpeta de `manage.py`, con el venv activo:

```bash
python manage.py test usuarios
```

Cubre modelos, OAuth (con mocks), autorización, listado admin, aprobar/rechazar, correos y el formulario público. No necesitas Google ni SMTP reales para la suite.

## Colaborar

- Trabaja sobre la rama acordada. No subas `.env`, `.venv/` ni `db.sqlite3`.
- No pongas secretos de Google ni de Gmail en el código ni en el README.
- Los cambios de interfaz van en `templates/` y `static/css/base.css`.
- La lógica de usuarios está en `usuarios/` (`views.py`, `forms.py`, `models.py`, `email_service.py`).
- PostgreSQL se podrá activar más adelante con `DATABASE_URL`. En local el valor por defecto es SQLite.
- Si OAuth falla con `redirect_uri_mismatch`, revisa que el servidor sea `localhost:8000` y que la URI en Google Cloud sea exactamente la de `.env`.
- Si el login dice que no hay solicitud, el Gmail no coincide con ningún `Usuario` ni `SolicitudAcceso`.
)
