from django import forms
from .models import Driver, Shipment


class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = ["sender_name", "recipient_name", "recipient_phone", "recipient_email", "origin", "destination", "weight_kg", "delivery_fee", "expected_delivery", "driver", "notes"]
        widgets = {
            "expected_delivery": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["driver"].queryset = Driver.objects.filter(is_active=True) | Driver.objects.filter(pk=getattr(self.instance, "driver_id", None))
        self.fields["driver"].queryset = self.fields["driver"].queryset.distinct()
        self.fields["driver"].required = False
        self.fields["expected_delivery"].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = ["full_name", "phone", "vehicle_registration", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")


class StatusForm(forms.Form):
    status = forms.ChoiceField(choices=Shipment.Status.choices, widget=forms.Select(attrs={"class": "form-control"}))
    location = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Nairobi hub"}))
    note = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional update"}))
