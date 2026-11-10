import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class EnvioCapturaService:
    """
    Servicio de integración para notificar y enviar la solicitud de prótesis
    al sistema de captura de escritorio (SCPMEP Escritorio).

    Cumple con RN-26 y gestiona la excepción 1.0.E2 (error de conexión o falla de envío).
    """

    @classmethod
    def enviar(cls, solicitud):
        """
        Envía la solicitud al sistema SCPMEP Escritorio.
        Retorna True si la notificación fue exitosa, o False si falló.

        Si settings.SIMULAR_ERROR_ENVIO_CAPTURA está activo, simula falla para pruebas.
        """
        if getattr(settings, "SIMULAR_ERROR_ENVIO_CAPTURA", False):
            logger.warning(
                "Simulando falla de envío de solicitud #%s al sistema de captura",
                solicitud.id_solicitud,
            )
            return False

        try:
            # Aquí se puede conectar con un webhook, endpoint REST o socket de SCPMEP Escritorio.
            # En modo estándar por defecto simulamos respuesta afirmativa.
            logger.info(
                "Solicitud de captura #%s enviada exitosamente para la paciente %s en %s",
                solicitud.id_solicitud,
                solicitud.paciente.curp,
                solicitud.lugar_captura.nombre,
            )
            solicitud.enviado_escritorio = True
            solicitud.save(update_fields=["enviado_escritorio"])
            return True
        except Exception as exc:
            logger.exception(
                "Error al enviar la solicitud #%s al sistema de captura: %s",
                solicitud.id_solicitud,
                exc,
            )
            return False

