from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Invoice, Payment


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["due_date", "notes"]
        widgets = {
            "due_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["due_date"].initial = timezone.localdate() + timedelta(days=14)
        for f in self.fields.values():
            f.widget.attrs["class"] = "form-control"


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "reference", "received_on", "notes"]
        widgets = {
            "received_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["received_on"].initial = timezone.localdate()
        for f in self.fields.values():
            f.widget.attrs["class"] = "form-control"
