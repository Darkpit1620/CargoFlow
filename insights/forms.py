from datetime import timedelta

from django import forms
from django.utils import timezone


class ReportDateForm(forms.Form):
    start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start'), cleaned.get('end')
        if not start or not end:
            return cleaned
        if start > end:
            raise forms.ValidationError('Start date must be on or before end date.')
        if end - start > timedelta(days=365):
            raise forms.ValidationError('Choose a reporting period of 366 days or fewer.')
        if end > timezone.localdate():
            raise forms.ValidationError('End date cannot be in the future.')
        return cleaned
