from django import forms
from django.contrib.auth import get_user_model
from deliveries.models import Shipment
from .models import WorkTask


class WorkTaskForm(forms.ModelForm):
    class Meta:
        model = WorkTask
        fields = ["title", "description", "shipment", "assigned_to", "priority", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = get_user_model().objects.filter(
            is_staff=True, is_active=True,
        ).order_by("username")
        self.fields["shipment"].queryset = Shipment.objects.order_by("-created_at")
        self.fields["shipment"].label_from_instance = lambda obj: obj.tracking_number
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_title(self):
        value = self.cleaned_data["title"].strip()
        if not value:
            raise forms.ValidationError("Enter a task title.")
        return value


class WorkNoteForm(forms.Form):
    note = forms.CharField(max_length=1000, strip=True, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))
