from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from membership.models import MemberProfile

CustomUser = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    # Add phone number and state as additional fields (not part of CustomUser model)
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        label='Phone Number',
        widget=forms.TextInput(attrs={'placeholder': 'Enter your phone number'})
    )
    state = forms.ChoiceField(
        choices=MemberProfile.STATE_CHOICES,
        required=True,
        label='State Chapter',
        widget=forms.Select()
    )

    def __init__(self, *args, **kwargs):
        super(CustomUserCreationForm, self).__init__(*args, **kwargs)
        # Fetching the choices directly from the model field if they are predefined there
        gender_field = self.fields['gender']
        state_field = self.fields['state']

        # Filter out any empty choices and set the new choices to the widget
        non_empty_choices = [choice for choice in gender_field.choices if choice[0] != '']
        non_empty_state_choices = [choice for choice in state_field.choices if choice[0] != 'Select']

        gender_field.choices = non_empty_choices
        state_field.choices = non_empty_state_choices

    def clean_email(self):
        """Validate that the email is unique"""
        email = self.cleaned_data.get('email')
        if email and CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "A user with this email address already exists. "
                "Please use a different email or login to your existing account."
            )
        return email

    class Meta:
        model = CustomUser
        fields = ['email', 'first_name', 'last_name', 'gender', 'phone_number', 'state']


class CustomAuthenticationForm(AuthenticationForm):
    class Meta:
        model = CustomUser
        fields = ['email', 'password']


class MemberSignupForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(MemberSignupForm, self).__init__(*args, **kwargs)
        # Fetching the choices directly from the model field if they are predefined there
        gender_field = self.fields['gender']
        # Filter out any empty choices and set the new choices to the widget
        non_empty_choices = [choice for choice in gender_field.choices if choice[0] != '']
        gender_field.choices = non_empty_choices


    class Meta:
        model = MemberProfile
        fields = ['gender', 'phone_number', 'address', 'city','state', 'zip_code', 'country', 'date_of_birth', 'profile_pic']