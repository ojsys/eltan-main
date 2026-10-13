from django import forms

from .models import MAX_EVIDENCE_BYTES, Achievement, PortfolioProfile


class AchievementForm(forms.ModelForm):
    class Meta:
        model = Achievement
        fields = ['title', 'category', 'provider', 'completed_on', 'cpd_hours',
                  'description', 'credential_url', 'evidence', 'is_public']
        widgets = {
            'completed_on': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_evidence(self):
        evidence = self.cleaned_data.get('evidence')
        if evidence and getattr(evidence, 'size', 0) > MAX_EVIDENCE_BYTES:
            raise forms.ValidationError('The file is larger than 5 MB. Please upload a smaller copy.')
        return evidence

    def clean_cpd_hours(self):
        hours = self.cleaned_data.get('cpd_hours')
        if hours is not None and hours < 0:
            raise forms.ValidationError('CPD hours cannot be negative.')
        return hours


class ProfileForm(forms.ModelForm):
    class Meta:
        model = PortfolioProfile
        fields = ['headline', 'bio', 'cpd_goal_hours']
        widgets = {'bio': forms.Textarea(attrs={'rows': 3})}
