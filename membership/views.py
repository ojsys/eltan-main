from django.utils import timezone
from datetime import timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.http import HttpResponse, Http404, FileResponse
from django.core.files.storage import default_storage
from django.template.loader import get_template, render_to_string
from weasyprint import HTML
from xhtml2pdf import pisa
from django.db import models
from django.conf import settings
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import EltanConference, EltanConferenceRegistration, MemberProfile, Subscription, Sigs, SigsRegistration, Events, News, Resource, Certificate, Newsletter, ELTANYearSetting, Download, ExcoMember
from .forms import ConferenceRegistrationForm, MemberProfileUpdateForm, SigsForm, SubscriptionForm, DownloadForm, SponsorApplicationForm
import qrcode
import os
import requests
from urllib.parse import quote
from decimal import Decimal, ROUND_HALF_UP
import logging
import uuid
import hmac
import hashlib
import json
import tempfile
from io import BytesIO
from .utils import get_subscription_eltan_year
from .utils import Paystack

from django.core.mail import send_mail, EmailMultiAlternatives, EmailMessage
from django.utils.html import strip_tags
from django.db import OperationalError as DBOperationalError




logger = logging.getLogger(__name__)
path_qr = "../static/images/qrcodes"


api_key = settings.PAYSTACK_SECRET_KEY
url = settings.PAYSTACK_INITIALIZE_PAYMENT_URL



def index(request):
    user=request.user
    events = Events.objects.filter()[:1]
    
    upcoming_conferences = EltanConference.objects.filter(
        end_date__gte=timezone.now().date(),
        is_active=True
    ).order_by('-created_at')[:1]  # Limit to 1 most recent
    
    context = {'title': 'ELTAN - Home', 'events': events, 'subscription': subscription, 'conferences': upcoming_conferences,}
    return render(request, 'membership/index.html', context)

def home_redesigned(request):
    """Modern landing page with Material Design 3
    Aligns redesigned layout with current homepage content (events, conferences, partners).
    """
    # Get dynamic CMS content
    homepage = None
    features = []
    statistics = []
    faqs = []
    partners = []
    testimonials = []

    try:
        from core.models_cms import HomePage, Feature, Statistic, FAQ, Partner, Testimonial, HeroSlide, SocialLink
        from core.models import SiteSettings

        # Get homepage content
        homepage = HomePage.objects.filter(is_active=True).first()

        # Get active features
        features = Feature.objects.filter(is_active=True).order_by('order')[:6]

        # Get active statistics
        statistics = Statistic.objects.filter(is_active=True).order_by('order')[:4]

        # Get active FAQs
        faqs = FAQ.objects.filter(is_active=True).order_by('order')[:5]

        # Get active partners
        partners = Partner.objects.filter(is_active=True).order_by('order')

        # Get active testimonials
        testimonials = Testimonial.objects.filter(is_active=True).order_by('order')[:3]

        # Get hero slides
        slides = HeroSlide.objects.filter(is_active=True).order_by('order')

        # Site settings and social links for footer
        site_settings = SiteSettings.objects.first()
        social_links = SocialLink.objects.filter(is_active=True).order_by('order')
    except:
        slides = []
        site_settings = None
        social_links = []

    # Get upcoming events (align with current homepage content)
    upcoming_events = Events.objects.filter(
        event_date__gte=timezone.now().date()
    ).order_by('event_date')[:3]

    # Get active/upcoming conferences (align with current homepage CTA)
    try:
        qs_conf = EltanConference.objects.filter(
            end_date__gte=timezone.now().date(),
            is_active=True
        ).order_by('start_date')[:2]
        upcoming_conferences = list(qs_conf)
    except DBOperationalError:
        qs_conf = EltanConference.objects.only(
            'id', 'title', 'theme', 'image', 'start_date', 'end_date', 'venue',
            'registration_start', 'registration_end', 'early_bird_end',
            'member_fee', 'member_early_bird_fee', 'non_member_fee',
            'non_member_early_bird_fee', 'international_delegate_fee', 'is_active'
        ).filter(
            end_date__gte=timezone.now().date(),
            is_active=True
        ).order_by('start_date')[:2]
        upcoming_conferences = list(qs_conf)
    active_conference = upcoming_conferences[0] if upcoming_conferences else None

    # Get latest news
    latest_news = News.objects.filter(
        is_published=True
    ).order_by('-date_added')[:3]

    # Dynamic, data-driven statistics (override to ensure live numbers)
    from account.models import CustomUser
    today = timezone.now().date()
    total_members_all = CustomUser.objects.count()
    paid_subscriptions_total = Subscription.objects.filter(payment_status='paid').count()
    active_members = Subscription.objects.filter(
        payment_status='paid', start_date__lte=today, end_date__gte=today
    ).values('user').distinct().count()
    # Count distinct states, excluding None, empty strings, and 'Select' option
    chapters_count_raw = MemberProfile.objects.exclude(state__in=[None, '', 'Select']).values('state').distinct().count()
    # Subtract 1 to account for 'Select' placeholder if it slipped through (37 states in Nigeria)
    chapters_count = max(0, chapters_count_raw - 1) if chapters_count_raw > 37 else chapters_count_raw
    downloads_count = Download.objects.count()
    events_12m = Events.objects.filter(event_date__gte=today - timedelta(days=365)).count()

    statistics = [
        {
            'icon': 'people',
            'number': f"{total_members_all}+",
            'label': 'Members',
            'color': '#E67918',
        },
        {
            'icon': 'location_city',
            'number': f"{chapters_count}",
            'label': 'Locations',
            'color': '#00796B',
        },
        {
            'icon': 'download',
            'number': f"{downloads_count}",
            'label': 'Resource Downloads',
            'color': '#4F46E5',
        },
        {
            'icon': 'workspace_premium',
            'number': f"{paid_subscriptions_total}",
            'label': 'Paid Subscriptions',
            'color': '#1565C0',
        },
    ]
    total_members = total_members_all
    total_events = events_12m

    context = {
        'title': 'ELTAN - You can Control All your Professional Growth through ELTAN',
        'homepage': homepage,
        'features': features,
        'statistics': statistics,
        'faqs': faqs,
        'partners': partners,
        'testimonials': testimonials,
        'upcoming_events': upcoming_events,
        'upcoming_conferences': upcoming_conferences,
        'active_conference': active_conference,
        'latest_news': latest_news,
        'total_members': total_members,
        'total_events': total_events,
        'slides': slides,
        'site_settings': site_settings,
        'social_links': social_links,
    }
    return render(request, 'landing/home_redesigned.html', context)

