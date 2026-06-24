"""Non-blocking email helpers.

Sending email inline in a request ties up an LSAPI/Passenger worker for the
whole SMTP round-trip. When the mail server is slow or rate-limiting us, those
blocked workers pile up and the server starts killing them ("Reached max
children process limit", "LSAPI: File error"). These helpers move the actual
SMTP send onto a background thread so the web worker returns immediately, and
send bulk mail over a single reused connection to stay gentle on the provider.
"""

import logging
import threading
import time

from django.core.mail import get_connection

logger = logging.getLogger(__name__)


def _run_in_background(fn, *args, **kwargs):
    thread = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread


def send_email_async(message):
    """Send a single EmailMessage in a background thread.

    The message is built by the caller (fast); only the SMTP send — the slow,
    blocking part — happens off the request thread.
    """
    def _send():
        try:
            message.send(fail_silently=False)
            logger.info(f"Async email sent to {getattr(message, 'to', None)}")
        except Exception as e:
            logger.error(f"Async email send failed (to={getattr(message, 'to', None)}): {e}")

    return _run_in_background(_send)


def send_bulk_async(messages, throttle_seconds=0.5):
    """Send many EmailMessage objects over a SINGLE SMTP connection, throttled,
    in the background.

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
