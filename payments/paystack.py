"""
Automated Paystack integration for ELTAN membership payments
"""

import requests
import json
import hmac
import hashlib
import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class PaystackAPI:
    """
    Comprehensive Paystack API integration with automated payment processing
    """
    
    def __init__(self):
        self.secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        self.public_key = getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
        self.base_url = 'https://api.paystack.co'
        
        if not self.secret_key:
            logger.error("Paystack secret key not configured")
            raise ValueError("Paystack secret key is required")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers with authorization"""
        return {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Tuple[bool, Dict]:
        """Make API request to Paystack"""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=data)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            result = response.json()
            
            return result.get('status', False), result.get('data', {})
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Paystack API request failed: {e}")
            return False, {'message': str(e)}
    
    def initialize_transaction(self, subscription) -> Tuple[bool, Dict]:
        """
        Initialize payment transaction for membership subscription
        """
        # Convert amount to kobo (Paystack uses kobo for NGN)
        amount_kobo = int(subscription.payment_amount * 100)
        
        data = {
            'email': subscription.user.email,
            'amount': amount_kobo,
            'currency': 'NGN',
            'reference': subscription.payment_reference,
            'callback_url': f"{settings.SITE_URL}/payments/callback/",
            'metadata': {
                'subscription_id': subscription.id,
                'user_id': subscription.user.id,
                'membership_type': subscription.membership_type.name,
                'eltan_number': subscription.eltan_number,
                'full_name': subscription.user.get_full_name(),
                'phone': getattr(subscription.user, 'phone', ''),
            },
            'channels': ['card', 'bank', 'ussd', 'qr', 'mobile_money', 'bank_transfer'],
        }
        
        success, response = self._make_request('POST', '/transaction/initialize', data)
        
        if success:
            logger.info(f"Payment initialized for subscription {subscription.id}: {response.get('reference')}")
            return True, response
        else:
            logger.error(f"Failed to initialize payment for subscription {subscription.id}: {response}")
            return False, response
    
    def verify_transaction(self, reference: str) -> Tuple[bool, Dict]:
        """
        Verify payment transaction
        """
        success, response = self._make_request('GET', f'/transaction/verify/{reference}')
        
        if success:
            logger.info(f"Transaction verified: {reference}")
            return True, response
        else:
            logger.error(f"Failed to verify transaction {reference}: {response}")
            return False, response
    
    def verify_webhook(self, payload: str, signature: str) -> bool:
        """
        Verify webhook signature from Paystack
        """
        expected_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def process_webhook(self, event_data: Dict) -> bool:
        """
        Process webhook event from Paystack
        """
        from membership.enhanced_models import EnhancedSubscription, PaymentLog
        
        event_type = event_data.get('event')
        data = event_data.get('data', {})
        reference = data.get('reference')
        
        if not reference:
            logger.error("No reference in webhook data")
            return False
        
        try:
            subscription = EnhancedSubscription.objects.get(payment_reference=reference)
        except EnhancedSubscription.DoesNotExist:
            logger.error(f"Subscription not found for reference: {reference}")
            return False
        
        # Log the payment event
        PaymentLog.objects.create(
            subscription=subscription,
            event_type=event_type,
            paystack_reference=reference,
            amount=Decimal(str(data.get('amount', 0))) / 100,  # Convert from kobo
            currency=data.get('currency', 'NGN'),
            status=data.get('status', ''),
            gateway_response=data.get('gateway_response', ''),
            raw_data=event_data
        )
        
        # Process different event types
        if event_type == 'charge.success':
            return self._handle_successful_payment(subscription, data)
        elif event_type == 'charge.failed':
            return self._handle_failed_payment(subscription, data)
        elif event_type == 'transfer.success':
            return self._handle_transfer_success(subscription, data)
        elif event_type == 'transfer.failed':
            return self._handle_transfer_failed(subscription, data)
        
        return True
    
    def _handle_successful_payment(self, subscription, payment_data: Dict) -> bool:
        """Handle successful payment"""
        try:
            # Update subscription
            subscription.payment_status = 'paid'
            subscription.membership_status = 'active'
            subscription.payment_verified = True
            subscription.payment_verified_at = timezone.now()
            subscription.paystack_reference = payment_data.get('reference')
            subscription.transaction_id = payment_data.get('id')
            subscription.save()
            
            # Send confirmation email
            self._send_payment_confirmation_email(subscription)
            
            # Generate certificate if needed
            self._generate_membership_certificate(subscription)
            
            logger.info(f"Payment processed successfully for subscription {subscription.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing successful payment: {e}")
            return False
    
    def _handle_failed_payment(self, subscription, payment_data: Dict) -> bool:
        """Handle failed payment"""
        try:
            subscription.payment_status = 'failed'
            subscription.save()
            
            # Send failure notification email
            self._send_payment_failure_email(subscription, payment_data.get('gateway_response', ''))
            
            logger.info(f"Payment failed for subscription {subscription.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing failed payment: {e}")
            return False
    
    def _handle_transfer_success(self, subscription, data: Dict) -> bool:
        """Handle successful bank transfer"""
        # Bank transfer logic if needed
        return True
    
    def _handle_transfer_failed(self, subscription, data: Dict) -> bool:
        """Handle failed bank transfer"""
        # Bank transfer failure logic if needed
        return True
    
    def _send_payment_confirmation_email(self, subscription):
        """Send payment confirmation email"""
        try:
            from core.models import EmailTemplate
            from django.core.mail import send_mail
            from django.template import Template, Context
            
            # Get email template
            template = EmailTemplate.objects.filter(
                template_type='payment_confirmation',
                is_active=True
            ).first()
            
            if not template:
                logger.warning("No payment confirmation email template found")
                return
            
            # Prepare context
            context = Context({
                'user_name': subscription.user.get_full_name() or subscription.user.username,
                'site_name': settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'ELTAN',
                'membership_type': subscription.membership_type.name,
                'eltan_number': subscription.eltan_number,
                'payment_amount': subscription.payment_amount,
                'expiry_date': subscription.end_date,
                'payment_reference': subscription.payment_reference,
            })
            
            # Render email content
            subject_template = Template(template.subject)
            content_template = Template(template.content)
            
            subject = subject_template.render(context)
            content = content_template.render(context)
            
            # Send email
            send_mail(
                subject=subject,
                message=content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[subscription.user.email],
                html_message=content,
                fail_silently=False
            )
            
            logger.info(f"Payment confirmation email sent to {subscription.user.email}")
            
        except Exception as e:
            logger.error(f"Failed to send payment confirmation email: {e}")
    
    def _send_payment_failure_email(self, subscription, reason: str):
        """Send payment failure notification email"""
        try:
            from django.core.mail import send_mail
            
            subject = f"Payment Failed - {subscription.membership_type.name} Membership"
            message = f"""
            Dear {subscription.user.get_full_name() or subscription.user.username},
            
            We're sorry to inform you that your payment for {subscription.membership_type.name} membership failed.
            
            Reference: {subscription.payment_reference}
            Amount: ₦{subscription.payment_amount:,.2f}
            Reason: {reason}
            
            Please try again or contact our support team for assistance.
            
            Best regards,
            ELTAN Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[subscription.user.email],
                fail_silently=False
            )
            
            logger.info(f"Payment failure email sent to {subscription.user.email}")
            
        except Exception as e:
            logger.error(f"Failed to send payment failure email: {e}")
    
    def _generate_membership_certificate(self, subscription):
        """Generate membership certificate"""
        try:
            if subscription.certificate_issued:
                return
            
            # Certificate generation logic here
            # This could involve PDF generation, database records, etc.
            subscription.certificate_issued = True
            subscription.certificate_issued_at = timezone.now()
            subscription.save()
            
            logger.info(f"Certificate generated for subscription {subscription.id}")
            
        except Exception as e:
            logger.error(f"Failed to generate certificate: {e}")
    
    def get_transaction_status(self, reference: str) -> Tuple[bool, Dict]:
        """Get current status of a transaction"""
        return self.verify_transaction(reference)
    
    def refund_transaction(self, transaction_id: str, amount: Optional[int] = None) -> Tuple[bool, Dict]:
        """
        Refund a transaction
        amount: amount in kobo, if None refunds full amount
        """
        data = {'transaction': transaction_id}
        if amount:
            data['amount'] = amount
        
        success, response = self._make_request('POST', '/refund', data)
        
        if success:
            logger.info(f"Refund initiated for transaction {transaction_id}")
        else:
            logger.error(f"Failed to initiate refund for transaction {transaction_id}: {response}")
        
        return success, response
    
    def list_transactions(self, per_page: int = 50, page: int = 1) -> Tuple[bool, Dict]:
        """List all transactions"""
        params = {
            'perPage': per_page,
            'page': page
        }
        
        return self._make_request('GET', '/transaction', params)
    
    def create_transfer_recipient(self, name: str, account_number: str, bank_code: str) -> Tuple[bool, Dict]:
        """Create transfer recipient for refunds"""
        data = {
            'type': 'nuban',
            'name': name,
            'account_number': account_number,
            'bank_code': bank_code,
            'currency': 'NGN'
        }
        
        return self._make_request('POST', '/transferrecipient', data)


# Utility functions
def verify_payment_signature(payload: str, signature: str) -> bool:
    """Standalone function to verify Paystack webhook signature"""
    api = PaystackAPI()
    return api.verify_webhook(payload, signature)


def initialize_membership_payment(subscription):
    """Initialize payment for membership subscription"""
    api = PaystackAPI()
    return api.initialize_transaction(subscription)


def process_payment_webhook(event_data: Dict) -> bool:
    """Process Paystack webhook event"""
    api = PaystackAPI()
    return api.process_webhook(event_data)