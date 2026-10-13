import logging

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from membership.models import Events

from . import certificates, services
from .forms import ActivityForm, RegistrationForm, ResendLinkForm
from .models import EventCertificate, EventRegistration, EventSetup

logger = logging.getLogger(__name__)


def _event_or_404(pk):
    return get_object_or_404(Events.objects.select_related('setup'), pk=pk, is_published=True)


def _setup(event):
    try:
        return event.setup
    except EventSetup.DoesNotExist:
        return None


def event_detail(request, pk):
    """An event's own page: what it is, and the way to register."""
    event = _event_or_404(pk)
    setup = _setup(event)

    mine = None
    initial = {}
    if request.user.is_authenticated:
        user = request.user
        mine = EventRegistration.objects.filter(event=event, email=(user.email or '').lower()).first()
        initial = {
            'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email,
            'phone': getattr(user, 'phone', '') or '',
        }

    is_member = services.is_current_member(request.user)
    return render(request, 'events/event_detail.html', {
        'event': event,
        'setup': setup,
        'form': RegistrationForm(initial=initial),
        'resend_form': ResendLinkForm(),
        'my_registration': mine,
        'is_member': is_member,
        'my_fee': setup.fee_for(is_member) if setup else None,
        'closed_reason': setup.registration_closed_reason() if setup else '',
    })


@require_POST
def register(request, pk):
    event = _event_or_404(pk)
    setup = _setup(event)
    if not setup:
        raise Http404('This event does not take registrations here.')

    form = RegistrationForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please check the registration details and try again.')
        return redirect('events:detail', pk=pk)

    try:
        registration, _ = services.register(
            event, user=request.user, **form.cleaned_data,
        )
    except services.RegistrationError as exc:
        messages.error(request, str(exc))
        return redirect('events:detail', pk=pk)

    if registration.is_confirmed:
        messages.success(request, f'You are registered. Your ticket ID is {registration.ticket_id}.')
        return redirect(registration.get_absolute_url())
    return _send_to_paystack(request, registration)


def _send_to_paystack(request, registration):
    try:
        return redirect(services.start_payment(registration))
    except services.RegistrationError as exc:
        messages.error(request, str(exc))
        return redirect(registration.get_absolute_url())


@require_POST
def pay(request, token):
    """Retry an unpaid registration's payment."""
    registration = _registration_or_404(token)
    if registration.is_confirmed:
        return redirect(registration.get_absolute_url())
    return _send_to_paystack(request, registration)


def payment_return(request):
    """Where Paystack sends the payer back. The webhook may already have confirmed it."""
    reference = request.GET.get('reference') or request.GET.get('trxref') or ''
    registration = services.verify_and_apply(reference) if reference else None
    if registration is None:
        messages.error(request, 'We could not find that payment. If you were charged, please contact us.')
        return redirect('events')
    if registration.is_confirmed:
        messages.success(request, f'Payment received. Your ticket ID is {registration.ticket_id}.')
    else:
        messages.warning(
            request,
            'Your payment has not been confirmed yet. If you completed it, this page will update '
            'shortly — refresh in a minute.',
        )
    return redirect(registration.get_absolute_url())


def _registration_or_404(token):
    registration = EventRegistration.from_token(token)
    if registration is None:
        raise Http404('That registration link is not valid.')
    return registration


def registration_page(request, token):
    """The attendee's own page: ticket, joining details, activity, certificate."""
    registration = _registration_or_404(token)
    setup = _setup(registration.event)
    certificate = getattr(registration, 'certificate', None)

    form = None
    if (setup and registration.is_confirmed and setup.activity_available
            and not registration.has_completed_activity):
        form = ActivityForm(setup=setup, questions=registration.event.questions.all())

    return render(request, 'events/registration.html', _registration_context(
        request, registration, setup, certificate, form,
    ))


def _registration_context(request, registration, setup, certificate, form):
    verify_url = (
        request.build_absolute_uri(certificate.get_verify_url()) if certificate else ''
    )
    return {
        'registration': registration,
        'event': registration.event,
        'setup': setup,
        'certificate': certificate if certificate and not certificate.is_revoked else None,
        'revoked': bool(certificate and certificate.is_revoked),
        'verify_url': verify_url,
        'linkedin_url': certificates.linkedin_url(certificate, verify_url) if certificate else '',
        'form': form,
    }


@require_POST
def submit_activity(request, token):
    registration = _registration_or_404(token)
    setup = _setup(registration.event)
    if not setup:
        raise Http404()

    form = ActivityForm(request.POST, setup=setup, questions=registration.event.questions.all())
    if form.is_valid():
        try:
            certificate = services.complete_activity(
                registration, form.cleaned_data.get('attendance_code', ''), form.answers(),
            )
        except services.RegistrationError as exc:
            messages.error(request, str(exc))
        else:
            if certificate:
                messages.success(request, 'Thank you. Your certificate is ready below.')
            else:
                messages.success(request, 'Thank you — your responses have been recorded.')
            return redirect(registration.get_absolute_url())

    registration.refresh_from_db()
    return render(request, 'events/registration.html', _registration_context(
        request, registration, setup, None, form,
    ))


def download_certificate(request, token):
    registration = _registration_or_404(token)
    certificate = getattr(registration, 'certificate', None)
    if certificate is None or certificate.is_revoked:
        raise Http404('There is no certificate for this registration.')

    verify_url = request.build_absolute_uri(certificate.get_verify_url())
    pdf = certificates.render(certificate, verify_url.split('://', 1)[-1])
    certificate.record_download()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{certificates.filename(certificate)}"'
    return response


def verify_certificate(request, certificate_id):
    """Public: is this certificate genuine, and who was it issued to?"""
    certificate = (
        EventCertificate.objects.select_related('registration__event')
        .filter(certificate_id__iexact=(certificate_id or '').strip()).first()
    )
    return render(request, 'events/verify.html', {
        'certificate': certificate, 'certificate_id': certificate_id,
    })


@require_POST
def resend_link(request, pk):
    """Email a registrant their page again. Answers the same whether or not they exist."""
    event = _event_or_404(pk)
    form = ResendLinkForm(request.POST)
    if form.is_valid():
        registration = EventRegistration.objects.filter(
            event=event, email=form.cleaned_data['email'].strip().lower(),
            status=EventRegistration.CONFIRMED,
        ).first()
        if registration:
            services.send_confirmation(registration)
    messages.info(
        request,
        'If that address is registered for this event, we have emailed it a link to your registration page.',
    )
    return redirect('events:detail', pk=pk)
