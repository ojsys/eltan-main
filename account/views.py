from django.shortcuts import render, redirect, get_object_or_404
from .forms import CustomUserCreationForm, CustomAuthenticationForm, MemberSignupForm
from django.contrib.auth import get_user_model, login as auth_login, logout
from django.contrib import messages
from membership.models import Subscription, MemberProfile
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


# All Auth Views Here

def login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            subscription = Subscription.objects.filter(user=user).last()  # Use the directly obtained user object
            if subscription and subscription.payment_status == 'paid':
                return redirect('dash')
            elif subscription and subscription.payment_status != 'paid':
                return redirect('subscription_pending')
            else:
                return redirect('subscribe')
        else:
            # Add error handling to give feedback on why login failed
            messages.error(request, "Invalid login details")
    else:
        form = CustomAuthenticationForm()
    return render(request, 'account/login.html', {'title': 'ELTAN', 'form': form})


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Update MemberProfile with phone number and state
            # (Profile is automatically created by signal)
            phone_number = form.cleaned_data.get('phone_number')
            state = form.cleaned_data.get('state')

            profile = MemberProfile.objects.get(user=user)
            profile.phone_number = phone_number
            profile.state = state
            profile.save()

            auth_login(request, user)

            # Send welcome email
            subject = 'Welcome to ELTAN'
            html_message = render_to_string('emails/welcome_email.html', {
                'email': user.email,
                'password': form.cleaned_data['password1']  # Be cautious with sending passwords via email
            })
            plain_message = strip_tags(html_message)
            from_email = settings.DEFAULT_FROM_EMAIL
            to_email = user.email

            try:
                send_mail(
                    subject,
                    plain_message,
                    from_email,
                    [to_email],
                    html_message=html_message,
                    fail_silently=False,
                )
                messages.success(request, "Registration successful. Welcome email sent!")
            except Exception as e:
                messages.warning(request, "Registration successful, but we couldn't send the welcome email. Please contact support.")
                # Log the error for debugging
                print(f"Error sending email: {str(e)}")


            return redirect('subscribe')
        else:
            messages.error(request, "Registration failed. Please correct the form errors.")
    else:
        form = CustomUserCreationForm()

    return render(request, 'account/register.html', {'title': 'ELTAN', 'form': form})



from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm, CustomAuthenticationForm, MemberSignupForm
from django.contrib.auth import login as auth_login, logout
from django.contrib import messages
from membership.models import Subscription, MemberProfile
from .models import CustomUser
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def logout_view(request):
    # Close the audit record first: logging out of a borrowed session must not
    # leave an impersonation that looks like it is still running.
    if request.session.get(impersonation.SESSION_KEY):
        impersonation.stop(request, reason='logout')
    logout(request)
    return redirect('login')


def member_search(request):
    query = request.GET.get('query')
    results = []
    if query:
        results = CustomUser.objects.filter(
            Q(eltan_number__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    return render(request, 'account/member_search.html', {'results': results, 'query': query})





# ---------------------------------------------------------------------------
# Admin impersonation
#
# Staff can borrow a member's session to see what the member sees. The rules
# that make that safe live in account/impersonation.py; these views are the
# doors into it. Both require POST, so no impersonation can ever start or stop
# from a link someone was tricked into following.
# ---------------------------------------------------------------------------

from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from . import impersonation


@staff_member_required
def impersonate_user(request, user_id):
    """Confirm, then sign the current session in as ``user_id``.

    GET shows what is about to happen and who will be able to see it afterwards;
    POST performs the switch. Deliberately two steps: taking over someone's
    account is not something to do by misclicking a row in a list.
    """
    User = get_user_model()
    target = get_object_or_404(User, pk=user_id)

    try:
        impersonation.check_permission(request.user, target)
    except impersonation.ImpersonationDenied as denied:
        messages.error(request, str(denied))
        return redirect('admin:account_customuser_changelist')

    if request.method != 'POST':
        return render(request, 'account/impersonate_confirm.html', {'target': target})

    try:
        impersonation.start(request, target)
    except impersonation.ImpersonationDenied as denied:
        messages.error(request, str(denied))
        return redirect('admin:account_customuser_changelist')

    messages.info(
        request,
        f"You are now viewing the site as {target.email}. "
        "Use the red banner at the bottom of the page to stop.",
    )
    return redirect('dash')


@require_POST
def stop_impersonation(request):
    """Hand the session back to the administrator who borrowed it.

    Not staff-gated on purpose: the person holding the session right now is the
    *member*, not a staff account, so a staff check here would lock the only
    people who can press this button out of pressing it. The session itself is
    the credential — it only works if this session was impersonating.
    """
    if not request.session.get(impersonation.SESSION_KEY):
        return redirect('home')

    impersonator = impersonation.stop(request, reason='manual')
    if impersonator is None:
        messages.info(request, "That session has ended. Please sign in again.")
        return redirect('login')

    messages.success(request, f"You are signed in as {impersonator.email} again.")
    return redirect('admin:account_customuser_changelist')
