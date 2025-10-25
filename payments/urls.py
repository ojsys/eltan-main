"""
URL patterns for payments app
"""

from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment initiation and processing
    path('initiate/<int:subscription_id>/', views.initiate_payment, name='initiate-payment'),
    path('callback/', views.payment_callback, name='callback'),
    path('webhook/', views.paystack_webhook, name='webhook'),
    
    # Payment results
    path('success/<int:subscription_id>/', views.payment_success, name='success'),
    path('failed/', views.payment_failed, name='failed'),
    
    # Membership checkout
    path('checkout/<int:membership_type_id>/', views.membership_checkout, name='checkout'),
    
    # Payment management
    path('history/', views.PaymentHistoryView.as_view(), name='history'),
    path('retry/<int:subscription_id>/', views.retry_payment, name='retry-payment'),
    path('invoice/<int:subscription_id>/', views.subscription_invoice, name='invoice'),
    
    # AJAX endpoints
    path('verify/', views.verify_payment_ajax, name='verify-ajax'),
]