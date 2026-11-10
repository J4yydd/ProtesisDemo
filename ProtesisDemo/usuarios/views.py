import hmac
import logging
import traceback

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from .email_service import (
    enviar_notificacion_aprobacion,
    enviar_notificacion_rechazo,
)
from .forms import SolicitudAccesoForm
from .models import SolicitudAcceso, Usuario

logger = logging.getLogger(__name__)

OAUTH_STATE_SESSION_KEY = "oauth_state"
OAUTH_CODE_VERIFIER_SESSION_KEY = "google_oauth_code_verifier"

SESION_ID_USUARIO = "id_usuario"
SESION_ID_ROL = "id_rol"
SESION_ROL = "rol"
SESION_CORREO = "correo_electronico"
SESION_NOMBRE = "nombre"
ROL_ADMINISTRADOR = "Administrador"
CONTRASENA_HASH_GOOGLE = "NO_USADA_GOOGLE_OAUTH"


def _google_flow(state=None, code_verifier=None):
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }
    kwargs = {
        "scopes": settings.GOOGLE_OAUTH_SCOPES,
        "state": state,
    }
    if code_verifier is not None:
        kwargs["code_verifier"] = code_verifier
    flow = Flow.from_client_config(client_config, **kwargs)
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    return flow


def _state_coincide(esperado, recibido):
    if not esperado or not recibido:
        return False
    return hmac.compare_digest(str(esperado), str(recibido))


def _limpiar_sesion_oauth(request):
    request.session.pop(OAUTH_STATE_SESSION_KEY, None)
    request.session.pop(OAUTH_CODE_VERIFIER_SESSION_KEY, None)


def _error_login(request, mensaje):
    _limpiar_sesion_oauth(request)
    messages.error(request, mensaje)
    return redirect("usuarios:login")


def _sesion_interna_valida(request):
    return bool(
        request.session.get(SESION_ID_USUARIO)
        and request.session.get(SESION_ID_ROL)
        and request.session.get(SESION_ROL)
        and request.session.get(SESION_CORREO)
    )


def _crear_sesion_interna(request, usuario):
    request.session[SESION_ID_USUARIO] = usuario.id_usuario
    request.session[SESION_ID_ROL] = usuario.rol.id_rol
    request.session[SESION_ROL] = usuario.rol.nombre
    request.session[SESION_CORREO] = usuario.correo_electronico
    request.session[SESION_NOMBRE] = usuario.nombre


def _redirigir_por_rol(request):
    rol = request.session.get(SESION_ROL)
    if rol == ROL_ADMINISTRADOR:
        return redirect("usuarios:administrar_usuarios")
    if rol in ["Enfermera", "Psicóloga"]:
        return redirect("pacientes:lista")
    return redirect("pacientes:lista")


def _autorizar_correo(request, correo):
    correo_normalizado = correo.strip()
    usuario = (
        Usuario.objects.select_related("rol")
        .filter(correo_electronico__iexact=correo_normalizado)
        .first()
    )
    if usuario is not None:
        if not usuario.activo:
            return _error_login(request, "Tu cuenta no se encuentra activa.")
        _crear_sesion_interna(request, usuario)
        return _redirigir_por_rol(request)

    solicitud = (
        SolicitudAcceso.objects.filter(correo_electronico__iexact=correo_normalizado)
        .order_by("-id_solicitud_acceso")
        .first()
    )
    if solicitud is None:
        return _error_login(
            request,
            "No existe una solicitud de acceso asociada a este correo.",
        )
    if solicitud.estado == SolicitudAcceso.Estado.PENDIENTE:
        return _error_login(
            request,
            "Tu solicitud de acceso aún se encuentra pendiente de revisión.",
        )
    if solicitud.estado == SolicitudAcceso.Estado.RECHAZADA:
        return _error_login(
            request,
            "Tu solicitud de acceso fue rechazada.",
        )
    return _error_login(
        request,
        "Tu acceso no está disponible actualmente. Contacta al administrador.",
    )


def login(request):
    if _sesion_interna_valida(request):
        return _redirigir_por_rol(request)
    return render(request, "usuarios/login.html")


