from accounting_bridge.permissions import user_is_accountant


def app_shell(request):
    path = request.path or '/'
    zone = 'accounting' if path.startswith('/accounting/') else 'crm'
    return {
        'app_zone': zone,
        'user_is_accountant': user_is_accountant(request.user),
        'accounting_root': '/accounting/',
    }
