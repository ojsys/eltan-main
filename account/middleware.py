"""Middleware that makes an impersonated session obvious and bounded.

Three jobs, in the order they matter:

1. Expose the real administrator as ``request.impersonator`` so views and
   templates can tell a borrowed session from a real one.
2. End the session automatically once it has run too long, or if the
   administrator behind it has lost their staff rights in the meantime.
3. Paint a banner on every page that comes back, naming both people and
   offering a one-click way out.

The banner is injected here rather than added to a base template because this
site has several base templates plus the Django admin, and a borrowed session
that *looks* ordinary on even one page is the failure this feature must not
have. Injecting into the response catches all of them at once.
"""

from django.contrib import messages
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import escape

from . import impersonation

# Only ever touch real, complete HTML pages.
_INJECTABLE_TYPES = ('text/html', 'application/xhtml+xml')

# The admin is closed while a session is borrowed. A superuser may impersonate a
# staff member, and without this they could act in the admin *as* that person —
# payments verified, certificates revoked, all under the wrong name. Stopping
# first takes one click and puts the actions back on the right account.
_ADMIN_PREFIX = '/admin/'


class ImpersonationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.impersonator = None

        if request.session.get(impersonation.SESSION_KEY):
            if impersonation.expired(request):
                impersonation.stop(request, reason='expired')
            else:
                impersonator = impersonation.get_impersonator(request)
                if impersonator is None:
                    # Staff rights revoked mid-session: end it rather than leave
                    # a borrowed session running with nobody accountable for it.
                    impersonation.stop(request, reason='revoked')
                else:
                    request.impersonator = impersonator

        if request.impersonator and request.path.startswith(_ADMIN_PREFIX):
            messages.warning(
                request,
                f"The admin is closed while you are viewing the site as "
                f"{request.user.email}. Stop first, using the red banner.",
            )
            return redirect('dash')

        response = self.get_response(request)

        if getattr(request, 'impersonator', None):
            response = self._inject_banner(request, response)
        return response

    def _inject_banner(self, request, response):
        if getattr(response, 'streaming', False) or response.status_code in (301, 302, 304):
            return response
        content_type = (response.get('Content-Type') or '').split(';')[0].strip().lower()
        if content_type not in _INJECTABLE_TYPES:
            return response
        # A downloadable file that happens to be HTML is not a page to decorate.
        if 'attachment' in (response.get('Content-Disposition') or '').lower():
            return response

        try:
            html = response.content.decode(response.charset or 'utf-8')
        except (UnicodeDecodeError, AttributeError):
            return response
        if '</body>' not in html:
            return response

        banner = self._banner_html(request)
        response.content = html.replace('</body>', banner + '</body>', 1).encode(
            response.charset or 'utf-8'
        )
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        return response

    def _banner_html(self, request):
        impersonator = request.impersonator
        target = request.user
        # get_token both returns the token and ensures CsrfViewMiddleware sets
        # the cookie on the way out — this middleware runs before it on response.
        token = get_token(request)
        stop_url = reverse('stop_impersonation')

        target_name = f"{target.first_name} {target.last_name}".strip() or target.email
        admin_name = f"{impersonator.first_name} {impersonator.last_name}".strip() or impersonator.email

        return f'''
<div id="eltan-impersonation-banner" role="alert" style="
    position:fixed; left:0; right:0; bottom:0; z-index:2147483647;
    background:#7f1d1d; color:#fff; border-top:3px solid #fca5a5;
    font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif; font-size:14px;
    box-shadow:0 -4px 18px rgba(0,0,0,.35);">
  <div style="max-width:1200px; margin:0 auto; padding:10px 16px;
              display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
    <span style="background:#fca5a5; color:#7f1d1d; font-weight:700; font-size:11px;
                 letter-spacing:1px; text-transform:uppercase; padding:4px 9px;
                 border-radius:999px; white-space:nowrap;">Viewing as</span>
    <span style="flex:1 1 260px; line-height:1.45;">
      You are signed in as <strong>{escape(target_name)}</strong>
      (<span style="opacity:.85;">{escape(target.email)}</span>).
      Your own account is <strong>{escape(admin_name)}</strong>
      (<span style="opacity:.85;">{escape(impersonator.email)}</span>).
      Anything you do here is recorded against this member.
    </span>
    <form method="post" action="{stop_url}" style="margin:0; flex:0 0 auto;">
      <input type="hidden" name="csrfmiddlewaretoken" value="{token}">
      <button type="submit" style="
          background:#fff; color:#7f1d1d; border:0; border-radius:999px;
          padding:8px 18px; font-size:14px; font-weight:700; cursor:pointer;">
        Stop viewing as this user
      </button>
    </form>
  </div>
</div>
<style>body {{ padding-bottom:76px !important; }}</style>
'''