def solicitar_acceso(request):
    if request.method == "POST":
        form = SolicitudAccesoForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.estado = SolicitudAcceso.Estado.PENDIENTE
            solicitud.save()
            return redirect("usuarios:solicitud_enviada")
    else:
        form = SolicitudAccesoForm()
    return render(request, "usuarios/solicitar_acceso.html", {"form": form})


def solicitud_enviada(request):
    return render(request, "usuarios/solicitud_enviada.html")


def _es_administrador(request):
    return request.session.get(SESION_ROL) == ROL_ADMINISTRADOR


def _respuesta_si_no_es_administrador(request):
    if not _sesion_interna_valida(request):
        return redirect("usuarios:login")
    if not _es_administrador(request):
        return render(request, "usuarios/acceso_denegado.html", status=403)
    return None


def _solicitudes_admin():
    return (
        SolicitudAcceso.objects.select_related("rol")
        .annotate(
            orden_estado=Case(
                When(estado=SolicitudAcceso.Estado.PENDIENTE, then=Value(0)),
                When(estado=SolicitudAcceso.Estado.APROBADA, then=Value(1)),
                When(estado=SolicitudAcceso.Estado.RECHAZADA, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        )
        .order_by("orden_estado", "-id_solicitud_acceso")
    )


def administrar_usuarios(request):
    denegado = _respuesta_si_no_es_administrador(request)
    if denegado:
        return denegado
    return render(
        request,
        "usuarios/administrar_usuarios.html",
        {"solicitudes": _solicitudes_admin()},
    )


def detalle_solicitud(request, id_solicitud_acceso):
    denegado = _respuesta_si_no_es_administrador(request)
    if denegado:
        return denegado
    solicitud = get_object_or_404(
        SolicitudAcceso.objects.select_related("rol"),
        pk=id_solicitud_acceso,
    )
    return render(
        request,
        "usuarios/detalle_solicitud.html",
        {"solicitud": solicitud, "solicitudes": _solicitudes_admin()},
    )


def _solicitud_admin_o_denegado(request, id_solicitud_acceso):
    denegado = _respuesta_si_no_es_administrador(request)
    if denegado:
        return denegado, None
    solicitud = get_object_or_404(
        SolicitudAcceso.objects.select_related("rol"),
        pk=id_solicitud_acceso,
    )
    return None, solicitud


def confirmar_aprobacion(request, id_solicitud_acceso):
    denegado, solicitud = _solicitud_admin_o_denegado(request, id_solicitud_acceso)
    if denegado:
        return denegado
    if request.method == "POST":
        return _procesar_aprobacion(request, id_solicitud_acceso)
    return render(
        request,
        "usuarios/confirmar_aprobacion.html",
        {"solicitud": solicitud, "solicitudes": _solicitudes_admin()},
    )


def confirmar_rechazo(request, id_solicitud_acceso):
    denegado, solicitud = _solicitud_admin_o_denegado(request, id_solicitud_acceso)
    if denegado:
        return denegado
    if request.method == "POST":
        return _procesar_rechazo(request, id_solicitud_acceso)
    return render(
        request,
        "usuarios/confirmar_rechazo.html",
        {"solicitud": solicitud, "solicitudes": _solicitudes_admin()},
    )


def _redirigir_detalle(id_solicitud_acceso):
    return redirect("usuarios:detalle_solicitud", id_solicitud_acceso=id_solicitud_acceso)


def _procesar_aprobacion(request, id_solicitud_acceso):
    try:
        with transaction.atomic():
            solicitud = (
                SolicitudAcceso.objects.select_related("rol")
                .select_for_update()
                .get(pk=id_solicitud_acceso)
            )
            if solicitud.estado != SolicitudAcceso.Estado.PENDIENTE:
                messages.error(request, "Esta solicitud ya fue procesada.")
                return _redirigir_detalle(id_solicitud_acceso)

            if Usuario.objects.filter(
                correo_electronico__iexact=solicitud.correo_electronico
            ).exists():
                messages.error(request, "El correo ya se encuentra autorizado.")
                return _redirigir_detalle(id_solicitud_acceso)

            Usuario.objects.create(
                nombre=solicitud.nombre_completo,
                correo_electronico=solicitud.correo_electronico,
                rol=solicitud.rol,
                activo=True,
                contrasena_hash=CONTRASENA_HASH_GOOGLE,
            )
            solicitud.estado = SolicitudAcceso.Estado.APROBADA
            solicitud.save(update_fields=["estado"])
    except SolicitudAcceso.DoesNotExist as exc:
        raise Http404("Solicitud no encontrada") from exc
    except IntegrityError:
        messages.error(
            request,
            "No fue posible autorizar el correo. Intenta de nuevo.",
        )
        return _redirigir_detalle(id_solicitud_acceso)

    _avisar_resultado_correo(
        request,
        enviado=enviar_notificacion_aprobacion(solicitud),
        exito="La solicitud fue aprobada correctamente.",
    )
    return _redirigir_detalle(id_solicitud_acceso)


def _procesar_rechazo(request, id_solicitud_acceso):
    try:
        with transaction.atomic():
            solicitud = (
                SolicitudAcceso.objects.select_for_update().get(pk=id_solicitud_acceso)
            )
            if solicitud.estado != SolicitudAcceso.Estado.PENDIENTE:
                messages.error(request, "Esta solicitud ya fue procesada.")
                return _redirigir_detalle(id_solicitud_acceso)
            solicitud.estado = SolicitudAcceso.Estado.RECHAZADA
            solicitud.save(update_fields=["estado"])
    except SolicitudAcceso.DoesNotExist as exc:
        raise Http404("Solicitud no encontrada") from exc

    _avisar_resultado_correo(
        request,
        enviado=enviar_notificacion_rechazo(solicitud),
        exito="La solicitud fue rechazada correctamente.",
    )
    return _redirigir_detalle(id_solicitud_acceso)


def _avisar_resultado_correo(request, enviado, exito):
    messages.success(request, exito)
    if enviado:
        messages.success(request, "El correo electrónico se envió correctamente.")
    else:
        messages.warning(
            request,
            "No fue posible enviar el correo electrónico.",
        )


def logout(request):
    request.session.flush()
    return redirect("usuarios:login")


def google_login(request):
    flow = _google_flow()
    authorization_url, state = flow.authorization_url(prompt="select_account")
    request.session[OAUTH_STATE_SESSION_KEY] = state
    request.session[OAUTH_CODE_VERIFIER_SESSION_KEY] = flow.code_verifier
    return redirect(authorization_url)


def google_callback(request):
    error_google = request.GET.get("error")
    if error_google == "access_denied":
        return _error_login(
            request,
            "El inicio de sesión fue cancelado. No se creó ninguna sesión.",
        )
    if error_google:
        return _error_login(
            request,
            "Google no pudo completar el inicio de sesión. Intenta de nuevo.",
        )

    state_sesion = request.session.get(OAUTH_STATE_SESSION_KEY)
    state_recibido = request.GET.get("state")
    if not _state_coincide(state_sesion, state_recibido):
        return _error_login(
            request,
            "La autenticación no es válida. Vuelve a iniciar sesión con Google.",
        )

    code_verifier = request.session.get(OAUTH_CODE_VERIFIER_SESSION_KEY)
    if not code_verifier:
        return _error_login(
            request,
            "La autenticación no es válida. Vuelve a iniciar sesión con Google.",
        )

    codigo = request.GET.get("code")
    if not codigo:
        return _error_login(
            request,
            "No se recibió la autorización de Google. Intenta de nuevo.",
        )

    try:
        flow = _google_flow(state=state_recibido, code_verifier=code_verifier)
        flow.fetch_token(code=codigo)
        credenciales = flow.credentials
        id_info = id_token.verify_oauth2_token(
            credenciales.id_token,
            google_requests.Request(),
            audience=settings.GOOGLE_CLIENT_ID,
        )
    except Exception as exc:
        logger.exception(
            "Error al verificar identidad de Google (%s): %s",
            type(exc).__name__,
            exc,
        )
        if settings.DEBUG:
            traceback.print_exc()
        return _error_login(
            request,
            "No se pudo verificar tu identidad con Google. Intenta de nuevo.",
        )

    correo = id_info.get("email")
    correo_verificado = id_info.get("email_verified")
    if not correo or correo_verificado is not True:
        return _error_login(
            request,
            "Tu correo de Google no está verificado. No se puede continuar.",
        )

    _limpiar_sesion_oauth(request)
    return _autorizar_correo(request, correo)
