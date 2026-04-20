from django.db import models
from datetime import timezone, date, datetime
from django.utils import timezone
from django.conf import settings
from ckeditor.fields import RichTextField
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from account.models import CustomUser
from dateutil.relativedelta import relativedelta


# class ELTANYearSetting(models.Model):
#     eltan_year = models.CharField(max_length=9)  # Format: 2023/2024
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         verbose_name = 'ELTAN Year Setting'
#         verbose_name_plural = 'ELTAN Year Settings'

#     def __str__(self):
#         return f"ELTAN Year: {self.eltan_year} ({'Active' if self.is_active else 'Inactive'})"

#     def clean(self):
#         # Ensure only one active year setting exists
#         if self.is_active:
#             active_settings = ELTANYearSetting.objects.filter(is_active=True)
#             if self.pk:
#                 active_settings = active_settings.exclude(pk=self.pk)
#             if active_settings.exists():
#                 raise ValidationError("There can only be one active ELTAN year setting.")

#     def save(self, *args, **kwargs):
#         self.full_clean()
#         super().save(*args, **kwargs)


class ELTANYearSetting(models.Model):
    eltan_year = models.CharField(max_length=20)
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.eltan_year



class MemberProfile(models.Model):
    GENDER_CHOICES = [
        ('select', 'Select Gender'),
        ('male', 'Male'),
        ('female', 'Female'),
    ]
    STATE_CHOICES = [
        ('Select', 'Select State'),
        ('FC', 'Abuja'),
        ('AB', 'Abia'),
        ('AD', 'Adamawa'),
        ('AK', 'Akwa Ibom'),
        ('AN', 'Anambra'),
        ('BA', 'Bauchi'),
        ('BY', 'Bayelsa'),
        ('BE', 'Benue'),
        ('BO', 'Borno'),
        ('CR', 'Cross River'),
        ('DE', 'Delta'),
        ('EB', 'Ebonyi'),
        ('ED', 'Edo'),
        ('EK', 'Ekiti'),
        ('EN', 'Enugu'),
        ('GO', 'Gombe'),
        ('IM', 'Imo'),
        ('JI', 'Jigawa'),
        ('KD', 'Kaduna'),
        ('KN', 'Kano'),
        ('KT', 'Katsina'),
        ('KE', 'Kebbi'),
        ('KO', 'Kogi'),
        ('KW', 'Kwara'),
        ('LA', 'Lagos'),
        ('NA', 'Nassarawa'),
        ('NI', 'Niger'),
        ('OG', 'Ogun'),
        ('ON', 'Ondo'),
        ('OS', 'Osun'),
        ('OY', 'Oyo'),
        ('PL', 'Plateau'),
        ('RI', 'Rivers'),
        ('SO', 'Sokoto'),
        ('TA', 'Taraba'),
        ('YO', 'Yobe'),
        ('ZA', 'Zamfara'),
        ]
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    address = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=50, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True, choices=STATE_CHOICES)
    zip_code = models.CharField(max_length=10, null=True, blank=True)
    country = models.CharField(max_length=50, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.first_name + ' ' + self.user.last_name

class MembershipType(models.Model):
    name = models.CharField(max_length=50, choices=(('New Membership (5,500)', 'New Membership (5,500)'), ('Renew Membership (3,000)', 'Renew Membership (3,000)')))
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)


