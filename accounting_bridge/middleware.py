from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from accounting_bridge.permissions import user_is_accountant

ACCOUNTING_PREFIX = '/accounting/'


class AccountingAccessMiddleware:
    """Restrict /accounting/ routes to accountant users."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith(ACCOUNTING_PREFIX):
            if not request.user.is_authenticated:
                return redirect(f"{reverse('login_user')}?next={path}")
            if not user_is_accountant(request.user):
                messages.error(request, 'Accounting access is restricted to main accountant users.')
                return redirect('calendar')
        return self.get_response(request)
