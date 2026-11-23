from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Driver, Shipment, TrackingEvent
from .serializers import DriverSerializer, ShipmentSerializer, TrackingEventSerializer


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    return Response({"project": "CargoFlow", "status": "success", "message": "CargoFlow API is running successfully!"})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def public_tracking(request, tracking_number):
    shipment = get_object_or_404(Shipment, tracking_number__iexact=tracking_number.strip())
    return Response({
        "tracking_number": shipment.tracking_number,
        "status": shipment.status,
        "status_label": shipment.get_status_display(),
        "origin": shipment.origin,
        "destination": shipment.destination,
        "estimated_delivery": shipment.expected_delivery,
        "events": [
            {"status": event.status, "status_label": event.get_status_display(), "location": event.location, "created_at": event.created_at}
            for event in shipment.events.all()
        ],
    })


class ShipmentViewSet(viewsets.ModelViewSet):
    queryset = Shipment.objects.select_related("driver").all()
    serializer_class = ShipmentSerializer
    permission_classes = [permissions.IsAdminUser]


class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [permissions.IsAdminUser]


class TrackingEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TrackingEvent.objects.select_related("shipment").all()
    serializer_class = TrackingEventSerializer
    permission_classes = [permissions.IsAdminUser]