def about(request):
    """About page with dynamic leadership data"""
    user = request.user

    # Fetch current executive members (active and not archived)
    current_exco = ExcoMember.objects.filter(
        is_active=True,
        is_archived=False
    ).select_related('user').prefetch_related('user__memberprofile').order_by('order', 'position')

    # Fetch past executive members (archived)
    past_exco = ExcoMember.objects.filter(
        is_archived=True
    ).select_related('user').prefetch_related('user__memberprofile').order_by('-start_date', 'order')

    context = {
        'title': 'ELTAN - About',
        'current_exco': current_exco,
        'past_exco': past_exco,
        'has_current_exco': current_exco.exists(),
        'has_past_exco': past_exco.exists(),
    }

    return render(request, 'membership/about.html', context)

################### Display SIGs #################################
def sigs(request):
    """Display all active SIGs"""
    sigs = Sigs.objects.filter(is_active=True)
    user_sigs = []

    if request.user.is_authenticated:
        # Get list of SIG IDs user is already a member of
        user_sigs = list(request.user.sig_memberships.values_list('sig_id', flat=True))

    context = {
        'title': 'ELTAN - Special Interest Groups',
        'sigs': sigs,
        'user_sigs': user_sigs
    }
    return render(request, 'membership/sigs.html', context)

def sig_detail(request, pk):
    """Display detailed view of a specific SIG"""
    sig = get_object_or_404(Sigs, pk=pk)
    members = sig.get_members()
    is_member = sig.is_member(request.user) if request.user.is_authenticated else False

    context = {
        'title': f'ELTAN - {sig.title}',
        'sig': sig,
        'members': members,
        'is_member': is_member,
        'member_count': sig.member_count,
    }
    return render(request, 'membership/sig_detail.html', context)

@login_required
def join_sig(request, pk):
    """Allow authenticated user to join a SIG"""
    sig = get_object_or_404(Sigs, pk=pk, is_active=True)

    # Check if user is already a member
    if not sig.is_member(request.user):
        SigsRegistration.objects.create(user=request.user, sig=sig)
        messages.success(request, f'You have successfully joined {sig.title}!')
    else:
        messages.info(request, f'You are already a member of {sig.title}.')

    return redirect('sig_detail', pk=pk)

@login_required
def leave_sig(request, pk):
    """Allow authenticated user to leave a SIG"""
    sig = get_object_or_404(Sigs, pk=pk)

    # Remove membership if it exists
    membership = SigsRegistration.objects.filter(user=request.user, sig=sig).first()
    if membership:
        membership.delete()
        messages.success(request, f'You have left {sig.title}.')
    else:
        messages.info(request, f'You are not a member of {sig.title}.')

    return redirect('sig_detail', pk=pk)

# Add Sigs (Admin functionality - should be restricted)
@login_required
def add_sigs(request):
    """Create a new SIG (should be admin-only)"""
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to create SIGs.')
        return redirect('sigs')

    if request.method == 'POST':
        form = SigsForm(request.POST or None, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'SIG created successfully!')
            return redirect('sigs')
    else:
        form = SigsForm()
    context = {'form': form, 'title': 'Create New SIG'}
    return render(request, 'membership/add_sigs.html', context)

################## Dashboard Display #######################
@login_required
def dash(request):
    user = request.user
    today = timezone.now().date()

    # Latest subscription
    subscription = Subscription.objects.filter(user=user).order_by('-end_date').first()

    # Determine active subscription
    active_subscription = None
    if subscription and subscription.payment_status == 'paid' and subscription.start_date <= today <= subscription.end_date:
        active_subscription = subscription

    # Compute membership progress and days remaining
    membership_progress = 0
    if active_subscription:
        total_days = (active_subscription.end_date - active_subscription.start_date).days or 1
        elapsed_days = max(0, (today - active_subscription.start_date).days)
        membership_progress = min(100, max(0, int((elapsed_days / total_days) * 100)))
        # Attach convenience attr for template
        active_subscription.days_remaining = max(0, (active_subscription.end_date - today).days)

    # Stats for dashboard
    try:
        events_attended = EltanConferenceRegistration.objects.filter(user=user, payment_status='completed').count()
    except Exception:
        events_attended = 0

    try:
        resources_downloaded = Download.objects.filter(email=user.email).count()
    except Exception:
        resources_downloaded = 0

    try:
        certificates_earned = Certificate.objects.filter(subscription__user=user).count()
    except Exception:
        certificates_earned = 0

    stats = {
        'events_attended': events_attended,
        'resources_downloaded': resources_downloaded,
        'certificates_earned': certificates_earned,
    }

    # Sidebar items: upcoming events and latest news for the dashboard
    upcoming_events = Events.objects.filter(event_date__gte=today).order_by('event_date')[:3]
    latest_news = News.objects.filter(is_published=True).order_by('-date_added')[:3]

    # Get user's SIGs
    user_sigs = Sigs.objects.filter(memberships__user=user, is_active=True).order_by('title')

    context = {
        'active_subscription': active_subscription,
        'membership_progress': membership_progress,
        'stats': stats,
        'upcoming_events': upcoming_events,
        'latest_news': latest_news,
        'user_sigs': user_sigs,
    }

    # Use the modern dashboard theme
    return render(request, 'dashboard/modern_dashboard.html', context)



# -----------------------------------------------------

