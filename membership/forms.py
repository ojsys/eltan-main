from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, Submit, Div
from .models import EltanConference, MemberProfile, Sigs, Subscription, Download, EltanConferenceRegistration, ConferenceSponsor

# class ConferenceRegistrationForm(forms.ModelForm):
#     class Meta:
#         model = EltanConferenceRegistration
#         fields = ['is_presenting', 'paper_title', 'paper_abstract', 'payment_proof']
#         widgets = {
#             'paper_abstract': forms.Textarea(attrs={'rows': 4}),
#         }

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields['paper_title'].required = False
#         self.fields['paper_abstract'].required = False
        
#         # Show paper details only if presenting
#         self.fields['paper_title'].widget.attrs['data-depends-on'] = 'is_presenting'
#         self.fields['paper_abstract'].widget.attrs['data-depends-on'] = 'is_presenting'


# class ConferenceRegistrationForm(forms.ModelForm):
#     email = forms.EmailField(required=False)
#     first_name = forms.CharField(max_length=100, required=False)
#     last_name = forms.CharField(max_length=100, required=False)
#     phone = forms.CharField(max_length=20, required=False)
    
    
#     class Meta:
#         model = EltanConferenceRegistration
#         fields = ['is_presenting', 'paper_title', 'paper_abstract']
#         widgets = {
#             'paper_abstract': forms.Textarea(attrs={'rows': 4}),
#         }
        
        
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.helper = FormHelper()
#         self.helper.form_method = 'post'
#         self.helper.form_class = 'form-horizontal'
#         self.helper.label_class = 'col-lg-2'
#         self.helper.field_class = 'col-lg-8'
        
#         self.helper.layout = Layout(
#             Div(
#                 Row(
#                     Column('first_name', css_class='form-group col-md-6 mb-0'),
#                     Column('last_name', css_class='form-group col-md-6 mb-0'),
#                     css_class='form-row'
#                 ),
#                 Row(
#                     Column('email', css_class='form-group col-md-6 mb-0'),
#                     Column('phone', css_class='form-group col-md-6 mb-0'),
#                     css_class='form-row'
#                 ),
#                 css_class='non-member-fields',
#                 css_id='non-member-section'
#             ),
#             Field('is_presenting', css_class='mb-3'),
#             Div(
#                 Field('paper_title', css_class='mb-3'),
#                 Field('paper_abstract', css_class='mb-3'),
#                 css_class='presenting-fields',
#                 css_id='presenting-section'
#             ),
            
#             Submit('submit', 'Proceed to Payment', css_class='btn btn-warning')
#         )


class ConferenceRegistrationForm(forms.ModelForm):
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=20, required=False)
    
    
    class Meta:
        model = EltanConferenceRegistration
        fields = ['is_presenting', 'email', 'first_name', 'last_name', 'phone']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_action = ''  # Will submit to same URL
        
        self.helper.layout = Layout(
            Field('is_presenting'),
            Field('email'),
            Field('first_name'),
            Field('last_name'),
            Field('phone'),
            Submit('submit', 'Proceed to Payment', 
                  css_class='btn btn-warning',
                  style="background-color: #E67918; border: none; color:white; padding: 10px;")
        )

class SponsorApplicationForm(forms.ModelForm):
    class Meta:
        model = ConferenceSponsor
        fields = ['company_name', 'contact_name', 'contact_email', 'contact_phone', 
                 'level', 'logo', 'website']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class MemberProfileUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(MemberProfileUpdateForm, self).__init__(*args, **kwargs)
        # Fetching the choices directly from the model field if they are predefined there
        gender_field = self.fields['gender']
        state_field = self.fields['state']
        # Filter out any empty choices and set the new choices to the widget
        non_empty_choices = [choice for choice in gender_field.choices if choice[0] != '']
        non_empty_choices2 = [item for item in state_field.choices if item[0]!= '']
        gender_field.choices = non_empty_choices
        state_field.choices = non_empty_choices2


    class Meta:
        model = MemberProfile
        fields = ['gender', 'phone_number', 'address', 'city', 'state', 'zip_code', 'country', 'date_of_birth', 'profile_pic']
        labels = {
            'gender': 'Select Gender',
            'phone_number': 'Phone Number', 
            'address': 'Enter Your Address', 
            'city': 'Current City', 
            'state': 'State Chapter', 
            'zip_code': 'Zip Code', 
            'country': 'Country', 
            'date_of_birth': 'Date of Birth', 
            'profile_pic': 'Upload Profile Picture'
        }
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }
            

class SigsForm(forms.ModelForm):
    class Meta:
        model = Sigs
        fields = "__all__"
        

class SubscriptionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(SubscriptionForm, self).__init__(*args, **kwargs)
        # Fetching the choices directly from the model field if they are predefined there
        membership_type_field = self.fields['membership_type']
        state_chapter_field = self.fields['state_chapter']
        
        # Filter out any empty choices and set the new choices to the widget
        non_empty_choices = [choice for choice in membership_type_field.choices if choice[0]!= '']
        non_empty_choices2 = [item for item in state_chapter_field.choices if item[0]!= '']
        membership_type_field.choices = non_empty_choices
        state_chapter_field.choices = non_empty_choices2
        
        # Set choices for eltan_year from ELTANYearSetting
        from .models import ELTANYearSetting  # Import at the top of the file instead
        eltan_years = ELTANYearSetting.objects.all()
        self.fields['eltan_year'].choices = [(year.eltan_year, year.eltan_year) for year in eltan_years]
    
    
    class Meta:
        model = Subscription
        #exclude = ('user', 'payment_id', 'payment_status', 'end_date', )
        #fields = "__all__"
        fields = ["membership_type", 'state_chapter', 'eltan_year', "qualification_certificate", "payment_proof"]
        labels = {
            "membership_type": "Membership Type",
            "state_chapter": "State Chapter",
            "eltan_year": "ELTAN Year",
            "qualification_certificate": "Teaching Qualification Certificate",
            "payment_proof": "Upload Proof"
        }
        
        
class DownloadForm(forms.ModelForm):
    class Meta:
        model = Download
        fields = ['name', 'email']