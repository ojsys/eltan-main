"""Email helpers.

Two things matter here:

1. **Reliability.** Transactional mail (a conference ticket, a payment receipt)
   must actually be delivered, and when it is not we must know. So those sends
   are synchronous and return an outcome — `EMAIL_TIMEOUT` keeps a slow mail
   server from tying up a worker forever, and the caller records the failure so
   staff can retry it.

2. **Not blocking the worker on bulk mail.** Sending hundreds of emails inline
   in a request ties up an LSAPI/Passenger worker for the whole run; those
   blocked workers pile up and the server starts killing them ("Reached max
   children process limit"). Bulk sends therefore go to a background thread over
   a single reused SMTP connection.

Fire-and-forget sending is deliberately NOT used for tickets/receipts any more:
a daemon thread can be killed when Passenger recycles the worker, which silently
loses the mail.
"""

import logging
import smtplib
import threading
import time
from email.utils import parseaddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

# A send that fails with one of these is worth one immediate retry — they are
# transient (greylisting, connection reset, rate limit) rather than a bad
# address or bad credentials.
_TRANSIENT_ERRORS = (
    smtplib.SMTPServerDisconnected,
    smtplib.SMTPConnectError,
    smtplib.SMTPHeloError,
    TimeoutError,
    ConnectionError,
    OSError,
)


def _run_in_background(fn, *args, **kwargs):
    thread = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread


# SMTP logins that are account identifiers rather than mailboxes. Kept in step
# with _RELAY_LOGIN_DOMAINS in settings/base.py.
_RELAY_LOGIN_DOMAINS = (
    'smtp-brevo.com', 'sendinblue.com', 'smtp-relay.brevo.com',
    'sendgrid.net', 'amazonses.com', 'mailtrap.io', 'postmarkapp.com',
)


def _sender_address(from_email):
    """Pull the bare address out of a 'Name <addr@example.com>' header value."""
    return parseaddr(from_email or '')[1]


def _is_relay_login(address):
    if not address or address.count('@') != 1:
        return False
    domain = address.rsplit('@', 1)[1].lower()
    return any(domain == relay or domain.endswith('.' + relay) for relay in _RELAY_LOGIN_DOMAINS)


def _looks_like_sender_rejection(exc):
    """True when a provider error is really 'this From: address is not authorised'."""
    text = str(exc).lower()
    return any(
        phrase in text
        for phrase in (
            'sender you used', 'not valid', 'unverified', 'verify your sender',
            'validate your sender', 'authenticate your domain', 'sender address',
            'not owned by user', 'domain not verified', 'from address',
        )
    )


def _sender_rejected_message(exc):
    """Explain a rejected From: address in terms of what to actually change."""
    return (
        f"The mail server rejected the sender address {settings.DEFAULT_FROM_EMAIL!r}. "
        f"Provider said: {exc}. "
        "Set DEFAULT_FROM_EMAIL in .env to an address your provider has verified "
        "(for Brevo/SendGrid the SMTP login is NOT a valid sender — verify a sender "
        "or authenticate the eltanigeria.org domain in the provider's dashboard)."
    )


def build_html_email(subject, html_body, to, reply_to=None, text_body=None):
    """Build a multipart email with an HTML body and a plain-text alternative.

    Sending HTML only (``content_subtype = 'html'``) makes several providers and
    spam filters mark the message down, and it renders as raw markup in
    text-only clients. Always ship both parts.
    """
    recipients = [to] if isinstance(to, str) else list(to)
    reply_to_addr = reply_to or getattr(settings, 'CONTACT_EMAIL', None) or settings.DEFAULT_FROM_EMAIL

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body or strip_tags(html_body),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        reply_to=[reply_to_addr],
    )
    message.attach_alternative(html_body, 'text/html')
    return message