@login_required
def subscription(request):
    user = request.user
    subscription = Subscription.objects.filter(user=user).first()
    form = SubscriptionForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        payment_method = request.POST.get('payment_method')
        membership_type = form.cleaned_data.get('membership_type')
        state_chapter = form.cleaned_data.get('state_chapter')
        eltan_year = form.cleaned_data.get('eltan_year')
        qualification_certificate = form.cleaned_data.get('qualification_certificate')

        # Determine payment amount based on membership type
        if 'New Membership' in membership_type:
            payment_amount = 5500
        else:  # Renew Membership
            payment_amount = 3000

        if payment_method == 'paystack':
            # Store subscription data in session for Paystack payment
            request.session['subscription_data'] = {
                'membership_type': membership_type,
                'state_chapter': state_chapter,
                'eltan_year': eltan_year,
                'payment_amount': payment_amount,
            }
            # Store qualification certificate in session (as file path or handle separately)
            # For now, we'll handle it after payment verification
            # Redirect to Paystack payment initiation
            return redirect('initiate_subscription_payment')

        elif payment_method == 'manual':
            # Handle manual payment with proof upload
            payment_proof = form.cleaned_data.get('payment_proof')

            if subscription and subscription.end_date < timezone.now().date():
                # Renew existing subscription
                subscription = renew_subscription(subscription, payment_proof, payment_amount, state_chapter, qualification_certificate)
                return redirect('subscribe_success')
            else:
                # Create new subscription
                subscription = create_subscription(user, payment_proof, payment_amount, state_chapter, qualification_certificate, payment_method='manual')
                return redirect('subscription_pending')

    context = {
        'subscription': subscription,
        'form': form,
    }
    return render(request, 'membership/subscription.html', context)

def create_subscription(user, payment_proof, payment_amount, state_chapter, qualification_certificate=None, payment_method='manual'):
    subscription = Subscription.objects.create(
        user=user,
        payment_proof=payment_proof,
        payment_amount=payment_amount,
        state_chapter=state_chapter,
        qualification_certificate=qualification_certificate,
        payment_status='pending',
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timezone.timedelta(days=365)  # Assuming 1-year subscription
    )

    user.is_subscribed = True
    user.save()  # This will trigger the ELTAN Number assignment

    return subscription

def renew_subscription(subscription, payment_proof, payment_amount, state_chapter, qualification_certificate=None):
    subscription.payment_proof = payment_proof
    subscription.payment_amount = payment_amount
    subscription.state_chapter = state_chapter
    subscription.qualification_certificate = qualification_certificate
    subscription.payment_status = 'pending'
    subscription.start_date = timezone.now().date()
    subscription.end_date = timezone.now().date() + timezone.timedelta(days=365)  # Assuming 1-year renewal
    subscription.save()

    user = subscription.user
    user.is_subscribed = True
    user.save()  # This will ensure ELTAN Number is assigned if it wasn't before

    return subscription


@login_required
def subscribe_past_year(request, eltan_year):
    eltan_year_setting = get_object_or_404(ELTANYearSetting, eltan_year=eltan_year)
    
    # Check if user already subscribed for this year
    existing = Subscription.objects.filter(user=request.user, eltan_year=eltan_year).first()
    if existing:
        if existing.payment_status != 'paid':
            return redirect('complete_subscription_payment', subscription_id=existing.id)
        
        messages.warning(request, f"You have already subscribed for ELTAN Year {eltan_year}.")
        return redirect('list_certificates')

    # Create new unpaid subscription
    Subscription.objects.create(
        user=request.user,
        eltan_year=eltan_year,
        start_date=eltan_year_setting.start_date,
        end_date=eltan_year_setting.end_date,
        payment_status='pending', 
        membership_type='Renew Membership',  
        
    )
    
    messages.success(request, f"Subscription created for ELTAN Year {eltan_year}. Please complete payment.")
    return redirect('list_certificates')


# @login_required
# def subscribe_past_year(request, eltan_year):
#     user = request.user
#     current_date = timezone.now().date()

#     # Check if the user has an active subscription for the current ELTAN Year
#     active_subscription = Subscription.objects.filter(
#         user=user,
#         start_date__lte=current_date,
#         end_date__gte=current_date,
#         payment_status='paid'
#     ).exists()

#     if not active_subscription:
#         messages.error(request, "You must have an active subscription for the current ELTAN Year before subscribing to past years.")
#         return redirect('list_certificates')

#     # Ensure the requested year is within the allowed range (up to 5 years prior)
#     latest_eltan_year = ELTANYearSetting.objects.order_by('-eltan_year').first()
#     if latest_eltan_year:
#         latest_start_year = int(latest_eltan_year.eltan_year.split('/')[0])
#         allowed_past_years = [f"{year}/{year+1}" for year in range(latest_start_year - 5, latest_start_year)]
#     else:
#         allowed_past_years = []

#     if eltan_year not in allowed_past_years:
#         messages.error(request, "You can only subscribe for past ELTAN Years up to 5 years prior.")
#         return redirect('list_certificates')

#     # Check if the user already has a subscription for this past year
#     existing_subscription = Subscription.objects.filter(user=user, eltan_year=eltan_year).first()
#     if existing_subscription:
#         if existing_subscription.payment_status != 'paid':
#             return redirect('complete_subscription_payment', subscription_id=existing_subscription.id)
#         else:
#             messages.info(request, f"You already have a subscription for ELTAN year {eltan_year}.")
#             return redirect('list_certificates')

#     # Create new subscription for past ELTAN Year
#     subscription = Subscription.objects.create(
#         user=user,
#         eltan_year=eltan_year,
#         membership_type='Renew Membership',
#         payment_status='pending',
#         start_date=calculate_start_date(eltan_year),
#         end_date=calculate_end_date(eltan_year)
#     )

#     return redirect('complete_subscription_payment', subscription_id=subscription.id)


def calculate_start_date(eltan_year):
    # Parse the ELTAN year (format: "2023/2024")
    start_year = int(eltan_year.split('/')[0])
    # Assuming ELTAN year starts in September
    return date(start_year, 9, 1)

def calculate_end_date(eltan_year):
    # Parse the ELTAN year (format: "2023/2024")
    end_year = int(eltan_year.split('/')[1])
    # Assuming ELTAN year ends in August
    return date(end_year, 8, 31)
    

@login_required
def complete_subscription_payment(request, subscription_id):
    """
    View to handle completing payment for a pending subscription
    """
    try:
        subscription = Subscription.objects.get(id=subscription_id, user=request.user)
        
        # Pre-fill the form with subscription data
        initial_data = {
            'state_chapter': subscription.state_chapter,
        }
        
        form = SubscriptionForm(request.POST or None, request.FILES or None, initial=initial_data)
        
        if request.method == 'POST':
            if form.is_valid():
                payment_amount = form.cleaned_data.get('payment_amount')
                payment_proof = form.cleaned_data.get('payment_proof')
                state_chapter = form.cleaned_data.get('state_chapter')
                
                # Update the existing subscription
                subscription.payment_proof = payment_proof
                subscription.payment_amount = payment_amount
                subscription.state_chapter = state_chapter
                subscription.payment_status = 'pending'  # Reset to pending for admin review
                subscription.save()
                
                return redirect('subscription_pending')
        
        context = {
            'form': form,
            'subscription': subscription,
            'is_completing_payment': True  # Flag to customize the template
        }
        
        return render(request, 'membership/subscription.html', context)
        
    except Subscription.DoesNotExist:
        messages.error(request, "Subscription not found or you don't have permission to access it.")
        return redirect('list_certificates')    

