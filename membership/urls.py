from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from . import views

urlpatterns = [
    # Make redesigned home the default landing page
    path('', views.home_redesigned, name='home'),
    # Keep both routes available
    path('new-home/', views.home_redesigned, name='home_redesigned'),  # New modern landing page
    path('classic-home/', views.index, name='home_classic'),           # Previous homepage
    path('dash/', views.dash, name='dash'),
    path('about/', views.about, name='about'),
    # SIGs (Special Interest Groups)
    path('sigs/', views.sigs, name='sigs'),
    path('sigs/<int:pk>/', views.sig_detail, name='sig_detail'),
    path('sigs/<int:pk>/join/', views.join_sig, name='join_sig'),
    path('sigs/<int:pk>/leave/', views.leave_sig, name='leave_sig'),
    path('add_sigs/', views.add_sigs, name='add_sig'),
    # Conference
    path('my_conf/<int:user_id>/', views.my_conferences, name='my_conf'),
    path('my_cpds/', views.my_cpds, name='my_cpds'),

    # Conference URLs
    path('conferences/', views.conference_list, name='conference_list'),
    path('conference/<int:pk>/', views.conference_page, name='conference_detail'),
    path('conference/<int:pk>/register/', views.conference_register, name='conference_register'),
    path('conference/registration/<int:pk>/', views.registration_detail, name='conference_registration_detail'),
    path('my-conferences/', views.my_conferences, name='my_conferences'),
    path('conference/<int:pk>/sponsor/', views.sponsor_application, name='sponsor_application'),
    
    ## Payment Links
    path('conference/<int:pk>/initiate-payment/', views.initiate_conference_registration, name='initiate_conference_registration'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('paystack/webhook/', views.paystack_webhook, name='paystack_webhook'),

    ## Staff conference payment verification
    path('staff/conference-verification/', views.conference_verification, name='conference_verification'),
    path('staff/conference-verification/<int:pk>/confirm/', views.confirm_conference_payment, name='confirm_conference_payment'),
    path('staff/conference-verification/<int:pk>/reject/', views.reject_conference_payment, name='reject_conference_payment'),
    path('staff/conference-verification/<int:pk>/send-ticket/', views.resend_conference_ticket, name='resend_conference_ticket'),
    path('staff/conference-verification/send-tickets/', views.send_conference_tickets, name='send_conference_tickets'),

    #Update Profile
    path('profile/update/', views.profile_update, name='profile_update'),
    path('profile/update/success/', views.profile_update_success, name='profile_update_success'),

    #Download Certificate
    path('download_certificate/my_certs', views.view_certs, name='my_certs'),
    path('download_certificate/certificate', views.generate_certs, name='download_certificate'),

    # Events Route
    path('events/', views.events, name='events'),

    # News Route
    path('news/', views.news, name='news'),
    path('news/<int:id>/', views.news_detail, name='news_detail'),

    #Summernote
    #path('summernote/', include('django_summernote.urls')),
    path('subscribe/', views.subscription, name='subscribe'),
    path('subscribe_success/', views.subscribe_success, name='subscribe_success'),
    path('subscription_pending/', views.subscribe_pending, name='subscription_pending'),
    path('subscribe/<slug:eltan_year>/', views.subscribe_past_year, name='subscribe_past_year'),
    path('subscribe-past-year/<str:eltan_year>/', views.subscribe_past_year, name='subscribe_past_year'),
    path('complete-subscription-payment/<int:subscription_id>/', views.complete_subscription_payment, name='complete_subscription_payment'),

    # Subscription Paystack Payment URLs
    path('subscription/initiate-payment/', views.initiate_subscription_payment, name='initiate_subscription_payment'),
    path('subscription/payment/success/', views.subscription_payment_success, name='subscription_payment_success'),
    
    path('download_certificate/download_certificate/certificate/', views.verifiedcert, name='verifiedcert'),
    
    path('resources/', views.resource_list, name='resource'),
    path('download/<int:resource_id>/', views.download_resource, name='download-resource'),
    
    path('certificates/', views.list_certificates, name='list_certificates'),
    path('certificate/generate/<int:subscription_id>/', views.generate_certs, name='generate_certificate'),
    path('certificate/generate/', views.generate_certs, name='generate_current_certificate'),
    path('verify-certificate/<int:subscription_id>/', views.verify_certificate, name='verify_certificate'),
    
    ### Newsletter
    path('newsletters/', views.newsletter_list, name='newsletter_list'),
    path('newsletters/download/<int:pk>/', views.download_newsletter, name='download_newsletter'),
    

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
