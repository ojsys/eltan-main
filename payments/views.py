"""
Payment views for automated Paystack integration
"""

import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.urls import reverse
from .paystack import PaystackAPI, verify_payment_signature, initialize_membership_payment
from membership.enhanced_models import EnhancedSubscription, MembershipType

logger = logging.getLogger(__name__)


@login_required
def initiate_payment(request, subscription_id):
    """Initiate Paystack payment for membership subscription"""
    subscription = get_object_or_404(
        EnhancedSubscription, 
        id=subscription_id, 
        user=request.user
    )
    
    if subscription.payment_status == 'paid':
        messages.info(request, 'This subscription has already been paid for.')
        return redirect('membership:subscription-detail', subscription_id=subscription.id)
    
    try:
        success, response = initialize_membership_payment(subscription)
        
        if success:
            # Store authorization URL in session for redirect
            authorization_url = response.get('authorization_url')
            access_code = response.get('access_code')
            
            if authorization_url:
                # Update subscription with payment reference
                subscription.paystack_reference = response.get('reference', subscription.payment_reference)
                subscription.payment_status = 'processing'
                subscription.save()
                
                # Redirect to Paystack payment page
                return redirect(authorization_url)
            else:
                messages.error(request, 'Unable to initiate payment. Please try again.')
        else:
            error_message = response.get('message', 'Payment initialization failed')
            messages.error(request, f'Payment failed: {error_message}')
            
    except Exception as e:
        logger.error(f"Payment initiation error: {e}")
        messages.error(request, 'An error occurred while processing your payment. Please try again.')
    
    return redirect('membership:subscription-detail', subscription_id=subscription.id)


@require_GET
def payment_callback(request):
    """Handle Paystack payment callback"""
    reference = request.GET.get('reference')
    
    if not reference:
        messages.error(request, 'Invalid payment reference.')
        return redirect('dashboard')
    
    try:
        # Verify transaction with Paystack
        api = PaystackAPI()
        success, response = api.verify_transaction(reference)
        
        if success and response.get('status') == 'success':
            # Find subscription by reference
            try:
                subscription = EnhancedSubscription.objects.get(
                    payment_reference=reference
                )

                # Mark payment as received — certificate_status stays 'pending' until admin approves
                subscription.payment_status = 'paid'
                subscription.paystack_reference = reference
                subscription.save()

                messages.success(
                    request,
                    'Payment received! Your subscription will be activated once our team verifies your qualification certificate.'
                )

                return redirect('membership:payment-success', subscription_id=subscription.id)
                
            except EnhancedSubscription.DoesNotExist:
                messages.error(request, 'Invalid subscription reference.')
                return redirect('dashboard')
                
        else:
            # Payment failed or was cancelled
            messages.error(request, 'Payment verification failed. Please contact support if you were charged.')
            return redirect('dashboard')
            
    except Exception as e:
        logger.error(f"Payment callback error: {e}")
        messages.error(request, 'An error occurred while verifying your payment.')
        return redirect('dashboard')


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """Handle Paystack webhook notifications"""
    
    # Get signature from headers
    signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
    
    if not signature:
        logger.warning("Webhook received without signature")
        return HttpResponse(status=400)
    
    # Get raw body
    payload = request.body.decode('utf-8')
    
    # Verify signature
    if not verify_payment_signature(payload, signature):
        logger.warning("Invalid webhook signature")
        return HttpResponse(status=400)
    
    try:
        # Parse webhook data
        event_data = json.loads(payload)
        
        # Process webhook
        api = PaystackAPI()
        success = api.process_webhook(event_data)
        
        if success:
            logger.info(f"Webhook processed successfully: {event_data.get('event')}")
            return HttpResponse("OK", status=200)
        else:
            logger.error(f"Webhook processing failed: {event_data.get('event')}")
            return HttpResponse("Processing failed", status=400)
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        return HttpResponse("Invalid JSON", status=400)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return HttpResponse("Internal error", status=500)


@login_required
def payment_success(request, subscription_id):
    """Payment success page"""
    subscription = get_object_or_404(
        EnhancedSubscription,
        id=subscription_id,
        user=request.user,
        payment_status='paid'
    )
    
    context = {
        'subscription': subscription,
        'membership_type': subscription.membership_type,
        'eltan_number': subscription.eltan_number,
    }
    
    return render(request, 'payments/success.html', context)


@login_required
def payment_failed(request):
    """Payment failed page"""
    reference = request.GET.get('reference')
    
    context = {
        'reference': reference,
    }
    
    return render(request, 'payments/failed.html', context)


@login_required
def membership_checkout(request, membership_type_id):
    """Checkout page for membership subscription"""
    membership_type = get_object_or_404(MembershipType, id=membership_type_id, is_active=True)
    
    if request.method == 'POST':
        try:
            # Create subscription
            subscription = EnhancedSubscription.objects.create(
                user=request.user,
                membership_type=membership_type,
                payment_amount=membership_type.get_current_price(),
                start_date=timezone.now().date(),
                state_chapter=request.POST.get('state_chapter', '')
            )
            
            # Redirect to payment
            return redirect('payments:initiate-payment', subscription_id=subscription.id)
            
        except Exception as e:
            logger.error(f"Subscription creation error: {e}")
            messages.error(request, 'An error occurred. Please try again.')
    
    context = {
        'membership_type': membership_type,
        'current_price': membership_type.get_current_price(),
        'is_early_bird': membership_type.is_early_bird_active,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
    }
    
    return render(request, 'payments/checkout.html', context)


@method_decorator(login_required, name='dispatch')
class PaymentHistoryView(TemplateView):
    """View payment history for user"""
    template_name = 'payments/history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user's subscriptions with payment logs
        subscriptions = EnhancedSubscription.objects.filter(
            user=self.request.user
        ).select_related('membership_type').prefetch_related('payment_logs')
        
        context['subscriptions'] = subscriptions
        return context


@login_required
@require_POST
def retry_payment(request, subscription_id):
    """Retry failed payment"""
    subscription = get_object_or_404(
        EnhancedSubscription,
        id=subscription_id,
        user=request.user
    )
    
    if subscription.payment_status in ['paid', 'processing']:
        messages.info(request, 'Payment is already processed or in progress.')
        return redirect('membership:subscription-detail', subscription_id=subscription.id)
    
    # Reset payment status and retry
    subscription.payment_status = 'pending'
    subscription.save()
    
    return redirect('payments:initiate-payment', subscription_id=subscription.id)


@require_GET
def verify_payment_ajax(request):
    """AJAX endpoint to verify payment status"""
    reference = request.GET.get('reference')
    
    if not reference:
        return JsonResponse({'error': 'Reference required'}, status=400)
    
    try:
        api = PaystackAPI()
        success, response = api.verify_transaction(reference)
        
        return JsonResponse({
            'success': success,
            'status': response.get('status') if success else None,
            'data': response if success else None
        })
        
    except Exception as e:
        logger.error(f"AJAX payment verification error: {e}")
        return JsonResponse({'error': 'Verification failed'}, status=500)


@login_required
def subscription_invoice(request, subscription_id):
    """Generate invoice/receipt for subscription"""
    subscription = get_object_or_404(
        EnhancedSubscription,
        id=subscription_id,
        user=request.user,
        payment_status='paid'
    )
    
    context = {
        'subscription': subscription,
        'site_name': getattr(settings, 'SITE_NAME', 'ELTAN'),
        'invoice_date': subscription.payment_verified_at or subscription.created_at,
    }
    
    return render(request, 'payments/invoice.html', context)