# --------------------------------------------------


@login_required
def subscribe_success(request):
    return render(request,'membership/subscribe_success.html')
    
@login_required
def subscribe_pending(request):
    return render(request,'membership/subscription_pending.html')


# Here we wrote the logic for all conference related components



########################## Conference Views

def conference_list(request):
    """Public view for listing conferences"""
    active_conference = EltanConference.objects.filter(
        is_active=True,
        end_date__gte=timezone.now().date()
    ).first()
    
    past_conferences = EltanConference.objects.filter(
        end_date__lt=timezone.now().date()
    )[:5]
    
    context = {
        'active_conference': active_conference,
        'past_conferences': past_conferences,
    }
    return render(request, 'membership/conference_list.html', context)

def conference_detail(request, pk):
    """Public view for conference details"""
    conference = get_object_or_404(EltanConference, pk=pk)
    is_registered = False
    registration = None
    
    if request.user.is_authenticated:
        registration = EltanConferenceRegistration.objects.filter(
            conference=conference,
            user=request.user
        ).first()
        is_registered = registration is not None
    
    context = {
        'conference': conference,
        'is_registered': is_registered,
        'registration': registration,
    }
    return render(request, 'membership/conference_detail.html', context)



def conference_register(request, pk):
    conference = get_object_or_404(EltanConference, pk=pk)
    
    # Determine default registration type
    registration_type = 'non_member'

    # Check if 'type' is passed in the URL (for international registrations)
    if request.GET.get('type') == 'international':
        registration_type = 'non_member2'  # Set as international
    
    # Adjust registration type if user is authenticated and subscribed
    if request.user.is_authenticated and hasattr(request.user, 'is_subscribed'):
        if request.user.is_subscribed:
            registration_type = 'member'

    if request.method == 'POST':
        form = ConferenceRegistrationForm(request.POST)
        if form.is_valid():
            is_presenting = form.cleaned_data['is_presenting']
            email = form.cleaned_data.get('email') or ''
            first_name = form.cleaned_data.get('first_name') or ''
            last_name = form.cleaned_data.get('last_name') or ''
            phone = form.cleaned_data.get('phone') or ''

            # Fall back to authenticated user's profile data for missing fields
            if request.user.is_authenticated:
                if not email:
                    email = request.user.email
                if not first_name:
                    first_name = request.user.first_name
                if not last_name:
                    last_name = request.user.last_name

            if not email or '@' not in email:
                messages.error(request, "A valid email address is required to proceed.")
                return redirect('conference_register', pk=conference.pk)

            # Store form data in session for use after payment
            request.session['registration_data'] = {
                'is_presenting': is_presenting,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone,
                'registration_type': request.POST.get('registration_type', registration_type),
            }
            request.session.modified = True

            # Redirect to payment initiation
            return redirect('initiate_conference_registration', pk=conference.pk)
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {
                'email': request.user.email,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
            }
        form = ConferenceRegistrationForm(initial=initial)

    context = {
        'conference': conference,
        'form': form,
        'registration_type': registration_type,
        'is_early_bird': conference.is_early_bird_active
    }
    return render(request, 'membership/conference_register.html', context)




def initiate_conference_registration(request, pk):
    conference = get_object_or_404(EltanConference, pk=pk)
    registration_data = request.session.get('registration_data', {})
    
    
    # Log initial data
    logger.info(f"Starting registration with data: {registration_data}")
    
    try:
        # Validate required fields
        email = registration_data.get('email', '')
        logger.info(f"Email from registration data: {email}")
        
        if not email or '@' not in email:
            raise ValueError("Valid email address is required")

        # Get first_name and last_name
        first_name = registration_data.get('first_name', '')  
        last_name = registration_data.get('last_name', '')
        phone = registration_data.get('phone', '')
        
        logger.info(f"Processing registration for {email} ({first_name} {last_name})")
        
        # Calculate amount
        if registration_data.get('registration_type') == 'member':
            base_fee = conference.member_early_bird_fee if conference.is_early_bird_active else conference.member_fee
        elif registration_data.get('registration_type') == 'non_member2':
            base_fee = conference.international_delegate_fee
        else:
            base_fee = conference.non_member_early_bird_fee if conference.is_early_bird_active else conference.non_member_fee

            
        logger.info(f"Calculated base fee: {base_fee}")
        
        amount = base_fee.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
        if amount <= Decimal('0.00'):
            raise ValueError("Invalid fee configuration")
            
        logger.info(f"Final amount: {amount}")

        # Generate payment reference
        payment_reference = str(uuid.uuid4())
        
        # Create registration defaults
        registration_defaults = {
            'payment_reference': payment_reference,
            'amount_paid': amount,
            'payment_status': 'pending',
            'is_presenting': registration_data.get('is_presenting', False),
            'email': email,
            'phone':phone,
            'first_name': first_name,
            'last_name': last_name,
            'registration_type': registration_data.get('registration_type', 'non_member'),
        }
        
        logger.info(f"Registration defaults prepared: {registration_defaults}")

        try:
            if request.user.is_authenticated:
                registration, created = EltanConferenceRegistration.objects.update_or_create(
                    conference=conference,
                    user=request.user,
                    defaults=registration_defaults
                )
            else:
                registration, created = EltanConferenceRegistration.objects.update_or_create(
                    conference=conference,
                    email=email,
                    defaults=registration_defaults
                )
            logger.info(f"Registration {'created' if created else 'updated'} with ID: {registration.pk}")
        except Exception as e:
            logger.error(f"Database error creating registration: {str(e)}")
            raise

        # Prepare Paystack request
        success_url = request.build_absolute_uri(
            reverse('payment_success')
        )
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "email": email,
            "amount": int(amount * 100),
            "reference": payment_reference,
            "callback_url": success_url,
            "return_url": success_url,
            "reference": payment_reference,
            "currency": "NGN",
            "metadata": {
                "conference_id": conference.pk,
                "registration_id": registration.pk
            }
        }
        
        logger.info(f"Preparing Paystack request with payload: {payload}")

        # Initialize Paystack transaction
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        response_data = response.json()
        
        
        logger.info(f"Success URL: {success_url}")
        logger.info(f"Paystack response: {response_data}")
        
        return redirect(response_data['data']['authorization_url'])
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Paystack API Error: {str(e)}")
        try:
            logger.error(f"Paystack response body: {e.response.text if hasattr(e, 'response') and e.response is not None else 'N/A'}")
        except Exception:
            pass
        messages.error(request, "Payment service temporarily unavailable. Please try again.")
    except KeyError as e:
        logger.error(f"Missing key in Paystack response: {str(e)}")
        messages.error(request, "Payment processing error. Please try again.")
    except ValueError as e:
        logger.error(f"Validation Error: {str(e)}")
        messages.error(request, str(e))
    except Exception as e:
        logger.critical(f"Unexpected Error: {type(e).__name__}: {str(e)}", exc_info=True)
        messages.error(request, "An unexpected error occurred. Please try again.")

    return redirect('conference_register', pk=pk)
    
