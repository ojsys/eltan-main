"""Admin impersonation — signing in as a member to see exactly what they see.

Support questions are almost always about something only the member can see:
a certificate that will not appear, a subscription stuck on "pending", a
dashboard showing the wrong year. Asking for screenshots is slow and asking for
their password is never acceptable, so staff can borrow a member's session
instead, look, and hand it back.

The whole feature is built around three rules:

* **It can only ever reduce privilege.** A superuser is never impersonatable by
  anyone, and only a superuser may impersonate another staff member. Without
  that, a junior staff account could take over an administrator's session and
  quietly promote itself.
* **It is always visible.** Every page rendered while impersonating carries a
  banner naming both people, so nobody mistakes a borrowed session for their
  own and takes an action "as" a member without realising.
* **It is always on the record.** Every session is written to
  :class:`~account.models.ImpersonationLog` with who, whom, from where and for
  how long — the answer to "who changed this?" months later.

The real administrator's id lives in the session under :data:`SESSION_KEY`.
``django.contrib.auth.login()`` flushes the session when the user changes, so
that key is always written *after* the login call, never before.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login as auth_login
from django.utils import timezone

logger = logging.getLogger(__name__)

# Session keys. Leading underscores keep them out of the way of ordinary
# application session data.
SESSION_KEY = '_impersonator_id'
SESSION_LOG_KEY = '_impersonation_log_id'
SESSION_STARTED_AT = '_impersonation_started_at'

# An impersonated session ends itself after this long. Staff forget to click
# "stop" — a borrowed session left open on a shared machine should not stay
# usable all day.
MAX_DURATION_SECONDS = 60 * 60


class ImpersonationDenied(Exception):
    """Raised when the rules above forbid an impersonation."""


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()[:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45]


def check_permission(actor, target):
    """Raise :class:`ImpersonationDenied` unless ``actor`` may become ``target``.

    ``actor`` is the real, signed-in administrator; ``target`` is the account
    they want to borrow.
    """
    if actor is None or not actor.is_authenticated:
        raise ImpersonationDenied("You must be signed in to do that.")
    if not actor.is_active or not actor.is_staff:
        raise ImpersonationDenied("Only staff accounts can sign in as another user.")
    if target is None:
        raise ImpersonationDenied("That user does not exist.")
    if target.pk == actor.pk:
        raise ImpersonationDenied("You are already signed in as yourself.")
    if not target.is_active:
        raise ImpersonationDenied(
            "That account is deactivated. Reactivate it first if you need to see it."
        )
    # Impersonation must never be a route to more privilege than you started with.
    if target.is_superuser:
        raise ImpersonationDenied("Superuser accounts cannot be impersonated.")
    if target.is_staff and not actor.is_superuser:
        raise ImpersonationDenied(
            "Only a superuser can sign in as another staff member."
        )
    return True


def can_impersonate(actor, target):
    """Boolean form of :func:`check_permission`, for templates and admin columns."""
    try:
        check_permission(actor, target)
    except ImpersonationDenied:
        return False
    return True


def is_impersonating(request):
    return bool(getattr(request, 'impersonator', None))


def get_impersonator(request):
    """The real administrator behind the current session, or ``None``.

    Reads straight from the session, so it is usable before the middleware has
    populated ``request.impersonator``.
    """
    impersonator_id = request.session.get(SESSION_KEY)
    if not impersonator_id:
        return None
    User = get_user_model()
    return User.objects.filter(pk=impersonator_id, is_active=True, is_staff=True).first()


def _default_backend():
    """The auth backend to log a user in under.

    The target is fetched from the database rather than authenticated, so
    ``login()`` has no backend to infer and must be told one.
    """
    backends = getattr(settings, 'AUTHENTICATION_BACKENDS', None)
    return backends[0] if backends else 'django.contrib.auth.backends.ModelBackend'


def start(request, target):
    """Sign the current session in as ``target``, remembering who did it.

    Returns the :class:`~account.models.ImpersonationLog` row created for the
    session. Raises :class:`ImpersonationDenied` if the rules forbid it.
    """
    from .models import ImpersonationLog

    actor = request.user
    if is_impersonating(request) or request.session.get(SESSION_KEY):
        raise ImpersonationDenied(
            "You are already signed in as someone else. Stop that first."
        )
    check_permission(actor, target)

    log = ImpersonationLog.objects.create(
        impersonator=actor,
        impersonator_email=actor.email,
        target=target,
        target_email=target.email,
        ip_address=client_ip(request),
    )

    # login() flushes the session when the user changes, so anything we want to
    # survive has to be written afterwards.
    auth_login(request, target, backend=_default_backend())
    request.session[SESSION_KEY] = actor.pk
    request.session[SESSION_LOG_KEY] = log.pk
    request.session[SESSION_STARTED_AT] = timezone.now().isoformat()
    request.impersonator = actor

    logger.warning(
        "Impersonation started: %s (#%s) is now acting as %s (#%s) from %s",
        actor.email, actor.pk, target.email, target.pk, log.ip_address,
    )
    return log


def stop(request, reason=''):
    """Hand the session back to the administrator who borrowed it.

    Returns the administrator, or ``None`` if this session was not impersonating
    (or the administrator's account has since been deactivated or destaffed, in
    which case the session is simply logged out).
    """
    from django.contrib.auth import logout as auth_logout
    from .models import ImpersonationLog

    impersonator = get_impersonator(request)
    log_id = request.session.get(SESSION_LOG_KEY)
    was_impersonating = bool(request.session.get(SESSION_KEY))

    if log_id:
        ImpersonationLog.objects.filter(pk=log_id, ended_at__isnull=True).update(
            ended_at=timezone.now(), end_reason=reason or 'manual',
        )

    if not was_impersonating:
        return None

    if impersonator is None:
        # The administrator lost their staff rights or was deactivated while
        # impersonating. Returning the session to them would be wrong, and
        # leaving it as the member would strand a borrowed session, so end it.
        logger.warning("Impersonation ended but the impersonator is no longer valid; logging out.")
        auth_logout(request)
        return None

    auth_login(request, impersonator, backend=_default_backend())
    # login() flushed the session, but clear the keys defensively in case a
    # future Django reuses the session instead.
    for key in (SESSION_KEY, SESSION_LOG_KEY, SESSION_STARTED_AT):
        request.session.pop(key, None)
    request.impersonator = None

    logger.warning(
        "Impersonation ended (%s): session returned to %s (#%s)",
        reason or 'manual', impersonator.email, impersonator.pk,
    )
    return impersonator


def expired(request):
    """True when the current impersonation has run past :data:`MAX_DURATION_SECONDS`."""
    started = request.session.get(SESSION_STARTED_AT)
    if not started:
        return False
    try:
        started_at = timezone.datetime.fromisoformat(started)
    except (TypeError, ValueError):
        # An unreadable timestamp is treated as expired: better to end a session
        # early than to leave one running that we cannot age out.
        return True
    if timezone.is_naive(started_at):
        started_at = timezone.make_aware(started_at)
    return (timezone.now() - started_at).total_seconds() > MAX_DURATION_SECONDS
