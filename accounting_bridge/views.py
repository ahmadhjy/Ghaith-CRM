from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounting_bridge.forms import OpeningBalanceForm
from accounting_bridge.models import InvoiceSyncQueue, PartyOpeningBalance
from accounting_bridge.permissions import user_is_accountant
from accounting_bridge.services.invoices import approve_queue_item
from accounting_bridge.services.master_data import sync_client_from_lead


def _require_accountant(view_func):
    def wrapper(request, *args, **kwargs):
        if not user_is_accountant(request.user):
            messages.error(request, 'Accounting access is restricted to main accountant users.')
            return redirect('calendar')
        return view_func(request, *args, **kwargs)

    return login_required(wrapper)


@_require_accountant
def review_queue(request):
    status = request.GET.get('status') or InvoiceSyncQueue.Status.PENDING_REVIEW
    items = (
        InvoiceSyncQueue.objects.select_related('leadtask', 'leadtask__lead', 'leadtask__assigned_to', 'sales_invoice')
        .filter(status=status)
        .order_by('-created_at')
    )
    return render(
        request,
        'accounting_bridge/review_queue.html',
        {
            'items': items,
            'status': status,
            'status_choices': InvoiceSyncQueue.Status.choices,
        },
    )


@_require_accountant
def review_detail(request, queue_id):
    queue = get_object_or_404(
        InvoiceSyncQueue.objects.select_related('leadtask', 'leadtask__lead', 'sales_invoice'),
        pk=queue_id,
    )
    leadtask = queue.leadtask
    services = leadtask.service_set.all()
    client_link = getattr(leadtask.lead, 'accounting_client_link', None)
    return render(
        request,
        'accounting_bridge/review_detail.html',
        {
            'queue': queue,
            'leadtask': leadtask,
            'lead': leadtask.lead,
            'services': services,
            'client_link': client_link,
        },
    )


@require_POST
@_require_accountant
def review_approve(request, queue_id):
    queue = get_object_or_404(InvoiceSyncQueue, pk=queue_id)
    publish = request.POST.get('publish') == '1'
    invoice = approve_queue_item(queue, request.user, publish=publish)
    sync_client_from_lead(queue.leadtask.lead)
    if publish:
        messages.success(request, f'Invoice approved and published as {invoice.invoice_no}.')
    else:
        messages.success(request, f'Invoice approved as accounting draft. Open it in accounting to publish.')
    return redirect('accounting_bridge:review_detail', queue_id=queue.pk)


@require_POST
@_require_accountant
def review_reject(request, queue_id):
    queue = get_object_or_404(InvoiceSyncQueue, pk=queue_id)
    queue.status = InvoiceSyncQueue.Status.REJECTED
    queue.review_notes = (request.POST.get('review_notes') or '').strip()
    queue.reviewed_by = request.user
    queue.reviewed_at = timezone.now()
    queue.save()
    messages.warning(request, 'Invoice sync rejected.')
    return redirect('accounting_bridge:review_queue')


@_require_accountant
def opening_balances_list(request):
    rows = PartyOpeningBalance.objects.select_related('client', 'supplier', 'created_by').order_by('-as_of_date', '-created_at')[:200]
    return render(request, 'accounting_bridge/opening_balances.html', {'rows': rows})


@_require_accountant
def opening_balance_create(request):
    if request.method == 'POST':
        form = OpeningBalanceForm(request.POST)
        if form.is_valid():
            row = form.save(commit=False)
            row.created_by = request.user
            row.save()
            messages.success(request, 'Opening balance saved.')
            return redirect('accounting_bridge:opening_balances')
    else:
        form = OpeningBalanceForm()
    return render(request, 'accounting_bridge/opening_balance_form.html', {'form': form, 'title': 'Add opening balance'})


@_require_accountant
def opening_balance_edit(request, row_id):
    row = get_object_or_404(PartyOpeningBalance, pk=row_id)
    if request.method == 'POST':
        form = OpeningBalanceForm(request.POST, instance=row)
        if form.is_valid():
            form.save()
            messages.success(request, 'Opening balance updated.')
            return redirect('accounting_bridge:opening_balances')
    else:
        form = OpeningBalanceForm(instance=row)
    return render(request, 'accounting_bridge/opening_balance_form.html', {'form': form, 'title': 'Edit opening balance', 'row': row})


@require_POST
@_require_accountant
def opening_balance_delete(request, row_id):
    row = get_object_or_404(PartyOpeningBalance, pk=row_id)
    row.delete()
    messages.success(request, 'Opening balance deleted.')
    return redirect('accounting_bridge:opening_balances')