############ SEnd Registration Email ####################    


def send_registration_receipt(registration):
    try:
        # Prepare email content
        context = {
            'registration': registration,
            'current_date': timezone.now(),
            'year': datetime.now().year
        }
        
        html_content = render_to_string(
            'emails/conference_receipt.html',
            context
        )
        
        # Create email
        subject = f'Registration Confirmation - {registration.conference.title}'
        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[registration.email],
            reply_to=[settings.DEFAULT_FROM_EMAIL],
        )
        email.content_subtype = 'html'
        
        # Send email
        email.send(fail_silently=False)
        logger.info(f"Registration receipt sent to {registration.email}")
        
    except Exception as e:
        logger.error(f"Failed to send registration receipt to {registration.email}: {str(e)}")
        raise


################## Payment Success views
@csrf_exempt
def payment_success(request):
    payment_ref = request.GET.get('reference') or request.POST.get('reference')
    internal_ref = request.GET.get('payment_ref') or payment_ref
    
    logger.info(f"Payment success called with payment_ref: {payment_ref}, internal_ref: {internal_ref}")
    
    try:
        # Try to find registration using both references
        registration = None
        if internal_ref:
            registration = EltanConferenceRegistration.objects.filter(
                payment_reference=internal_ref,
                payment_status='pending'
            ).first()
        
        if not registration and payment_ref:
            registration = EltanConferenceRegistration.objects.filter(
                payment_reference=payment_ref,
                payment_status='pending'
            ).first()
            
        if not registration:
            logger.error(f"Registration not found for refs - payment: {payment_ref}, internal: {internal_ref}")
            raise EltanConferenceRegistration.DoesNotExist()

        # Verify transaction with Paystack
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        verify_url = f"https://api.paystack.co/transaction/verify/{payment_ref}"
        
        logger.info(f"Verifying payment with Paystack: {verify_url}")
        response = requests.get(verify_url, headers=headers)
        response.raise_for_status()
        verification = response.json()
        logger.info(f"Paystack verification response: {verification}")

        # Validate payment details
        if verification['data']['status'] != 'success':
            logger.error(f"Payment not successful: {verification['data']['status']}")
            raise ValueError("Payment not successful")

        received_amount = verification['data']['amount']
        expected_amount = int(registration.amount_paid * 100)
        if received_amount != expected_amount:
            logger.error(f"Amount mismatch: received {received_amount}, expected {expected_amount}")
            raise ValueError(f"Amount mismatch: received {received_amount}, expected {expected_amount}")

        received_email = verification['data']['customer']['email']
        if received_email.lower() != registration.email.lower():
            logger.error(f"Email mismatch: received {received_email}, registration {registration.email}")
            raise ValueError(f"Email mismatch: {received_email} vs {registration.email}")

        # Update registration
        registration.payment_status = 'completed'
        registration.paystack_reference = payment_ref
        registration.payment_verified_at = timezone.now()
        registration.save()
            
        logger.info(f"Registration {registration.id} payment completed successfully")

        # Clear session data
        if 'registration_data' in request.session:
            del request.session['registration_data']
        
        try:
            send_registration_receipt(registration)
            logger.info(f"Registration receipt sent to {registration.email}")
        except Exception as e:
            logger.error(f"Failed to send registration receipt: {str(e)}")
            # Don't raise the error as payment is already successful

        messages.success(request, "Registration payment completed successfully!")
        return render(request, 'membership/payment_success.html', {
            'registration': registration,
            'conference': registration.conference
        })

    except EltanConferenceRegistration.DoesNotExist:
        logger.error(f"Registration not found. Payment ref: {payment_ref}, Internal ref: {internal_ref}")
        messages.error(request, "Invalid registration reference")
    except requests.exceptions.RequestException as e:
        logger.error(f"Paystack verification failed: {str(e)}")
        messages.error(request, "Payment verification failed")
    except ValueError as e:
        logger.error(f"Payment validation error: {str(e)}")
        messages.error(request, str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in payment processing: {str(e)}", exc_info=True)
        messages.error(request, "An unexpected error occurred while processing your payment")

    return redirect('conference_list')
    

    

@csrf_exempt
def paystack_webhook(request):
    if request.method == 'POST':
        payload = request.body
        signature = request.headers.get('x-paystack-signature')
        
        # Verify signature
        computed_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            payload,
            digestmod=hashlib.sha512
        ).hexdigest()

        if not hmac.compare_digest(computed_signature, signature):
            return HttpResponse(status=400)

        try:
            event = json.loads(payload)
            if event['event'] == 'charge.success':
                data = event['data']
                reference = data['metadata']['internal_ref']
                
                registration = EltanConferenceRegistration.objects.get(
                    payment_reference=reference,
                    payment_status='pending'
                )
                
                # Validate and update registration
                if data['amount'] == int(registration.amount_paid * 100):
                    registration.payment_status = 'completed'
                    registration.paystack_reference = data['reference']
                    registration.save()
                    logger.info(f"Webhook updated registration: {reference}")

        except json.JSONDecodeError:
            logger.error("Invalid JSON payload")
        except KeyError as e:
            logger.error(f"Missing key in webhook payload: {str(e)}")
        except EltanConferenceRegistration.DoesNotExist:
            logger.error(f"Webhook registration not found: {reference}")
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")

        return HttpResponse(status=200)
    return HttpResponse(status=405)