def send_now(message, retries=1):
    """Send one message synchronously.

    Returns ``(ok, error)`` — ``error`` is a human-readable string when the send
    failed, so the caller can surface it instead of claiming success. Never
    raises: a mail problem must not break a confirmed payment.
    """
    recipients = getattr(message, 'to', None)
    attempt = 0
    last_error = None

    while attempt <= retries:
        try:
            sent = message.send(fail_silently=False)
            if sent:
                logger.info(f"Email sent to {recipients}: {message.subject!r}")
                return True, None
            last_error = "The mail server accepted the request but delivered 0 messages."
        except smtplib.SMTPAuthenticationError as e:
            # Bad credentials never fix themselves on retry.
            logger.error(f"SMTP authentication failed sending to {recipients}: {e}")
            return False, (
                "The mail server rejected the login credentials "
                "(check EMAIL_HOST_USER / EMAIL_HOST_PASSWORD)."
            )
        except smtplib.SMTPSenderRefused as e:
            logger.error(f"SMTP sender refused ({settings.DEFAULT_FROM_EMAIL}) for {recipients}: {e}")
            return False, _sender_rejected_message(e)
        except smtplib.SMTPDataError as e:
            # Relay providers (Brevo, SendGrid, ...) often reject an unverified
            # sender here rather than at MAIL FROM, so check for that first.
            if _looks_like_sender_rejection(e):
                logger.error(f"SMTP rejected sender ({settings.DEFAULT_FROM_EMAIL}) for {recipients}: {e}")
                return False, _sender_rejected_message(e)
            last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Email send failed to {recipients}: {last_error}")
            break
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipients refused {recipients}: {e}")
            return False, f"The mail server rejected the recipient address {recipients}."
        except _TRANSIENT_ERRORS as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.warning(f"Transient email failure to {recipients} (attempt {attempt + 1}): {last_error}")
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Email send failed to {recipients}: {last_error}")
            break

        attempt += 1
        if attempt <= retries:
            time.sleep(1)

    logger.error(f"Giving up on email to {recipients}: {last_error}")
    return False, last_error or "Unknown mail error."


def send_email_async(message):
    """Send a single message on a background thread, fire-and-forget.

    Only for mail whose loss is tolerable (notices, announcements). For anything
    the recipient is owed — tickets, receipts — use :func:`send_now` so the
    outcome is known and recorded.
    """
    def _send():
        send_now(message)

    return _run_in_background(_send)


def send_bulk_async(messages, throttle_seconds=0.5):
    """Send many messages over a SINGLE SMTP connection, throttled, in the
    background.

    Returns immediately so the triggering request (e.g. an admin action) is not
    blocked while hundreds of emails go out. A per-message failure is logged and
    skipped rather than aborting the whole run.

    Note: this stays within the provider's connection, but it cannot raise the
    provider's *daily* cap — for large volumes use a transactional provider.
    """
    messages = list(messages)

    def _send_all():
        sent = failed = 0
        try:
            connection = get_connection()
            connection.open()
        except Exception as e:
            logger.error(f"Could not open SMTP connection for bulk send: {e}")
            return
        try:
            for msg in messages:
                try:
                    msg.connection = connection
                    msg.send(fail_silently=False)
                    sent += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Bulk email to {getattr(msg, 'to', None)} failed: {e}")
                if throttle_seconds:
                    time.sleep(throttle_seconds)
        finally:
            try:
                connection.close()
            except Exception:
                pass
        logger.info(f"Bulk email run complete: {sent} sent, {failed} failed.")

    return _run_in_background(_send_all)


def check_email_configuration():
    """Return ``(ok, problems)`` describing anything that would stop mail going out.

    Used by the ``test_email`` management command and the admin's SMTP check so a
    misconfiguration is visible before members start missing their tickets.
    """
    problems = []
    backend = getattr(settings, 'EMAIL_BACKEND', '')

    if 'console' in backend or 'locmem' in backend or 'dummy' in backend:
        problems.append(
            f"EMAIL_BACKEND is {backend!r} — mail is not actually delivered. "
            "Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend."
        )
        return False, problems

    if not settings.EMAIL_HOST:
        problems.append("EMAIL_HOST is empty.")
    if not settings.EMAIL_HOST_USER:
        problems.append("EMAIL_HOST_USER is empty — SMTP login will fail.")
    if not settings.EMAIL_HOST_PASSWORD:
        problems.append("EMAIL_HOST_PASSWORD is empty — SMTP login will fail.")
    if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
        problems.append("EMAIL_USE_TLS and EMAIL_USE_SSL are both on; enable only one.")

    # The single most common cause of "sent successfully" mail that never arrives:
    # a From: address the provider has not authorised.
    sender = _sender_address(settings.DEFAULT_FROM_EMAIL)
    if not sender:
        problems.append(f"DEFAULT_FROM_EMAIL ({settings.DEFAULT_FROM_EMAIL!r}) is not a usable address.")
    elif _is_relay_login(sender):
        problems.append(
            f"DEFAULT_FROM_EMAIL is {sender!r}, which is an SMTP *login*, not a sendable address. "
            "Relay providers reject it. Set DEFAULT_FROM_EMAIL in .env to a sender you have "
            "verified in the provider's dashboard, e.g. 'ELTAN <nationalsec@eltanigeria.org>'."
        )

    try:
        connection = get_connection(fail_silently=False)
        connection.open()
        connection.close()
    except Exception as e:
        problems.append(f"Could not connect to {settings.EMAIL_HOST}:{settings.EMAIL_PORT} — {type(e).__name__}: {e}")

    return (not problems), problems
