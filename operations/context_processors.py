from .models import DeliveryAttempt, DeliveryConfirmation

def shipment_operations(request):
    """Provide proof/attempts to the existing staff shipment detail template."""
    match = getattr(request, "resolver_match", None)
    if not match or match.url_name != "shipment-detail":
        return {}
    # The detail template renders only for staff; do not query for anonymous users.
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_staff:
        return {}
    pk = match.kwargs.get("pk")
    return {
        "proof": DeliveryConfirmation.objects.filter(shipment_id=pk).select_related("confirmed_by").first(),
        "attempts": DeliveryAttempt.objects.filter(shipment_id=pk).select_related("recorded_by"),
    }