###### End Registration Init #####



@login_required
def registration_detail(request, pk):
    """View for showing registration details and payment status"""
    registration = get_object_or_404(EltanConferenceRegistration, pk=pk, user=request.user)
    
    context = {
        'registration': registration,
    }
    return render(request, 'membership/registration_detail.html', context)



@login_required
def my_conferences(request):
    """View for users to see their conference registrations"""
    registrations = EltanConferenceRegistration.objects.filter(user=request.user)
    
    context = {
        'registrations': registrations,
    }
    return render(request, 'membership/my_conferences.html', context)
    


@login_required
def register_for_conference(request, conference_id):
    conference = EltanConference.objects.get(pk=conference_id)
    ConferenceRegistration.objects.create(user=request.user, conference=conference)
    return redirect('my_conf')

@login_required
def user_conferences(request):
    conferences = EltanConference.objects.all()
    user_conferences = EltanConferenceRegistration.objects.filter(user=request.user)
    return render(request, 'membership/my_conferences.html', {'user_conferences': user_conferences, 'conferences': conferences})
    
    
###### Conference Page

def conference_page(request, pk):
    # Be resilient if DB migrations for new fields aren't applied yet
    try:
        conference = get_object_or_404(EltanConference, pk=pk)
        sub_themes = getattr(conference, 'sub_themes', None)
        cfp_guidelines = getattr(conference, 'cfp_guidelines', None)
        sponsor_packages = getattr(conference, 'sponsor_packages', None)
        contact_name = getattr(conference, 'contact_name', '')
        contact_email = getattr(conference, 'contact_email', '')
        contact_phone = getattr(conference, 'contact_phone', '')
        abstract_form_link = getattr(conference, 'abstract_form_link', None)
        loc_members = getattr(conference, 'loc_members', None)
        loc_qs = loc_members.all() if loc_members is not None else []
    except DBOperationalError:
        # Fallback: load only legacy fields to avoid "no such column" errors
        conference = EltanConference.objects.only(
            'id', 'title', 'theme', 'image', 'start_date', 'end_date', 'venue',
            'member_fee', 'member_early_bird_fee', 'non_member_fee',
            'non_member_early_bird_fee', 'international_delegate_fee',
            'registration_start', 'registration_end', 'early_bird_end', 'is_active', 'description'
        ).get(pk=pk)
        sub_themes = None
        cfp_guidelines = None
        sponsor_packages = None
        contact_name = ''
        contact_email = ''
        contact_phone = ''
        abstract_form_link = None
        loc_qs = []

    from .models import ConferenceDocument, SponsorshipPackage, ConferenceAccommodation
    context = {
        'conference': conference,
        'speakers': conference.speakers.all() if hasattr(conference, 'speakers') else [],
        'sponsors': conference.sponsors.all() if hasattr(conference, 'sponsors') else [],
        'schedule': conference.schedule.all() if hasattr(conference, 'schedule') else [],
        'abstract_form_link': abstract_form_link or 'https://forms.gle/26eaEr4b1Zm7C9pb6',
        'loc_members': loc_qs,
        'accommodations': ConferenceAccommodation.objects.filter(conference=conference).order_by('order', 'name'),
        'documents': ConferenceDocument.objects.filter(conference=conference, is_public=True).order_by('-uploaded_at'),
        'sub_themes': sub_themes,
        'cfp_guidelines': cfp_guidelines,
        'sponsor_packages': SponsorshipPackage.objects.filter(conference=conference).order_by('order'),
        'contact_name': contact_name,
        'contact_email': contact_email,
        'contact_phone': contact_phone,
    }
    return render(request, 'membership/conference_detail_modern.html', context)


def sponsor_application(request, pk):
    conference = get_object_or_404(EltanConference, pk=pk)

    if request.method == 'POST':
        form = SponsorApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            sponsor = form.save(commit=False)
            sponsor.conference = conference
            sponsor.save()
            messages.success(request, 'Your sponsorship application has been submitted successfully.')
            return redirect('conference_detail', pk=pk)
    else:
        level = request.GET.get('level', '')
        initial = {'level': level} if level else {}
        form = SponsorApplicationForm(initial=initial)

    return render(request, 'membership/sponsor_form.html', {
        'form': form,
        'conference': conference,
    })


#-------- End of conference components ------------------------


#----------  My CPDs Views --------------------------
@login_required
def my_cpds(request):
    context = {}
    return render(request, 'membership/my_cpds.html', context)




# ----------- User Update Views -------------------
@login_required
def profile_update(request):
    if request.method == 'POST':
        form = MemberProfileUpdateForm(request.POST, request.FILES, instance=request.user.memberprofile)
        if form.is_valid():
            form.save()
            return redirect('profile_update_success')
    else:
        form = MemberProfileUpdateForm(instance=request.user.memberprofile)
    context = {'form': form}
    return render(request,'membership/update_profile.html', context)


@login_required
def profile_update_success(request):
    return render(request,'membership/profile_update_success.html')

# ----------- Download Certificate Views -------------------
@login_required
def view_certs(request):
    return render(request,'membership/my_certs.html')


def makeQRcode(url):
    qr = qrcode.make(url)
    name = "m.jpg"
    qr.save(path_qr + name)

@login_required
def generate_certs(request, subscription_id):
    # Get the subscription
    subscription = get_object_or_404(Subscription, id=subscription_id, user=request.user)
    
    # Get ELTAN year with fallback
    eltan_year = get_subscription_eltan_year(subscription)
    safe_year = eltan_year.replace('/', '_') 
    
    # Generate QR code for certificate verification
    code_url = request.build_absolute_uri(f'/verify-certificate/{subscription.id}/')
    qr = qrcode.make(code_url)
    
    # Define where to save the QR code images
    qr_code_dir = os.path.join('static', 'images', 'qrcodes')
    os.makedirs(qr_code_dir, exist_ok=True)
    
    # Save the QR code image
    qr_code_filename = f'qr_{subscription.user.eltan_number}_{safe_year}.png'
    qr_code_path = os.path.join(qr_code_dir, qr_code_filename)
    qr.save(qr_code_path)
    
    # Render Certificate Template
    template_path = 'membership/cert_template.html'
    context = {
        'member': subscription.user,
        'eltan_year': eltan_year,  # Using the fetched year
        'qr_code_path': qr_code_path,
    }
    
    template = get_template(template_path)
    html = template.render(context)

    # Generate PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ELTAN_Certificate_{safe_year}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Failed to generate the certificate. Please try again.', status=500)

    # Save certificate record to database (create if doesn't exist, update if exists)
    try:
        from django.core.files.base import ContentFile

        # Get or create the certificate record
        certificate, created = Certificate.objects.get_or_create(subscription=subscription)

        # Save the PDF content to the certificate's pdf_file field
        pdf_filename = f'ELTAN_Certificate_{subscription.user.eltan_number}_{safe_year}.pdf'
        certificate.pdf_file.save(pdf_filename, ContentFile(response.content), save=True)

    except Exception as e:
        # Log the error but don't fail the download
        print(f"Error saving certificate record: {e}")

    return response




