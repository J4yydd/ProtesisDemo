import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

NOMBRE_SISTEMA = "SPMEP · Sistema de Prótesis Mamarias Externas Personalizadas"


def enviar_notificacion_aprobacion(solicitud):
    contexto = {
        "nombre": solicitud.nombre_completo,
        "correo": solicitud.correo_electronico,
        "rol": solicitud.rol.nombre,
        "sistema": NOMBRE_SISTEMA,
    }
    return _enviar(
        destinatario=solicitud.correo_electronico,
        asunto="Solicitud de acceso aprobada",
        plantilla_texto="usuarios/emails/solicitud_aprobada.txt",
        plantilla_html="usuarios/emails/solicitud_aprobada.html",
        contexto=contexto,
    )


def enviar_notificacion_rechazo(solicitud):
    contexto = {
        "nombre": solicitud.nombre_completo,
        "correo": solicitud.correo_electronico,
        "rol": solicitud.rol.nombre,
        "sistema": NOMBRE_SISTEMA,
    }
    return _enviar(
        destinatario=solicitud.correo_electronico,
        asunto="Resultado de tu solicitud de acceso",
        plantilla_texto="usuarios/emails/solicitud_rechazada.txt",
        plantilla_html="usuarios/emails/solicitud_rechazada.html",
        contexto=contexto,
    )


def _enviar(destinatario, asunto, plantilla_texto, plantilla_html, contexto):
    try:
        texto = render_to_string(plantilla_texto, contexto)
        html = render_to_string(plantilla_html, contexto)
        mensaje = EmailMultiAlternatives(
            subject=asunto,
            body=texto,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destinatario],
        )
        mensaje.attach_alternative(html, "text/html")
        mensaje.send()
        return True
    except Exception:
        logger.exception("Error al enviar notificación de solicitud de acceso")
        return False
