from django import forms

from .models import EventQuestion


class RegistrationForm(forms.Form):
    """Who is coming. Members arrive with these filled in from their account."""

    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)


class ResendLinkForm(forms.Form):
    email = forms.EmailField(label='The email address you registered with')


class ActivityForm(forms.Form):
    """The post-event activity: the attendance code, then the event's own questions."""

    def __init__(self, *args, setup, questions, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = list(questions)
        if setup.attendance_code:
            self.fields['attendance_code'] = forms.CharField(
                max_length=40, label='Attendance code',
                help_text='The code announced during the session.',
            )
        for question in self.questions:
            self.fields[f'q{question.pk}'] = self._field_for(question)

    @staticmethod
    def _field_for(question):
        common = {'label': question.prompt, 'required': question.required}
        if question.kind == EventQuestion.RATING:
            return forms.ChoiceField(
                choices=[(str(n), str(n)) for n in range(1, 6)],
                widget=forms.RadioSelect, help_text='1 = not useful, 5 = very useful', **common,
            )
        if question.kind == EventQuestion.CHOICE:
            return forms.ChoiceField(
                choices=[(option, option) for option in question.choice_list],
                widget=forms.RadioSelect, **common,
            )
        if question.kind == EventQuestion.SHORT_TEXT:
            return forms.CharField(max_length=300, **common)
        return forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), max_length=4000, **common)

    def answers(self):
        return [
            (question, self.cleaned_data.get(f'q{question.pk}', '') or '')
            for question in self.questions
        ]

    @property
    def question_fields(self):
        return [self[f'q{question.pk}'] for question in self.questions]
