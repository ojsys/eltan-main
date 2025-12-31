from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm, CustomAuthenticationForm, MemberSignupForm
from django.contrib.auth import login as auth_login, logout
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



def logout_view(request):
    logout(request)
    return redirect('login')