class Subscription(models.Model):

    MEMBER_CHOICES = [
        ('select', 'Select Membership'),
        ('New Membership', 'New Membership (N5,500)'),
        ('Renew Membership', 'Renew Membership (N3,000)'),
    ]

    ELTANYEAR_CHOICES = [
        ('Select', 'Select Year'),
        ('2022-2023', '2022-2023'),
        ('2023-2024', '2023-2024'),
        ('2024-2025', '2024-2025'),
        ('2025-2026', '2025-2026'),
        ('2027-2028', '2027-2028'),
        ]

    STATE_CHOICES = [
        ('Select', 'Select State'),
        ('FCT', 'Abuja'),
        ('ABIA', 'Abia'),
        ('ADAMAWA', 'Adamawa'),
        ('AKWA IBOM', 'Akwa Ibom'),
        ('ANAMBRA', 'Anambra'),
        ('BAUCHI', 'Bauchi'),
        ('BAYELSA', 'Bayelsa'),
        ('BENUE', 'Benue'),
        ('BORNO', 'Borno'),
        ('CROSS RIVER', 'Cross River'),
        ('DELTA', 'Delta'),
        ('EBONYI', 'Ebonyi'),
        ('EDO', 'Edo'),
        ('EKITI', 'Ekiti'),
        ('ENUGU', 'Enugu'),
        ('GOOMBE', 'Gombe'),
        ('IMO', 'Imo'),
        ('JIGAWA', 'Jigawa'),
        ('KADUNA', 'Kaduna'),
        ('KANO', 'Kano'),
        ('KATSINA', 'Katsina'),
        ('KEBBI', 'Kebbi'),
        ('KOGI', 'Kogi'),
        ('KWARA', 'Kwara'),
        ('LAGOS', 'Lagos'),
        ('NASARAWA', 'Nasarawa'),
        ('NIGER', 'Niger'),
        ('OGUN', 'Ogun'),
        ('ONDO', 'Ondo'),
        ('OSUN', 'Osun'),
        ('OYO', 'Oyo'),
        ('PLATEAU', 'Plateau'),
        ('RIVERS', 'Rivers'),
        ('SOKOTO', 'Sokoto'),
        ('TARABA', 'Taraba'),
        ('YOBE', 'Yobe'),
        ('ZAMFARA', 'Zamfara'),
        ]

    PAYMENT_METHOD_CHOICES = [
        ('manual', 'Manual Payment (Bank Transfer)'),
        ('paystack', 'Online Payment (Paystack)'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    membership_type = models.CharField(max_length=50, default="New Membership (5,500)", choices=MEMBER_CHOICES)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)
    eltan_year = models.CharField(max_length=9, default='2024/2025', choices=ELTANYEAR_CHOICES)
    payment_status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=(('paid','paid'),('pending', 'pending'))
    )
    payment_id = models.CharField(max_length=255, blank=True, null=True)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    state_chapter = models.CharField(max_length=20, blank=True, null=True, choices=STATE_CHOICES)
    payment_proof = models.FileField(upload_to='payment_proof/', null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='manual', help_text="Payment method used for this subscription")
    paystack_reference = models.CharField(max_length=100, null=True, blank=True, help_text="Paystack transaction reference")
    qualification_certificate = models.FileField(upload_to='qualifications/', null=True, blank=True, help_text="Teaching qualification certificate for English language")

    def calculate_eltan_dates(self):
        """Calculate the correct ELTAN year dates based on registration date"""
        registration_date = self.start_date or date.today()
        current_year = registration_date.year

        # If registering before September, use current academic year
        # If registering after September, use next academic year
        if registration_date.month < 9:
            start_year = current_year - 1
            end_year = current_year
        else:
            start_year = current_year
            end_year = current_year + 1

        return {
            'end_date': date(end_year, 8, 31),
            'eltan_year': f"{start_year}/{end_year}"
        }

    def save(self, *args, **kwargs):
        if not self.pk or not self.end_date:  # Only on creation or if end_date not set
            dates = self.calculate_eltan_dates()
            self.end_date = dates['end_date']
            self.eltan_year = dates['eltan_year']

        super().save(*args, **kwargs)

    @property
    def is_active(self):
        today = timezone.now().date()
        return (
            self.payment_status == 'paid' and 
            self.start_date <= today <= self.end_date
        )

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.membership_type} - {self.eltan_year}"

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'



############ Cert Download Count ###########
class Certificate(models.Model):
    subscription = models.OneToOneField(Subscription, on_delete=models.CASCADE)
    generated_date = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(upload_to='certificates/')
    
    def __str__(self):
        return f"Certificate for {self.subscription.user.username} - {self.subscription.eltan_year}"
        
    class Meta:
        db_table = 'membership_certificate'






########### Conference Model
class Conference(models.Model):
    title = models.CharField(max_length=255)
    conf_date = models.DateField()
    location = models.CharField(max_length=100)
    image = models.ImageField(upload_to='conference_images/')

    def __str__(self):
        return self.title


class ConferenceRegistration(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE)
    registration_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-registration_date']
        verbose_name_plural = 'Conference Registrations'


    def __str__(self):
        return self.conference.title + " - " + self.user.first_name + "  " + self.user.last_name

       
