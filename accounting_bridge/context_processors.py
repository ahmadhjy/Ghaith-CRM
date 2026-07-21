from accounting_bridge.permissions import user_is_accountant
from display.permissions import user_can_view_management_dashboards


def app_shell(request):
    path = request.path or '/'
    zone = 'accounting' if path.startswith('/accounting/') else 'crm'
    return {
        'app_zone': zone,
        'user_is_accountant': user_is_accountant(request.user),
        'user_can_view_management_dashboards': user_can_view_management_dashboards(
            request.user
        ),
        'accounting_root': '/accounting/',
    }
