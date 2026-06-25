"""Sync CRM master data into accounting models."""

from __future__ import annotations

import logging

from django.contrib.auth.models import User
from django.db import transaction

from accounts_core.models import Client, Employee, Supplier
from accounts_core.party_codes import next_client_code, next_supplier_code
from catalog.models import Destination, ServiceType
from display.models import Lead
from tasks.models import LeadTask, Service
from tasks.models import ServiceType as CrmServiceType
from tasks.models import Supplier as CrmSupplier

from accounting_bridge.models import (
    CrmDestinationLink,
    CrmEmployeeLink,
    CrmServiceTypeLink,
    CrmSupplierLink,
    LeadClientLink,
)
from accounting_bridge.utils import normalize_phone_key

logger = logging.getLogger(__name__)


def _service_type_code(name: str) -> str:
    base = ''.join(ch for ch in name.upper() if ch.isalnum())[:8] or 'SRV'
    code = base
    suffix = 1
    while ServiceType.objects.filter(code=code).exists():
        code = f'{base[:6]}{suffix}'
        suffix += 1
    return code


def sync_client_from_lead(lead: Lead) -> Client:
    phone_key = normalize_phone_key(lead.phone)
    link = LeadClientLink.objects.filter(phone_key=phone_key).select_related('client', 'lead').first()
    if link:
        client = link.client
        changed = False
        if client.name_en != lead.name:
            client.name_en = lead.name
            changed = True
        if lead.email and client.email != lead.email:
            client.email = lead.email
            changed = True
        if lead.phone and client.phone != lead.phone:
            client.phone = lead.phone
            changed = True
        if changed:
            client.save(update_fields=['name_en', 'email', 'phone', 'updated_at'])
        if link.lead_id != lead.pk:
            link.lead = lead
            link.save(update_fields=['lead', 'synced_at'])
        return client

    existing = LeadClientLink.objects.filter(lead=lead).select_related('client').first()
    if existing:
        return existing.client

    client = Client.objects.create(
        client_code=next_client_code(),
        name_en=lead.name or 'Unknown',
        phone=lead.phone or '',
        email=lead.email or '',
        type=Client.ClientType.INDIVIDUAL,
    )
    LeadClientLink.objects.create(lead=lead, client=client, phone_key=phone_key)
    return client


def sync_destination(name: str) -> Destination | None:
    name = (name or '').strip()
    if not name:
        return None
    link = CrmDestinationLink.objects.filter(destination_name__iexact=name).select_related('acc_destination').first()
    if link:
        return link.acc_destination
    destination, _ = Destination.objects.get_or_create(name=name, defaults={'country': ''})
    CrmDestinationLink.objects.get_or_create(
        destination_name=name,
        defaults={'acc_destination': destination},
    )
    return destination


def sync_supplier(name: str) -> Supplier | None:
    name = (name or '').strip()
    if not name:
        return None
    crm_supplier = CrmSupplier.objects.filter(name__iexact=name).first()
    if crm_supplier:
        link = getattr(crm_supplier, 'accounting_link', None)
        if link:
            return link.acc_supplier
        acc_supplier = Supplier.objects.create(
            supplier_code=next_supplier_code(),
            name=crm_supplier.name,
            type=Supplier.SupplierType.OTHER,
        )
        CrmSupplierLink.objects.create(crm_supplier=crm_supplier, acc_supplier=acc_supplier)
        return acc_supplier
    acc_supplier = Supplier.objects.filter(name__iexact=name).first()
    if acc_supplier:
        return acc_supplier
    return Supplier.objects.create(
        supplier_code=next_supplier_code(),
        name=name,
        type=Supplier.SupplierType.OTHER,
    )


def sync_service_type(name: str) -> ServiceType | None:
    name = (name or '').strip()
    if not name:
        return None
    crm_type = CrmServiceType.objects.filter(name__iexact=name).first()
    if crm_type:
        link = getattr(crm_type, 'accounting_link', None)
        if link:
            return link.acc_service_type
        acc_type = ServiceType.objects.create(
            name=crm_type.name,
            code=_service_type_code(crm_type.name),
            is_active=True,
        )
        CrmServiceTypeLink.objects.create(crm_service_type=crm_type, acc_service_type=acc_type)
        return acc_type
    acc_type = ServiceType.objects.filter(name__iexact=name).first()
    if acc_type:
        return acc_type
    return ServiceType.objects.create(
        name=name,
        code=_service_type_code(name),
        is_active=True,
    )