class EltanConference(models.Model):
    title = models.CharField(max_length=200)
    theme = models.CharField(max_length=500)
    description = RichTextField()
    image = models.ImageField(upload_to='eltan_conference_images/', null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    venue = models.CharField(max_length=200)
    registration_start = models.DateField(default=timezone.now)
    registration_end = models.DateField()
    early_bird_end = models.DateField(null=True, blank=True)
    abstract_form_link = models.URLField(blank=True, null=True)
    contact_name = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    sub_themes = RichTextField(blank=True, help_text="List of sub-themes (HTML allowed)")
    cfp_guidelines = RichTextField(blank=True, help_text="Call for papers guidelines/content (HTML allowed)")
    sponsor_packages = RichTextField(
        blank=True,
        help_text="Sponsorship package tiers and benefits displayed on the Sponsors tab",
        default="""<h3>Sponsorship Categories</h3>
<p>ELTAN offers four sponsorship tiers, each with a tailored package of recognition and benefits. Your sponsorship will not only support the success of this event but also offer your organisation meaningful visibility and engagement with a key audience.</p>

<h4>1. Platinum Sponsor &ndash; &#8358;700,000 and above</h4>
<ul>
<li>Recognition as Platinum Sponsor in all event materials</li>
<li>Logo placement on all banners, posters, and digital promotions</li>
<li>Full-page advert in the conference programme</li>
<li>Speaking opportunity during the opening session</li>
<li>Exhibition booth in premium location</li>
<li>4 complimentary registrations</li>
<li>Social media recognition before, during, and after the event</li>
<li>Company materials included in participant bags</li>
</ul>

<h4>2. Gold Sponsor &ndash; &#8358;500,000 &ndash; &#8358;699,000</h4>
<ul>
<li>Recognition as Gold Sponsor in event materials</li>
<li>Logo on banners, posters, and digital promotions</li>
<li>Half-page advert in the programme</li>
<li>Exhibition booth</li>
<li>2 complimentary registrations</li>
<li>Social media shoutouts</li>
<li>Company materials included in participant bags</li>
</ul>

<h4>3. Silver Sponsor &ndash; &#8358;350,000 &ndash; &#8358;499,000</h4>
<ul>
<li>Recognition as Silver Sponsor</li>
<li>Logo on event website and select materials</li>
<li>Quarter-page advert in the programme</li>
<li>1 complimentary registration</li>
<li>Shared exhibition space</li>
<li>Mention on social media</li>
</ul>

<h4>4. Bronze Sponsor &ndash; &#8358;150,000 &ndash; &#8358;349,000</h4>
<ul>
<li>Name listed in the programme and on the website</li>
<li>Company materials displayed at registration</li>
<li>Mention during the closing session</li>
</ul>

<h3>In-Kind Sponsorship</h3>
<p>ELTAN warmly welcomes contributions in forms other than cash. In-kind sponsors receive benefits matched to the value of their contribution, which may include logo display, exhibition space, and formal acknowledgements. Acceptable in-kind contributions include:</p>
<ul>
<li>Conference materials (e.g., bags, notepads, pens)</li>
<li>Refreshments and catering</li>
<li>Technical support (AV equipment, printing, photography)</li>
</ul>
<p>Custom sponsorship packages are also available upon request. We are happy to design an arrangement that aligns with your organisation&rsquo;s specific goals and budget.</p>"""
    )
    
    # Different fee categories
    member_fee = models.DecimalField(max_digits=10, decimal_places=2)
    member_early_bird_fee = models.DecimalField(max_digits=10, decimal_places=2)
    non_member_fee = models.DecimalField(max_digits=10, decimal_places=2)
    non_member_early_bird_fee = models.DecimalField(max_digits=10, decimal_places=2)
    international_delegate_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    member_payment_link = models.URLField(null=True, blank=True, help_text="Paystack payment link for members")
    non_member_payment_link = models.URLField(null=True, blank=True, help_text="Paystack payment link for non-members")
    
    def get_fee_for_type(self, registration_type):
        if registration_type == 'member':
            return self.member_early_bird_fee if self.is_early_bird_active else self.member_fee
        return self.non_member_early_bird_fee if self.is_early_bird_active else self.non_member_fee
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'ELTAN Conference'
        verbose_name_plural = 'ELTAN Conferences'
    
    def __str__(self):
        return f"{self.title} ({self.start_date.year})"
    
    @property
    def is_open_for_registration(self):
        today = timezone.now().date()
        return self.registration_start <= today <= self.registration_end
    
    @property
    def is_early_bird_active(self):
        if not self.early_bird_end:
            return False
        return timezone.now().date() <= self.early_bird_end
        
        

class EltanConferenceRegistration(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    currency = models.CharField(max_length=3, default="NGN")
    conference = models.ForeignKey(EltanConference, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    registration_type = models.CharField(max_length=20, choices=[
        ('member', 'Member'),
        ('non_member', 'Non-Member (Nigeria)'),
        ('non_member2', 'Non-Member (International)'),
    ], default='non_member')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_proof = models.FileField(upload_to='conference_payments/', null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    paystack_ref = models.CharField(max_length=100, null=True, blank=True)  # Paystack's reference
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    registered_at = models.DateTimeField(auto_now_add=True)
    is_presenting = models.BooleanField(default=False)
    paper_title = models.CharField(max_length=500, blank=True, null=True)
    paper_abstract = models.TextField(blank=True, null=True)
    
    #fields for non-members
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    class Meta:
        unique_together = ['conference', 'user']
        ordering = ['-registered_at']
        verbose_name = 'Conference Registration'
        verbose_name_plural = 'Conference Registrations'
    
    def __str__(self):
        return f"{self.user} - {self.conference.title}"
        
    def get_amount(self):
        return self.amount
    
    def clean(self):
        if not self.user and not self.email:
            raise ValidationError("Either a registered user or a valid email is required.")

    # def clean(self):
    #     super().clean()
    
    #     # Ensure that conference is set before checking for duplicates
    #     if not self.conference:
    #         raise ValidationError("Conference is required for registration.")
    
    #     if not self.user:
    #         existing_registration = EltanConferenceRegistration.objects.filter(
    #             conference=self.conference, email=self.email
    #         ).exclude(id=self.id)
    
    #         if existing_registration.exists():
    #             raise ValidationError("This email has already been used for registration in this conference.")

    def is_payment_successful(self):
        return self.payment_status == 'completed'


class ConferenceDocument(models.Model):
    conference = models.ForeignKey(EltanConference, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    document = models.FileField(upload_to='conference_documents/', default="upload document")
    uploaded_at = models.DateTimeField(default=timezone.now)
    is_public = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.title} - {self.conference.title}"
 
###### More models for Conference #######

class ConferenceSpeaker(models.Model):
    conference = models.ForeignKey(EltanConference, on_delete=models.CASCADE, related_name='speakers')
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=200)  # e.g., "Keynote Speaker", "Guest Speaker"
    bio = RichTextField()
    image = models.ImageField(upload_to='conference_speakers/')
    presentation_title = models.CharField(max_length=300, blank=True)
    order = models.IntegerField(default=0)  # For controlling display order

    class Meta:
        ordering = ['order']
        
    def __str__(self):
        return self.name

class ConferenceSchedule(models.Model):
    conference = models.ForeignKey(EltanConference, on_delete=models.CASCADE, related_name='schedule')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    session_title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    speaker = models.ForeignKey(ConferenceSpeaker, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.CharField(max_length=200)  # e.g., "Main Hall", "Room A"

    class Meta:
        ordering = ['date', 'start_time']
        
    def __str__(self):
        return f'{self.session_title} - {self.speaker}'
        

class ConferenceSponsor(models.Model):
    SPONSOR_LEVELS = [
        ('platinum', 'Platinum'),
        ('gold', 'Gold'),
        ('silver', 'Silver'),
        ('bronze', 'Bronze'),
    ]
    
    conference = models.ForeignKey(EltanConference, on_delete=models.CASCADE, related_name='sponsors')
    company_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    level = models.CharField(max_length=20, choices=SPONSOR_LEVELS)
    logo = models.ImageField(upload_to='sponsor_logos/')
    website = models.URLField(blank=True)
    is_approved = models.BooleanField(default=False) 
 

    def __str__(self):
        return f'{self.company_name} - {self.contact_name}'

class ConferenceLocMember(models.Model):
    conference = models.ForeignKey(EltanConference, on_delete=models.CASCADE, related_name='loc_members')
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=200, help_text="Committee role e.g. Chair, Media, Technical")
    organization = models.CharField(max_length=300, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    image = models.ImageField(upload_to='conference_loc/', blank=True, null=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'LOC Member'
        verbose_name_plural = 'LOC Members'

    def __str__(self):
        return f"{self.name} - {self.role}"


###############Defining Executive Committee (Exco) Models#######################
class ExcoMember(models.Model):
    """Executive Committee Member - Current and Past Leadership"""

    POSITION_CHOICES = [
        ('president', 'President'),
        ('vice_president', 'National Vice President'),
        ('secretary', 'National Secretary'),
        ('assistant_secretary', 'Assistant National Secretary'),
        ('treasurer', 'Treasurer'),
        ('financial_secretary', 'Financial Secretary'),
        ('publicity_secretary', 'Publicity Secretary'),
        ('auditor', 'Auditor'),
        ('ex_officio', 'Ex-Officio'),
        ('legal_adviser', 'Legal Adviser'),
        ('provost', 'Provost'),
        ('other', 'Other Position'),
    ]

    # Link to existing user account (optional - some may not have accounts)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exco_positions',
        help_text="Link to existing ELTAN member account (optional)"
    )

    # Basic Information (required even if user is linked)
    full_name = models.CharField(
        max_length=200,
        help_text="Full name of the executive member"
    )
    position = models.CharField(
        max_length=50,
        choices=POSITION_CHOICES,
        help_text="Executive position/portfolio"
    )

    # Institution/Organization
    institution = models.CharField(
        max_length=300,
        blank=True,
        help_text="University, college, or organization"
    )

    # Contact Information
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    linkedin_url = models.URLField(
        blank=True,
        verbose_name="LinkedIn Profile",
        help_text="Full LinkedIn profile URL"
    )

    # Photo
    photo = models.ImageField(
        upload_to='exco_members/',
        blank=True,
        null=True,
        help_text="Professional headshot (recommended: 400x400px)"
    )

    # Bio (optional)
    bio = RichTextField(
        blank=True,
        help_text="Brief biography or professional background"
    )

    # Tenure Information
    start_date = models.DateField(
        help_text="Start date of this position"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date of position (leave blank for current members)"
    )

    # Status Management
    is_active = models.BooleanField(
        default=True,
        help_text="Show in Current Exco section"
    )
    is_archived = models.BooleanField(
        default=False,
        help_text="Moved to Past Exco (archived members)"
    )

    # Display Order
    order = models.IntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'position', 'full_name']
        verbose_name = 'Executive Committee Member'
        verbose_name_plural = 'Executive Committee Members'
        indexes = [
            models.Index(fields=['is_active', 'is_archived']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        status = "Current" if self.is_active and not self.is_archived else "Past"
        return f"{self.full_name} - {self.get_position_display()} ({status})"

    def get_display_name(self):
        """Returns the full_name entered by admin"""
        return self.full_name

    def get_email(self):
        """Returns email from user account or stored email"""
        if self.user and self.user.email:
            return self.user.email
        return self.email

    def get_photo_url(self):
        """Returns photo URL, falling back to user profile pic if available"""
        if self.photo:
            return self.photo.url
        if self.user:
            try:
                profile = self.user.memberprofile
                if profile.profile_pic:
                    return profile.profile_pic.url
            except:
                pass
        return None

    def clean(self):
        """Validation logic"""
        # If user is linked but no full_name provided, use user's name as default
        # Admin can override this by entering a custom full_name
        if self.user and not self.full_name:
            self.full_name = f"{self.user.first_name} {self.user.last_name}"

        # Validate that either user or full_name is provided
        if not self.user and not self.full_name:
            raise ValidationError("Either link a user account or provide a full name")

        # Validate date logic
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date")

        # Auto-archive logic: if end_date is in the past, should be archived
        if self.end_date and self.end_date < timezone.now().date():
            self.is_active = False
            # Note: is_archived remains manual for admin control

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


###############Defining SIGs Models#######################
class Sigs(models.Model):
    title = models.CharField(max_length=255)
    description = RichTextField()
    image = models.ImageField(upload_to='sig_images/', blank=True, null=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Material icon name for this SIG"
    )
    moderator = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_sigs',
        help_text="SIG moderator assigned by admin"
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['order', 'title']
        verbose_name_plural = 'Sigs'

    def __str__(self):
        return self.title

    @property
    def member_count(self):
        """Return the number of members in this SIG"""
        return self.memberships.count()

    def get_members(self):
        """Return all members of this SIG"""
        return CustomUser.objects.filter(sig_memberships__sig=self)

    def is_member(self, user):
        """Check if a user is a member of this SIG"""
        if not user.is_authenticated:
            return False
        return self.memberships.filter(user=user).exists()

class SigsRegistration(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sig_memberships')
    sig = models.ForeignKey(Sigs, on_delete=models.CASCADE, related_name='memberships')
    registration_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'sig']
        verbose_name = 'SIG Membership'
        verbose_name_plural = 'SIG Memberships'

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.sig.title}"


##################### Events Model ###################################
class Events(models.Model):
    event_title = models.CharField(max_length=255)
    event_date = models.DateField()
    event_end_date = models.DateField(null=True, blank=True)
    event_location = models.CharField(max_length=100)
    event_desc = RichTextField()
    event_image = models.ImageField(upload_to='event_images/', null=True, blank=True)

    # CMS Enhancements
    short_description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Brief description for event cards"
    )
    registration_link = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    capacity = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['-event_date']
        verbose_name_plural = 'Events'

    def __str__(self):
        return f"{self.event_title} - {self.event_date} - {self.event_location}"
    

##################### News Model ###################################
class News(models.Model):
    headline = models.CharField(max_length=255)
    author = models.CharField(max_length=60)
    date_added = models.DateTimeField(auto_now_add=True)
    short_desc = models.TextField(null=True, blank=True)
    content = RichTextField(null=True, blank=True)
    featured_img = models.ImageField(upload_to='news_images/', null=True, blank=True)

    # CMS Enhancements
    slug = models.SlugField(unique=True, blank=True)
    category = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('general', 'General'),
            ('announcement', 'Announcement'),
            ('event', 'Event'),
            ('member', 'Member News'),
        ]
    )
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    views_count = models.IntegerField(default=0)
    meta_description = models.CharField(max_length=160, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_added']
        verbose_name_plural = 'News'

    def __str__(self):
        return f"{self.headline} - {self.author} - {self.date_added}"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.headline)
        super().save(*args, **kwargs)
        
        
##################### Resources Model ###################################
class Resource(models.Model):
    CATEGORY_CHOICES = [
        ('guide', 'Guides & Manuals'),
        ('template', 'Templates'),
        ('report', 'Reports'),
        ('presentation', 'Presentations'),
        ('policy', 'Policies'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='other'
    )
    file = models.FileField(upload_to='resources/')
    thumbnail = models.ImageField(upload_to='resource_thumbnails/', blank=True, null=True)

    # CMS Enhancements
    is_public = models.BooleanField(
        default=True,
        help_text="If unchecked, only members can download"
    )
    is_featured = models.BooleanField(default=False)
    file_size = models.CharField(max_length=20, blank=True)
    download_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Resources'

    def __str__(self):
        return f"{self.title} - {self.category}"
    

class Download(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    download_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-download_date']
        verbose_name_plural = 'Downloads'

    def __str__(self):
        return f"{self.resource.title} - {self.name} - {self.email} - {self.download_date}"
        
        
############## Newsletter

class Newsletter(models.Model):
    MONTH_CHOICES = [
        ('01', 'January'),
        ('02', 'February'),
        ('03', 'March'),
        ('04', 'April'),
        ('05', 'May'),
        ('06', 'June'),
        ('07', 'July'),
        ('08', 'August'),
        ('09', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ]

    title = models.CharField(max_length=200)
    month = models.CharField(max_length=2, choices=MONTH_CHOICES)
    year = models.IntegerField()
    pdf_file = models.FileField(upload_to='newsletters/')
    upload_date = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to='newsletter_thumbnails/', blank=True, null=True)
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    file_size = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['-year', '-month']
        unique_together = ['month', 'year']
        verbose_name = 'Newsletter'
        verbose_name_plural = 'Newsletters'

    def __str__(self):
        return f"ELTAN Newsletter - {self.get_month_display()} {self.year}"

    @property
    def file_size(self):
        """Return file size in MB"""
        if self.pdf_file:
            try:
                # Check if file exists before accessing size
                if self.pdf_file.storage.exists(self.pdf_file.name):
                    return f"{self.pdf_file.size / 1048576:.2f} MB"
                else:
                    return "File not found"
            except (OSError, ValueError, AttributeError):
                return "Error reading file"
        return "No file"


























    