@login_required
def list_certificates(request):
    current_date = timezone.now().date()

    # Get all subscriptions for the current user
    subscriptions = Subscription.objects.filter(
        user=request.user
    ).order_by('-eltan_year')

    # Find current subscription based on active date and paid status
    current_subscription = subscriptions.filter(
        start_date__lte=current_date,
        end_date__gte=current_date,
        payment_status='paid'
    ).first()

    # Past subscriptions are all others
    if current_subscription:
        past_subscriptions = subscriptions.exclude(id=current_subscription.id)
    else:
        past_subscriptions = subscriptions

    # Determine current ELTAN year based on date
    current_eltan_year = ELTANYearSetting.objects.filter(
        start_date__lte=current_date,
        end_date__gte=current_date
    ).first()

    # Get ELTAN years within the past 5 years (including current year)
    if current_eltan_year:
        year_range = ELTANYearSetting.objects.filter(
            start_date__lte=current_eltan_year.end_date
        ).order_by('-start_date')[:5]
    else:
        year_range = ELTANYearSetting.objects.all().order_by('-start_date')[:5]

    # Get all ELTAN years the user already subscribed to
    user_years = set(subscriptions.values_list('eltan_year', flat=True))

    # Identify ELTAN years the user has not subscribed to
    missing_eltan_years = [y for y in year_range if y.eltan_year not in user_years]

    context = {
        'current_subscription': current_subscription,
        'past_subscriptions': past_subscriptions,
        'missing_eltan_years': missing_eltan_years,  # These are ELTANYearSetting objects
    }

    return render(request, 'membership/list_certificates.html', context)

    


def verify_certificate(request, subscription_id):
    try:
        # Get the subscription
        subscription = get_object_or_404(Subscription, id=subscription_id)
        
        # Get certificate details
        certificate = Certificate.objects.filter(subscription=subscription).first()
        
        context = {
            'is_valid': True,
            'member_name': f"{subscription.user.first_name} {subscription.user.last_name}",
            'eltan_number': subscription.user.eltan_number,
            'eltan_year': subscription.eltan_year,
            'issue_date': certificate.generated_date if certificate else None,
            'subscription': subscription,
        }
        
        return render(request, 'membership/verify_certificate.html', context)
        
    except Http404:
        context = {
            'is_valid': False,
            'error_message': 'Certificate not found or invalid.'
        }
        return render(request, 'membership/verify_certificate.html', context)


# Event View
def events(request):
    today = timezone.now().date()

    # Get all events
    events = Events.objects.all()

    # Get upcoming/ongoing conferences
    try:
        upcoming_conferences = EltanConference.objects.filter(
            end_date__gte=today,
            is_active=True
        ).order_by('start_date')
        conferences = list(upcoming_conferences)
    except DBOperationalError:
        upcoming_conferences = EltanConference.objects.only(
            'id', 'title', 'theme', 'image', 'start_date', 'end_date', 'venue',
            'registration_start', 'registration_end', 'early_bird_end',
            'member_fee', 'member_early_bird_fee', 'non_member_fee',
            'non_member_early_bird_fee', 'international_delegate_fee', 'is_active', 'created_at'
        ).filter(
            end_date__gte=today,
            is_active=True
        ).order_by('start_date')
        conferences = list(upcoming_conferences)

    # Get past conferences (most recent first)
    try:
        past_conferences = EltanConference.objects.filter(
            end_date__lt=today,
            is_active=True
        ).order_by('-start_date')[:10]  # Limit to 10 most recent past events
    except DBOperationalError:
        past_conferences = EltanConference.objects.only(
            'id', 'title', 'theme', 'image', 'start_date', 'end_date', 'venue', 'created_at'
        ).filter(
            end_date__lt=today,
            is_active=True
        ).order_by('-start_date')[:10]

    upcoming_events = Events.objects.filter(
        event_date__gte=today,
        is_published=True
    ).order_by('event_date')

    past_events = Events.objects.filter(
        event_date__lt=today,
        is_published=True
    ).order_by('-event_date')[:10]

    context = {
        'title': 'ELTAN - Events',
        'events': events,
        'conferences': conferences,
        'past_conferences': past_conferences,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'has_upcoming': conferences,
        'has_past': past_conferences.exists() if hasattr(past_conferences, 'exists') else bool(past_conferences)
    }
    return render(request, 'membership/events.html', context)


# News View
def news(request):
    news = News.objects.all()
    context = {'title': 'ELTAN - News', 'news': news}
    return render(request, 'membership/our_news.html', context)

def news_detail(request, id):
    story = News.objects.get(pk=id)
    context = {'story': story}
    return render(request, 'membership/news_detail.html', context)
    
    
def verifiedcert(request):
    return render(request, 'membership/verifiedcert.html')
    
    
################################################################
# # Download Recourses View
@csrf_exempt  # Use this to bypass CSRF token requirement for demonstration purposes only.
def download_resource(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id)
    if request.method == 'POST':
        form = DownloadForm(request.POST)
        if form.is_valid():
            download = form.save(commit=False)
            download.resource = resource
            download.save()
            
            # Redirect to the resource list with a message
            #messages.success(request, "The resource has been successfully downloaded.")
            #return redirect('resource')
            # Handle zip file download
            zip_file_path = resource.file.path  # Assuming the file is a zip
            response = HttpResponse(open(zip_file_path, 'rb'), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(zip_file_path)}"'
            return response
    else:
        form = DownloadForm()

    return render(request, 'download_page.html', {'form': form, 'resource': resource})



