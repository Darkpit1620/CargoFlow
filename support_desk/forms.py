from django import forms

from .models import SupportCase


class CaseCreateForm(forms.ModelForm):
    class Meta:
        model = SupportCase
        fields = ["category", "priority", "subject", "description", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean_subject(self):
        value = self.cleaned_data["subject"].strip()
        if not value:
            raise forms.ValidationError("Enter a subject for this issue.")
        return value

    def clean_description(self):
        value = self.cleaned_data["description"].strip()
        if not value:
            raise forms.ValidationError("Describe the issue.")
        return value


class CaseUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=SupportCase.Status.choices)
    note = forms.CharField(
        required=False, max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Private staff update (optional when changing status)"}),
    )

    def clean_note(self):
        return self.cleaned_data["note"].strip()