def sync_employee_from_user(user: User) -> Employee | None:
    if not user or not user.pk:
        return None
    link = getattr(user, 'accounting_employee_link', None)
    if link:
        employee = link.employee
        display_name = user.get_full_name().strip() or user.username
        if employee.name != display_name:
            employee.name = display_name
            employee.save(update_fields=['name', 'updated_at'])
        return employee
    display_name = user.get_full_name().strip() or user.username
    role = Employee.EmployeeRole.ACCOUNTING if getattr(getattr(user, 'profile', None), 'is_accountant', False) else Employee.EmployeeRole.SALES
    employee = Employee.objects.create(name=display_name, user=user, role=role, is_active=user.is_active)
    CrmEmployeeLink.objects.create(user=user, employee=employee)
    return employee


@transaction.atomic
def sync_all_leads_as_clients():
    count = 0
    for lead in Lead.objects.all().iterator():
        sync_client_from_lead(lead)
        if lead.destination:
            sync_destination(lead.destination)
        count += 1
    return count


@transaction.atomic
def sync_all_crm_suppliers():
    count = 0
    for row in CrmSupplier.objects.filter(is_active=True).iterator():
        sync_supplier(row.name)
        count += 1
    return count


@transaction.atomic
def sync_all_crm_service_types():
    count = 0
    for row in CrmServiceType.objects.filter(is_active=True).iterator():
        sync_service_type(row.name)
        count += 1
    return count


@transaction.atomic
def sync_all_crm_employees():
    count = 0
    for user in User.objects.filter(is_active=True).iterator():
        sync_employee_from_user(user)
        count += 1
    return count


def sync_master_data_from_leadtask(leadtask: LeadTask) -> None:
    """Sync client, destination, employees, and every service line on a CRM order."""
    lead = leadtask.lead
    sync_client_from_lead(lead)
    sync_employee_from_user(leadtask.assigned_to)
    sync_employee_from_user(lead.assigned_to)
    if lead.destination:
        sync_destination(lead.destination)
    if lead.supplier:
        sync_supplier(lead.supplier)
    if lead.type_of_service:
        sync_service_type(lead.type_of_service)
    for service in leadtask.service_set.all().iterator():
        sync_master_data_from_service(service, leadtask=leadtask, lead=lead)


def sync_master_data_from_service(service: Service, *, leadtask=None, lead=None) -> None:
    leadtask = leadtask or service.leadtask
    lead = lead or leadtask.lead
    sync_client_from_lead(lead)
    if lead.destination:
        sync_destination(lead.destination)
    if service.service_name:
        sync_service_type(service.service_name)
    if service.supplier:
        sync_supplier(service.supplier)


@transaction.atomic
def sync_all_crm_destinations():
    """Sync CRM destination catalog and every destination seen on orders/leads."""
    from display.models import Destination as CrmDestination

    count = 0
    for row in CrmDestination.objects.all().iterator():
        if sync_destination(row.name):
            count += 1
    for name in Lead.objects.exclude(destination='').values_list('destination', flat=True).distinct():
        if sync_destination(name):
            count += 1
    return count


@transaction.atomic
def sync_all_from_crm_orders():
    """Pull clients, destinations, suppliers, and service types from all CRM invoices/orders."""
    order_count = 0
    service_count = 0
    for leadtask in LeadTask.objects.select_related('lead', 'assigned_to').iterator():
        sync_master_data_from_leadtask(leadtask)
        order_count += 1
        service_count += leadtask.service_set.count()
    return order_count, service_count


@transaction.atomic
def sync_all_crm_master_data():
    """
    Deployment backfill: master data from CRM orders (LeadTask), not unqualified leads.

    Creates/updates accounting clients (one per lead on an order), suppliers, service types,
    destinations, and employees. Does not create accounting invoices for historical orders.
  """
    destinations = sync_all_crm_destinations()
    suppliers = sync_all_crm_suppliers()
    service_types = sync_all_crm_service_types()
    employees = sync_all_crm_employees()
    orders, service_lines = sync_all_from_crm_orders()
    return {
        'clients': Client.objects.count(),
        'destinations': Destination.objects.count(),
        'destinations_synced': destinations,
        'suppliers': suppliers,
        'service_types': service_types,
        'employees': employees,
        'orders': orders,
        'service_lines': service_lines,
    }