def resource_list(request):
    resources = Resource.objects.all()
    return render(request, 'membership/resource_list.html', {'resources': resources})
    
####### Newsletter

def newsletter_list(request):
    newsletters = Newsletter.objects.filter(is_published=True)
    years = newsletters.values_list('year', flat=True).distinct().order_by('-year')
    
    # Group newsletters by year
    newsletters_by_year = {}
    for year in years:
        newsletters_by_year[year] = newsletters.filter(year=year)
    
    context = {
        'newsletters_by_year': newsletters_by_year
    }
    return render(request, 'membership/newsletter_list.html', context)

def download_newsletter(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk, is_published=True)
    response = FileResponse(newsletter.pdf_file, as_attachment=True)
    return response


################## Subscription Paystack Payment Views ##################

@login_required
def initiate_subscription_payment(request):
    """Initialize Paystack payment for subscription"""
    try:
        user = request.user
        email = user.email
        # Accept data either from session (old flow) or POST (direct modal submit)
        subscription_data = request.session.get('subscription_data')
        qualification_certificate = None

        if not subscription_data and request.method == 'POST':
            membership_type = request.POST.get('membership_type')
            state_chapter = request.POST.get('state_chapter')
            eltan_year = request.POST.get('eltan_year')
            qualification_certificate = request.FILES.get('qualification_certificate')

            if not (membership_type and state_chapter and eltan_year):
                messages.error(request, 'Please complete the form before proceeding to payment.')
                return redirect('subscribe')
            # Determine amount
            amount = 5500 if 'New Membership' in membership_type else 3000
            subscription_data = {
                'membership_type': membership_type,
                'state_chapter': state_chapter,
                'eltan_year': eltan_year,
                'payment_amount': amount,
            }
        elif subscription_data:
            amount = subscription_data['payment_amount']
        else:
            messages.error(request, "Session expired. Please try again.")
            return redirect('subscribe')

        # Generate payment reference
        payment_reference = f"SUB-{user.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        # Create or update pending subscription
        defaults = {
            'membership_type': subscription_data['membership_type'],
            'state_chapter': subscription_data['state_chapter'],
            'payment_amount': amount,
            'payment_status': 'pending',
            'payment_id': payment_reference,
        }

        # Add qualification_certificate if provided
        if qualification_certificate:
            defaults['qualification_certificate'] = qualification_certificate

        subscription, created = Subscription.objects.update_or_create(
            user=user,
            eltan_year=subscription_data['eltan_year'],
            defaults=defaults
        )

        logger.info(f"Subscription {'created' if created else 'updated'} with ID: {subscription.pk}")

        # Prepare Paystack request
        success_url = request.build_absolute_uri(
            reverse('subscription_payment_success')
        )

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "email": email,
            "amount": int(amount * 100),  # Convert to kobo
            "reference": payment_reference,
            "callback_url": success_url,
            "currency": "NGN",
            "metadata": {
                "subscription_id": subscription.pk,
                "user_id": user.id,
                "membership_type": subscription_data['membership_type'],
                "eltan_year": subscription_data['eltan_year'],
            }
        }

        logger.info(f"Preparing Paystack request with payload: {payload}")

        # Initialize Paystack transaction
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        response_data = response.json()

        logger.info(f"Paystack response: {response_data}")

        return redirect(response_data['data']['authorization_url'])

    except requests.exceptions.RequestException as e:
        logger.error(f"Paystack API Error: {str(e)}")
        messages.error(request, "Payment service temporarily unavailable. Please try again later.")
    except KeyError as e:
        logger.error(f"Missing key in Paystack response: {str(e)}")
        messages.error(request, "Payment processing error. Please try again.")
    except Exception as e:
        logger.critical(f"Unexpected Error: {type(e).__name__}: {str(e)}")
        messages.error(request, "An unexpected error occurred. Please try again.")

    return redirect('subscribe')


@csrf_exempt
def subscription_payment_success(request):
    """Verify and process successful subscription payment"""
    payment_ref = request.GET.get('reference') or request.POST.get('reference')

    logger.info(f"Subscription payment success called with reference: {payment_ref}")

    try:
        # Find subscription using payment reference
        subscription = Subscription.objects.filter(
            payment_id=payment_ref,
            payment_status='pending'
        ).first()

        if not subscription:
            logger.error(f"Subscription not found for payment reference: {payment_ref}")
            messages.error(request, "Invalid payment reference")
            return redirect('subscribe')

        # Verify transaction with Paystack
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        verify_url = f"https://api.paystack.co/transaction/verify/{payment_ref}"

        logger.info(f"Verifying payment with Paystack: {verify_url}")
        response = requests.get(verify_url, headers=headers)
        response.raise_for_status()
        verification = response.json()
        logger.info(f"Paystack verification response: {verification}")

        # Validate payment details
        if verification['data']['status'] != 'success':
            logger.error(f"Payment not successful: {verification['data']['status']}")
            messages.error(request, "Payment verification failed")
            return redirect('subscribe')

        received_amount = verification['data']['amount']
        expected_amount = int(subscription.payment_amount * 100)
        if received_amount != expected_amount:
            logger.error(f"Amount mismatch: received {received_amount}, expected {expected_amount}")
            messages.error(request, f"Payment amount mismatch")
            return redirect('subscribe')

        # Update subscription
        subscription.payment_status = 'paid'
        subscription.payment_id = payment_ref
        subscription.save()

        # Update user subscription status
        user = subscription.user
        user.is_subscribed = True
        user.save()

        logger.info(f"Subscription {subscription.id} payment completed successfully")

        # Clear session data
        if 'subscription_data' in request.session:
            del request.session['subscription_data']

        messages.success(request, "Subscription payment completed successfully!")
        return redirect('subscribe_success')

    except Subscription.DoesNotExist:
        logger.error(f"Subscription not found for payment reference: {payment_ref}")
        messages.error(request, "Invalid subscription reference")
    except requests.exceptions.RequestException as e:
        logger.error(f"Paystack verification failed: {str(e)}")
        messages.error(request, "Payment verification failed. Please contact support.")
    except ValueError as e:
        logger.error(f"Payment validation error: {str(e)}")
        messages.error(request, str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in payment processing: {str(e)}", exc_info=True)
        messages.error(request, "An unexpected error occurred while processing your payment")

    return redirect('subscribe')
