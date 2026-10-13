"""What happens to a registration, kept apart from the views that trigger it.

Paystack reports a payment in two places — the attendee's browser coming back,
and the webhook the conference module already receives — so confirming has to
be callable from either, and safe when both arrive at once.
"""

import logging

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from membership.email_utils import build_html_email, send_now
from membership.models import Subscription

from .models import (
    MAX_CODE_ATTEMPTS,
    EventAnswer,
    EventCertificate,
    EventRegistration,
    EventResponse,
)

logger = logging.getLogger(__name__)

PAYSTACK_INITIALIZE_URL = 'https://api.paystack.co/transaction/initialize'
PAYSTACK_VERIFY_URL = 'https://api.paystack.co/transaction/verify/{reference}'
METADATA_KIND = 'event_registration'


class RegistrationError(Exception):
    """A registration could not go ahead, for a reason worth telling the person."""


def is_current_member(user):
    """A paid subscription covering today — the same test the dashboard uses."""
    if not user or not user.is_authenticated:
        return False
    today = timezone.now().date()
    return Subscription.objects.filter(
        user=user, payment_status='paid', start_date__lte=today, end_date__gte=today,
    ).exists()


def site_url(path):
    return f"{settings.SITE_URL}{path}"


# --- registering -------------------------------------------------------------

def register(event, *, user=None, first_name='', last_name='', email='', phone=''):
    """Create or resume a registration. Returns (registration, created).

    One place per email address per event. Registering again with an address
    already confirmed returns that registration rather than a second one; an
    unpaid one is picked up again, at today's price, so an abandoned payment
    can simply be retried.
    """
    setup = event.setup
    reason = setup.registration_closed_reason()
    if reason:
        raise RegistrationError(reason)

    if user and user.is_authenticated:
        first_name = first_name or user.first_name
        last_name = last_name or user.last_name
        email = email or user.email
    email = (email or '').strip().lower()
    if not email or not first_name:
        raise RegistrationError('Please give your name and email address.')

    is_member = is_current_member(user)
    existing = EventRegistration.objects.filter(event=event, email=email).first()
    if existing and existing.status == EventRegistration.CONFIRMED:
        return existing, False

    values = {
        'user': user if user and user.is_authenticated else None,
        'first_name': first_name.strip(), 'last_name': last_name.strip(),
        'phone': phone.strip(), 'is_member': is_member,
        'amount': setup.fee_for(is_member), 'status': EventRegistration.PENDING,
    }
    if existing:
        for field, value in values.items():
            setattr(existing, field, value)
        existing.save()
        registration, created = existing, False
    else:
        try:
            with transaction.atomic():
                registration = EventRegistration.objects.create(event=event, email=email, **values)
        except IntegrityError:
            # A double click got there first.
            return EventRegistration.objects.get(event=event, email=email), False
        created = True

    if not registration.amount:
        if registration.confirm():
            send_confirmation(registration)
    return registration, created


