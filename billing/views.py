"""Staff-facing manual invoicing and payment recording; no payment gateway."""
import csv
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from deliveries.models import Shipment
from deliveries.views import staff_required
from .forms import InvoiceForm, PaymentForm
from .models import Invoice, Payment


def safe_csv(value):
    content = str(value if value is not None else "")
    if content.lstrip().startswith(("=", "+", "-", "@")) or content.startswith(("\t", "\r", "\n")):
        return "'" + content
    return content


def filtered_invoices(request):
    query = request.GET.get("q", "").strip()[:100]
    qs = Invoice.objects.select_related("shipment", "issued_by")
    if query:
        qs = qs.filter(Q(invoice_number__icontains=query) | Q(shipment__tracking_number__icontains=query) |
                       Q(shipment__recipient_name__icontains=query))
    return qs, query


@staff_required
def invoice_list(request):
    qs, query = filtered_invoices(request)
    invoices = list(qs)
    # Values are computed from actual recorded payments, not shipment statuses.
    issued = sum((item.amount for item in invoices), Decimal("0.00"))
    paid = Payment.objects.filter(invoice__in=qs).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    return render(request, "billing/list.html", {
        "page_obj": Paginator(qs, 20).get_page(request.GET.get("page")),
        "query": query, "invoice_count": len(invoices), "issued": issued,
        "collected": paid, "outstanding": issued - paid,
    })


@staff_required
def invoice_create(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    existing = Invoice.objects.filter(shipment=shipment).first()
    if existing:
        return redirect("billing-detail", pk=existing.pk)
    if shipment.delivery_fee <= 0:
        messages.error(request, "Set a positive delivery fee before creating an invoice.")
        return redirect("shipment-detail", pk=pk)
    form = InvoiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        invoice = form.save(commit=False)
        invoice.shipment = shipment
        invoice.amount = shipment.delivery_fee  # Snapshot the agreed fee.
        invoice.issued_by = request.user
        try:
            with transaction.atomic():
                invoice.full_clean()
                invoice.save()
        except (IntegrityError, ValidationError):
            existing = Invoice.objects.filter(shipment=shipment).first()
            if existing:
                return redirect("billing-detail", pk=existing.pk)
            form.add_error(None, "Could not create invoice. Please retry.")
        else:
            messages.success(request, "Invoice created. No payment has been collected.")
            return redirect("billing-detail", pk=invoice.pk)
    return render(request, "billing/create.html", {"shipment": shipment, "form": form})


@staff_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("shipment", "issued_by"), pk=pk)
    return render(request, "billing/detail.html", {
        "invoice": invoice,
        "payments": invoice.payments.select_related("recorded_by"),
    })


@staff_required
def payment_create(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("shipment"), pk=pk)
    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
                payment = form.save(commit=False)
                payment.invoice = locked
                payment.recorded_by = request.user
                payment.full_clean()
                payment.save()
        except ValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, problems in exc.message_dict.items():
                    for problem in problems:
                        form.add_error(field if field in form.fields else None, problem)
            else:
                form.add_error(None, exc)
        except IntegrityError:
            form.add_error("reference", "Reference already recorded, or another payment changed the balance.")
        else:
            messages.success(request, "Payment recorded. Confirm receipt independently before recording transactions.")
            return redirect("billing-detail", pk=invoice.pk)
    return render(request, "billing/payment.html", {"invoice": invoice, "form": form})


@staff_required
def invoice_export(request):
    qs, _ = filtered_invoices(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="cargoflow_invoices.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Invoice", "Shipment", "Recipient", "Amount KES", "Paid KES", "Balance KES", "Status", "Due date", "Created"])
    for invoice in qs.iterator():
        paid = invoice.total_paid
        writer.writerow([safe_csv(invoice.invoice_number), safe_csv(invoice.shipment.tracking_number),
                         safe_csv(invoice.shipment.recipient_name), invoice.amount, paid,
                         max(Decimal("0.00"), invoice.amount - paid), invoice.payment_status,
                         invoice.due_date.isoformat(), invoice.created_at.date().isoformat()])
    return response
