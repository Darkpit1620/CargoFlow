from django import forms
from deliveries.models import Driver
from .models import ServiceRecord, Vehicle


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "registration", "make", "model_name", "kind", "status", "capacity_kg",
            "mileage_km", "assigned_driver", "last_service_date", "next_service_date", "notes",
        ]
        widgets = {
            "last_service_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "next_service_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_driver"].queryset = Driver.objects.filter(is_active=True).order_by("full_name")
        self.fields["assigned_driver"].required = False
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.HiddenInput)):
                field.widget.attrs["class"] = "form-control"

    def clean_registration(self):
        value = self.cleaned_data["registration"].strip().upper()
        existing = Vehicle.objects.filter(registration__iexact=value)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This registration number is already recorded.")
        return value


class ServiceRecordForm(forms.ModelForm):
    class Meta:
        model = ServiceRecord
        fields = ["service_date", "service_type", "description", "cost", "mileage_km", "next_due_date"]
        widgets = {
            "service_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "next_due_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
