import logging
from functools import wraps

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import View

from usuarios.models import Usuario
from usuarios.views import (
    SESION_CORREO,
    SESION_ID_ROL,
    SESION_ID_USUARIO,
    SESION_NOMBRE,
    SESION_ROL,
    _sesion_interna_valida,
)

from .forms import (
    ExpedienteForm,
    MedicionForm,
    PacienteForm,
    SolicitudProtesisForm,
)
from .models import (
    Expediente,
    LugarCaptura,
    MedicionAntropometrica,
    Paciente,
    SolicitudProtesis,
)
from .services import EnvioCapturaService

logger = logging.getLogger(__name__)

ROLES_SALUD = ["Enfermera", "Psicóloga"]


def _usuario_en_sesion(request):
    id_usuario = request.session.get(SESION_ID_USUARIO)
    if id_usuario:
        return Usuario.objects.filter(pk=id_usuario).first()
    return None


def _es_rol_salud(request):
    rol = request.session.get(SESION_ROL)
    return rol in ROLES_SALUD


def requiere_rol_salud(view_func):
    """
    Decorador que restringe el acceso únicamente a usuarias con rol
    Enfermera o Psicóloga y sesión interna activa.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not _sesion_interna_valida(request):
            return redirect("usuarios:login")
        if not _es_rol_salud(request):
            return render(request, "usuarios/acceso_denegado.html", status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped


class RolSaludRequiredMixin:
    """Mixin para vistas basadas en clases que requieren rol de salud."""

    def dispatch(self, request, *args, **kwargs):
        if not _sesion_interna_valida(request):
            return redirect("usuarios:login")
        if not _es_rol_salud(request):
            return render(request, "usuarios/acceso_denegado.html", status=403)
        return super().dispatch(request, *args, **kwargs)


class PacienteListView(RolSaludRequiredMixin, View):
    """
    Listado y búsqueda en tiempo real de pacientes.
    Permite filtrar por nombre o CURP.
    """

    def get(self, request):
        q = request.GET.get("q", "").strip()
        pacientes = Paciente.objects.prefetch_related("solicitudes").select_related("expediente")
        if q:
            pacientes = pacientes.filter(
                models_q := (
                    django_q(nombre_completo__icontains=q) | django_q(curp__icontains=q)
                )
            )

        total_pacientes = Paciente.objects.count()
        return render(
            request,
            "pacientes/paciente_list.html",
            {
                "pacientes": pacientes,
                "q": q,
                "total_pacientes": total_pacientes,
                "rol_usuario": request.session.get(SESION_ROL),
                "nombre_usuario": request.session.get(SESION_NOMBRE),
            },
        )


def django_q(**kwargs):
    from django.db.models import Q
    return Q(**kwargs)


class PacienteCreateView(RolSaludRequiredMixin, View):
    """
    CU-W01: Registrar paciente.
    Valida CURP única, mayoría de edad, campos obligatorios y opcionales.
    """

    def get(self, request):
        form = PacienteForm()
        return render(
            request,
            "pacientes/paciente_form.html",
            {"form": form, "modo": "crear"},
        )

    def post(self, request):
        form = PacienteForm(request.POST)
        if form.is_valid():
            try:
                paciente = form.save()
                messages.success(request, f"Paciente {paciente.nombre_completo} registrado exitosamente.")
                return redirect("pacientes:detalle", curp=paciente.curp)
            except DatabaseError as exc:
                logger.exception("Error de base de datos al guardar paciente: %s", exc)
                messages.error(request, "Ocurrió un error al guardar el registro en la base de datos. Intente nuevamente.")
        else:
            curp_ingresada = request.POST.get("curp", "").strip().upper()
            if curp_ingresada and Paciente.objects.filter(curp=curp_ingresada).exists():
                paciente_existente = Paciente.objects.get(curp=curp_ingresada)
                messages.warning(
                    request,
                    f"Ya existe un paciente con la CURP {curp_ingresada}: {paciente_existente.nombre_completo}.",
                )

        return render(
            request,
            "pacientes/paciente_form.html",
            {"form": form, "modo": "crear"},
        )


class PacienteDetailView(RolSaludRequiredMixin, View):
    """
    Vista integral del Paciente y su Expediente Clínico (si existe).
    Muestra antecedentes oncológicos, mediciones antropométricas con estado de vigencia,
    consentimientos y solicitudes de prótesis con sus estados.
    """

    def get(self, request, curp):
        paciente = get_object_or_404(
            Paciente.objects.prefetch_related(
                "solicitudes__lugar_captura",
                "solicitudes__medicion",
            ),
            curp=curp.upper(),
        )
        expediente = getattr(paciente, "expediente", None)
        mediciones = []
        medicion_vigente = None
        solicitud_activa = paciente.solicitud_activa()

        if expediente:
            mediciones = list(expediente.mediciones.all())
            medicion_vigente = expediente.obtener_medicion_vigente()

        return render(
            request,
            "pacientes/paciente_detail.html",
            {
                "paciente": paciente,
                "expediente": expediente,
                "mediciones": mediciones,
                "medicion_vigente": medicion_vigente,
                "solicitud_activa": solicitud_activa,
                "rol_usuario": request.session.get(SESION_ROL),
                "nombre_usuario": request.session.get(SESION_NOMBRE),
            },
        )


class ExpedienteCreateView(RolSaludRequiredMixin, View):
    """
    CU-W02: Registrar Expediente de Paciente.
    Asocia el expediente al paciente existente, registra sus antecedentes oncológicos,
    su primera medición antropométrica y sus consentimientos dentro de una transacción atómica.
    """

    def get(self, request, curp):
        paciente = get_object_or_404(Paciente, curp=curp.upper())
        if paciente.tiene_expediente():
            messages.info(request, "Este paciente ya cuenta con un expediente registrado.")
            return redirect("pacientes:detalle", curp=paciente.curp)

        exp_form = ExpedienteForm()
        med_form = MedicionForm()
        return render(
            request,
            "pacientes/expediente_form.html",
            {
                "paciente": paciente,
                "exp_form": exp_form,
                "med_form": med_form,
            },
        )

    def post(self, request, curp):
        paciente = get_object_or_404(Paciente, curp=curp.upper())
        if paciente.tiene_expediente():
            messages.info(request, "Este paciente ya cuenta con un expediente registrado.")
            return redirect("pacientes:detalle", curp=paciente.curp)

        exp_form = ExpedienteForm(request.POST)
        med_form = MedicionForm(request.POST)

        if exp_form.is_valid() and med_form.is_valid():
            try:
                with transaction.atomic():
                    expediente = exp_form.save(commit=False)
                    expediente.paciente = paciente
                    expediente.save()

                    medicion = med_form.save(commit=False)
                    medicion.expediente = expediente
                    medicion.registrado_por = _usuario_en_sesion(request)
                    medicion.registrado_por_nombre = (
                        request.session.get(SESION_NOMBRE)
                        or request.session.get(SESION_ROL)
                        or "Enfermera/Psicóloga"
                    )
                    medicion.es_vigente = True
                    medicion.save()

                messages.success(
                    request,
                    "Expediente clínico y primera medición antropométrica creados exitosamente.",
                )
                return redirect("pacientes:detalle", curp=paciente.curp)
            except DatabaseError as exc:
                logger.exception("Error al guardar expediente en BD: %s", exc)
                messages.error(
                    request,
                    "No fue posible guardar el expediente. Intente nuevamente.",
                )
        else:
            messages.error(
                request,
                "Por favor corrige los errores señalados en el formulario.",
            )

        return render(
            request,
            "pacientes/expediente_form.html",
            {
                "paciente": paciente,
                "exp_form": exp_form,
                "med_form": med_form,
            },
        )


class MedicionCreateView(RolSaludRequiredMixin, View):
    """
    Registrar una nueva medición antropométrica para un expediente existente.
    Permite actualizar la vigencia antropométrica cuando la anterior ha vencido.
    """

    def get(self, request, id_expediente):
        expediente = get_object_or_404(
            Expediente.objects.select_related("paciente"),
            pk=id_expediente,
        )
        ultima = expediente.ultima_medicion()
        ultima_fecha = ultima.fecha_medicion if ultima else None
        form = MedicionForm(ultima_fecha=ultima_fecha)
        return render(
            request,
            "pacientes/medicion_form.html",
            {
                "expediente": expediente,
                "paciente": expediente.paciente,
                "form": form,
                "ultima_medicion": ultima,
            },
        )

    def post(self, request, id_expediente):
        expediente = get_object_or_404(
            Expediente.objects.select_related("paciente"),
            pk=id_expediente,
        )
        ultima = expediente.ultima_medicion()
        ultima_fecha = ultima.fecha_medicion if ultima else None
        form = MedicionForm(request.POST, ultima_fecha=ultima_fecha)

        if form.is_valid():
            try:
                medicion = form.save(commit=False)
                medicion.expediente = expediente
                medicion.registrado_por = _usuario_en_sesion(request)
                medicion.registrado_por_nombre = (
                    request.session.get(SESION_NOMBRE)
                    or request.session.get(SESION_ROL)
                    or "Enfermera/Psicóloga"
                )
                medicion.es_vigente = True
                medicion.save()

                messages.success(
                    request,
                    "Nueva medición antropométrica registrada correctamente. Ahora se encuentra vigente.",
                )
                return redirect("pacientes:detalle", curp=expediente.paciente.curp)
            except DatabaseError as exc:
                logger.exception("Error al guardar la nueva medición: %s", exc)
                messages.error(
                    request,
                    "No fue posible guardar la medición. Intente nuevamente.",
                )

        return render(
            request,
            "pacientes/medicion_form.html",
            {
                "expediente": expediente,
                "paciente": expediente.paciente,
                "form": form,
                "ultima_medicion": ultima,
            },
        )


class SolicitudCreateView(RolSaludRequiredMixin, View):
    """
    CU-W11: Solicitar Prótesis.
    Verifica consentimiento de captura, que no exista solicitud activa y que exista
    una medición antropométrica vigente (7 días). Vincula datos, guarda en estado
    Pendiente y notifica a SCPMEP Escritorio con manejo de excepción 1.0.E2.
    """

    def _verificar_precondiciones(self, request, expediente):
        paciente = expediente.paciente

        # RN-21: Consentimiento para captura aprobado
        if not expediente.captura_aprobada():
            messages.error(
                request,
                "El paciente no tiene aprobado el consentimiento para la captura.",
            )
            return redirect("pacientes:detalle", curp=paciente.curp)

        # RN-22: Sin solicitud activa simultánea
        if paciente.tiene_solicitud_activa():
            activa = paciente.solicitud_activa()
            messages.warning(
                request,
                f"El paciente ya tiene una solicitud activa ({activa.estado}) "
                f"programada para {activa.fecha_hora_cita.strftime('%d/%m/%Y %H:%M')} "
                f"en {activa.lugar_captura.nombre}.",
            )
            return redirect("pacientes:detalle", curp=paciente.curp)

        # Medición antropométrica vigente (7 días)
        medicion_vigente = expediente.obtener_medicion_vigente()
        if not medicion_vigente:
            ultima = expediente.ultima_medicion()
            msg = "No hay una medición antropométrica vigente para solicitar la prótesis."
            if ultima:
                msg += f" La última medición es del {ultima.fecha_medicion.strftime('%d/%m/%Y')} y supera los 7 días de vigencia."
            messages.warning(request, msg)
            return redirect("pacientes:nueva_medicion", id_expediente=expediente.id_expediente)

        return None

    def get(self, request, id_expediente):
        expediente = get_object_or_404(
            Expediente.objects.select_related("paciente"),
            pk=id_expediente,
        )
        bloqueo = self._verificar_precondiciones(request, expediente)
        if bloqueo:
            return bloqueo

        medicion_vigente = expediente.obtener_medicion_vigente()
        form = SolicitudProtesisForm()
        return render(
            request,
            "pacientes/solicitud_form.html",
            {
                "expediente": expediente,
                "paciente": expediente.paciente,
                "medicion_vigente": medicion_vigente,
                "form": form,
            },
        )

    def post(self, request, id_expediente):
        expediente = get_object_or_404(
            Expediente.objects.select_related("paciente"),
            pk=id_expediente,
        )
        bloqueo = self._verificar_precondiciones(request, expediente)
        if bloqueo:
            return bloqueo

        medicion_vigente = expediente.obtener_medicion_vigente()
        form = SolicitudProtesisForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    solicitud = form.save(commit=False)
                    solicitud.expediente = expediente
                    solicitud.paciente = expediente.paciente
                    solicitud.medicion = medicion_vigente
                    solicitud.solicitado_por = _usuario_en_sesion(request)
                    solicitud.solicitado_por_nombre = (
                        request.session.get(SESION_NOMBRE)
                        or request.session.get(SESION_ROL)
                        or "Enfermera/Psicóloga"
                    )
                    solicitud.marcar_pendiente()
                    solicitud.save()

                # Envío al sistema SCPMEP Escritorio (RN-26 / Excepción 1.0.E2)
                enviado = EnvioCapturaService.enviar(solicitud)
                if enviado:
                    messages.success(
                        request,
                        f"Solicitud #{solicitud.id_solicitud} registrada correctamente y enviada al sistema de captura.",
                    )
                else:
                    messages.warning(
                        request,
                        "La solicitud se guardó, pero no pudo enviarse al sistema de captura. Se reintentará el envío.",
                    )

                return redirect("pacientes:detalle", curp=expediente.paciente.curp)

            except DatabaseError as exc:
                logger.exception("Error al guardar la solicitud de prótesis: %s", exc)
                messages.error(
                    request,
                    "No fue posible guardar la solicitud. Intente nuevamente.",
                )
        else:
            messages.error(
                request,
                "Por favor corrige los datos señalados en la solicitud.",
            )

        return render(
            request,
            "pacientes/solicitud_form.html",
            {
                "expediente": expediente,
                "paciente": expediente.paciente,
                "medicion_vigente": medicion_vigente,
                "form": form,
            },
        )
