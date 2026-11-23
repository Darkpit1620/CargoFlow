from rest_framework import serializers
from .models import Driver, Shipment, TrackingEvent


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = ["id", "full_name", "phone", "vehicle_registration", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class ShipmentSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source="driver.full_name", read_only=True, default=None)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    status_location = serializers.CharField(max_length=120, required=False, write_only=True, allow_blank=True)
    status_note = serializers.CharField(max_length=255, required=False, write_only=True, allow_blank=True)

    class Meta:
        model = Shipment
        fields = ["id", "tracking_number", "sender_name", "recipient_name", "recipient_phone", "recipient_email", "origin", "destination", "weight_kg", "delivery_fee", "driver", "driver_name", "status", "status_label", "status_location", "status_note", "expected_delivery", "delivered_at", "notes", "created_at", "updated_at"]
        read_only_fields = ["id", "tracking_number", "status_label", "driver_name", "delivered_at", "created_at", "updated_at"]

    def create(self, validated_data):
        location = validated_data.pop("status_location", "")
        note = validated_data.pop("status_note", "")
        request = self.context.get("request")
        shipment = Shipment.objects.create(created_by=request.user if request and request.user.is_authenticated else None, **validated_data)
        event = shipment.events.first()
        if event:
            event.updated_by = request.user if request and request.user.is_authenticated else None
            if location:
                event.location = location
            if note:
                event.note = note
            event.save(update_fields=["updated_by", "location", "note"])
        return shipment

    def update(self, instance, validated_data):
        location = validated_data.pop("status_location", "")
        note = validated_data.pop("status_note", "")
        old_status = instance.status
        shipment = super().update(instance, validated_data)
        if old_status != shipment.status:
            event = shipment.events.first()
            if event:
                request = self.context.get("request")
                event.updated_by = request.user if request and request.user.is_authenticated else None
                event.location = location
                event.note = note or "Status updated"
                event.save(update_fields=["updated_by", "location", "note"])
        return shipment


class TrackingEventSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    class Meta:
        model = TrackingEvent
        fields = ["id", "shipment", "status", "status_label", "location", "note", "created_at"]
        read_only_fields = fields
