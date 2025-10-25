from django.utils import timezone
from .models import ELTANYearSetting
from django.conf import settings


class Paystack:
    @staticmethod
    def verify_payment(reference):
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] and data['data']['status'] == 'success':
                return True, data
            return False, data
            
        except (requests.exceptions.RequestException, KeyError) as e:
            logger.error(f"Paystack verification failed: {str(e)}")
            return False, {'error': 'Verification failed'}


def get_current_eltan_year():
    """
    Get the current ELTAN year from settings or calculate it if not set.
    """
    # First try to get from settings
    current_setting = ELTANYearSetting.objects.filter(is_active=True).first()
    if current_setting:
        return current_setting.eltan_year
        
    # If no setting exists, calculate based on current date
    current_date = timezone.now()
    if current_date.month >= 9:  # New academic year starts in September
        return f"{current_date.year}/{current_date.year + 1}"
    return f"{current_date.year - 1}/{current_date.year}"

def get_subscription_eltan_year(subscription):
    """
    Get ELTAN year for a subscription, falling back to current year if not set.
    """
    if subscription.eltan_year:
        return subscription.eltan_year
    return get_current_eltan_year()