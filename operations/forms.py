from django import forms
from django.utils import timezone
from deliveries.models import Driver
from .models import DeliveryAttempt, DeliveryConfirmation


class DriverAssignmentForm(forms.Form):
    driver = forms.ModelChoiceField(
        queryset=Driver.objects.none(), required=False,
        empty_label="Unassigned", widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["driver"].queryset = Driver.objects.filter(is_active=True)


class ConfirmationForm(forms.ModelForm):
    class Meta:
        model = DeliveryConfirmation
        fields = ["received_by", "location", "note"]
        labels = {"received_by": "Name of person who received the shipment", "note": "Internal note (optional)"}
        widgets = {
            "received_by": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full name"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "Delivery location"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class AttemptForm(forms.ModelForm):
    class Meta:
        model = DeliveryAttempt
        fields = ["reason", "location", "internal_note", "next_attempt_on"]
        labels = {"internal_note": "Internal note (not public)", "next_attempt_on": "Next attempt date (optional)"}
        widgets = {
            "reason": forms.Select(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "Last known location"}),
            "internal_note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "next_attempt_on": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        }

    def clean_next_attempt_on(self):
        next_date = self.cleaned_data.get("next_attempt_on")
        if next_date and next_date < timezone.localdate():
            raise forms.ValidationError("The next attempt must be today or later.")
        return next_date