def start_payment(registration):
    """Open a Paystack checkout for the registration. Returns the URL to send them to."""
    payload = {
        'email': registration.email,
        'amount': int(registration.amount * 100),
        'currency': 'NGN',
        'reference': registration.payment_reference,
        'callback_url': site_url(reverse('events:payment_return')),
        'metadata': {
            'kind': METADATA_KIND,
            'event_registration_id': registration.pk,
            'event_id': registration.event_id,
            'full_name': registration.full_name,
        },
    }
    try:
        response = requests.post(
            PAYSTACK_INITIALIZE_URL, json=payload, timeout=20,
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error('Paystack initialise failed for event registration %s: %s', registration.pk, exc)
        raise RegistrationError(
            'We could not reach the payment service. Your place is held — please try again in a moment.'
        ) from exc
    if not body.get('status') or not body.get('data', {}).get('authorization_url'):
        logger.error('Paystack refused event registration %s: %s', registration.pk, body)
        raise RegistrationError('The payment could not be started. Please try again.')
    return body['data']['authorization_url']


def is_event_payment(data):
    """Whether a Paystack charge belongs to an event registration."""
    metadata = data.get('metadata') or {}
    if isinstance(metadata, dict) and metadata.get('kind') == METADATA_KIND:
        return True
    return str(data.get('reference', '')).startswith('EVT-')


def apply_paystack_charge(data):
    """Confirm the registration a successful Paystack charge paid for.

    Used by the webhook with the event's own payload, and by the return page
    with the verify call's. Returns the registration, or None if it was not
    ours or could not be matched.
    """
    reference = data.get('reference', '')
    registration = EventRegistration.objects.filter(payment_reference=reference).first()
    if registration is None:
        logger.error('Event payment %s matches no registration', reference)
        return None
    if data.get('status', 'success') != 'success':
        return registration
    # Overpayment is fine — Paystack's fee is often added on top.
    if int(data.get('amount') or 0) < int(registration.amount * 100):
        logger.error(
            'Event registration %s underpaid: received %s, expected %s',
            registration.pk, data.get('amount'), int(registration.amount * 100),
        )
        return registration
    if registration.confirm(paystack_reference=reference):
        send_confirmation(registration)
    return registration


def verify_and_apply(reference):
    """Ask Paystack about a reference the browser brought back, and act on it."""
    try:
        response = requests.get(
            PAYSTACK_VERIFY_URL.format(reference=reference), timeout=20,
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
        )
        response.raise_for_status()
        data = response.json().get('data') or {}
    except (requests.RequestException, ValueError) as exc:
        logger.error('Paystack verify failed for %s: %s', reference, exc)
        return EventRegistration.objects.filter(payment_reference=reference).first()
    return apply_paystack_charge(data)


# --- the activity and the certificate ------------------------------------------

def complete_activity(registration, code, answers):
    """Record the activity and issue the certificate. Returns the certificate or None.

    `answers` is [(question, text), ...]. Raises RegistrationError when the
    activity cannot be accepted.
    """
    setup = registration.event.setup
    if not registration.is_confirmed:
        raise RegistrationError('Your registration is not confirmed yet.')
    if not setup.activity_available:
        raise RegistrationError('The post-event activity is not open.')
    if registration.has_completed_activity:
        raise RegistrationError('You have already completed this activity.')
    if registration.failed_code_attempts >= MAX_CODE_ATTEMPTS:
        raise RegistrationError(
            'Too many incorrect attendance codes. Please contact the organisers to have this reset.'
        )
    if not setup.code_matches(code):
        EventRegistration.objects.filter(pk=registration.pk).update(
            failed_code_attempts=F('failed_code_attempts') + 1,
        )
        raise RegistrationError(
            "That attendance code is not right. It was announced during the session — "
            "check with the organisers if you missed it."
        )

    with transaction.atomic():
        response = EventResponse.objects.create(registration=registration, code_entered=(code or '').strip())
        EventAnswer.objects.bulk_create([
            EventAnswer(response=response, question=question, prompt=question.prompt, answer=text)
            for question, text in answers
        ])
        certificate = None
        if setup.issues_certificates:
            certificate = EventCertificate.objects.create(
                registration=registration,
                participant_name=registration.full_name,
                event_title=registration.event.event_title,
                certificate_title=setup.certificate_title,
                cpd_hours=setup.cpd_hours,
            )
    if certificate:
        send_certificate_ready(registration, certificate)
    return certificate


# --- email ---------------------------------------------------------------------

def _send(registration, subject, template, context, text):
    html = render_to_string(template, {
        'registration': registration, 'event': registration.event,
        'setup': registration.event.setup, 'year': timezone.now().year,
        'registration_url': site_url(registration.get_absolute_url()),
        **context,
    })
    return send_now(build_html_email(subject=subject, html_body=html, to=registration.email, text_body=text))


def send_confirmation(registration):
    """The ticket: confirmation, joining details, and the link back to their page."""
    event = registration.event
    setup = event.setup
    lines = [
        f'Hello {registration.first_name},',
        '',
        f'Your place at {event.event_title} is confirmed.',
        f'Ticket ID: {registration.ticket_id}',
        f"When: {setup.start:%d %B %Y, %H:%M}",
    ]
    if setup.join_link:
        lines.append(f'Join here: {setup.join_link}')
    if setup.joining_instructions:
        lines += ['', setup.joining_instructions]
    lines += [
        '', 'Your registration page, where the post-event activity and your certificate will appear:',
        site_url(registration.get_absolute_url()),
    ]
    ok, error = _send(
        registration, f'Registration confirmed: {event.event_title}',
        'events/emails/confirmation.html', {}, '\n'.join(lines),
    )
    EventRegistration.objects.filter(pk=registration.pk).update(
        confirmation_sent_at=timezone.now() if ok else None, confirmation_error=error or '',
    )
    return ok, error


def send_activity_invitation(registration):
    """After the session: the activity is open, here is where to do it."""
    lines = [
        f'Hello {registration.first_name},',
        '',
        f'Thank you for attending {registration.event.event_title}.',
        'Complete the short post-event activity to receive your certificate:',
        site_url(registration.get_absolute_url()),
        '',
        "You will need the attendance code announced during the session.",
    ]
    return _send(
        registration, f'Get your certificate: {registration.event.event_title}',
        'events/emails/activity_invitation.html', {}, '\n'.join(lines),
    )


def send_certificate_ready(registration, certificate):
    lines = [
        f'Hello {registration.first_name},',
        '',
        f'Your {certificate.certificate_title} for {certificate.event_title} is ready.',
        f'Certificate ID: {certificate.certificate_id}',
        'Download it from your registration page:',
        site_url(registration.get_absolute_url()),
    ]
    return _send(
        registration, f'Your certificate: {certificate.event_title}',
        'events/emails/certificate_ready.html', {'certificate': certificate}, '\n'.join(lines),
    )
