"""Business intelligence — redirected to accounting dashboard."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from accounting_bridge.permissions import user_is_accountant


@login_required(login_url='/login/')
def overview_dashboard(request):
    """CRM overview retired; accountants use /accounting/, others use stats dashboard."""
    if user_is_accountant(request.user):
        return redirect('/accounting/')
    return redirect('stats_dashboard')
