from django import forms
from django.core.exceptions import ValidationError

from deliveries.models import Shipment
from .models import Warehouse, StorageBin, ParcelScan, ParcelPosition


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ['code', 'name', 'city', 'address', 'is_active']

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()


class StorageBinForm(forms.ModelForm):
    class Meta:
        model = StorageBin
        fields = ['warehouse', 'code', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['warehouse'].queryset = Warehouse.objects.filter(is_active=True)

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()


class ParcelScanForm(forms.Form):
    shipment = forms.ModelChoiceField(queryset=Shipment.objects.all(), label='Shipment tracking number')
    action = forms.ChoiceField(choices=ParcelScan.Action.choices)
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.none())
    bin = forms.ModelChoiceField(queryset=StorageBin.objects.none(), required=False)
    note = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['warehouse'].queryset = Warehouse.objects.filter(is_active=True)
        self.fields['bin'].queryset = StorageBin.objects.filter(is_active=True, warehouse__is_active=True).select_related('warehouse')

    def clean(self):
        data = super().clean()
        shipment = data.get('shipment')
        action = data.get('action')
        warehouse = data.get('warehouse')
        bin_obj = data.get('bin')
        if not (shipment and action and warehouse):
            return data
        if bin_obj and bin_obj.warehouse_id != warehouse.pk:
            self.add_error('bin', 'The bin must belong to the chosen warehouse.')
        if action == ParcelScan.Action.CHECK_OUT and bin_obj:
            self.add_error('bin', 'Leave the bin empty when checking a parcel out.')
        if action in (ParcelScan.Action.CHECK_IN, ParcelScan.Action.MOVE, ParcelScan.Action.HOLD):
            if shipment.status in (Shipment.Status.DELIVERED, Shipment.Status.CANCELLED):
                self.add_error('shipment', 'Delivered or cancelled shipments cannot be put in storage.')
        current = ParcelPosition.objects.filter(shipment=shipment).first()
        if action in (ParcelScan.Action.MOVE, ParcelScan.Action.HOLD, ParcelScan.Action.CHECK_OUT):
            if not current or current.state == ParcelPosition.State.RELEASED:
                self.add_error('action', 'Check this parcel in before moving, holding, or checking it out.')
        if action == ParcelScan.Action.CHECK_IN and current and current.state != ParcelPosition.State.RELEASED:
            self.add_error('action', 'Parcel is already in storage. Use Move / transfer instead.')
        if action == ParcelScan.Action.HOLD and current and current.state == ParcelPosition.State.HELD:
            self.add_error('action', 'Parcel is already on hold. Use Move / transfer to resume storage.')
        if action == ParcelScan.Action.CHECK_OUT and current and current.warehouse_id != warehouse.pk:
            self.add_error('warehouse', 'Select the parcel’s current warehouse for check-out.')
        return data
