import csv
import json
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from display.models import Lead


class Command(BaseCommand):
    help = 'Export all leads to CSV or JSON file with status, destination, and personal info'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['csv', 'json'],
            default='csv',
            help='Export format: csv or json (default: csv)'
        )
        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='Output file path (default: leads_export_TIMESTAMP.csv/json)'
        )

    def handle(self, *args, **options):
        format_type = options['format']
        
        # Generate output filename if not provided
        if options['output']:
            output_file = options['output']
        else:
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'leads_export_{timestamp}.{format_type}'
        
        # Get all leads
        leads = Lead.objects.all().select_related('assigned_to').order_by('id')
        
        self.stdout.write(self.style.SUCCESS(f'Found {leads.count()} leads to export'))
        
        if format_type == 'csv':
            self.export_csv(leads, output_file)
        else:
            self.export_json(leads, output_file)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully exported leads to: {output_file}'))
        self.stdout.write(self.style.SUCCESS(f'File location: {os.path.abspath(output_file)}'))

    def safe_getattr(self, obj, attr, default=''):
        """Safely get attribute, return default if attribute doesn't exist"""
        return getattr(obj, attr, default) or default

    def export_csv(self, leads, output_file):
        """Export leads to CSV format"""
        fieldnames = [
            'ID',
            'Name',
            'Country Code',
            'Phone',
            'Status',
            'Sold',
            'Lost',
            'Destination',
            'Channel',
            'Type of Service',
            'Assigned To',
            'Pax',
            'Duration',
            'Travel Date From',
            'Travel Date To',
            'Selling Price',
            'Net',
            'Profit',
            'Budget Range From',
            'Budget Range To',
            'Reason of Travel',
            'Why This Destination',
            'Travel Dates Flexible',
            'Special Request',
            'Date Notes',
            'Assignment Notes',
            'Supplier',
            'Finalization Notes',
            'Urgent',
            'Follow Up Date',
            'Offer Prepared',
            'Offer Details',
            'Created At',
            'Last Modified',
            'Assigned At',
            'Status Changed At',
            'Is Archived',
            'Takeover',
            'Special Takeover',
            'Takeover Added At',
            'Moved to Negotiation',
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            total = leads.count()
            count = 0
            for lead in leads:
                count += 1
                if count % 100 == 0:
                    self.stdout.write(f'Processing lead {count}/{total}...')
                writer.writerow({
                    'ID': lead.id,
                    'Name': self.safe_getattr(lead, 'name'),
                    'Country Code': self.safe_getattr(lead, 'country_code'),
                    'Phone': self.safe_getattr(lead, 'phone'),
                    'Status': self.safe_getattr(lead, 'status'),
                    'Sold': 'Yes' if getattr(lead, 'sold', False) else 'No',
                    'Lost': 'Yes' if getattr(lead, 'lost', False) else 'No',
                    'Destination': self.safe_getattr(lead, 'destination'),
                    'Channel': self.safe_getattr(lead, 'channel'),
                    'Type of Service': self.safe_getattr(lead, 'type_of_service'),
                    'Assigned To': lead.assigned_to.username if lead.assigned_to else '',
                    'Pax': self.safe_getattr(lead, 'pax'),
                    'Duration': self.safe_getattr(lead, 'duration'),
                    'Travel Date From': lead.travel_date_from.strftime('%Y-%m-%d') if getattr(lead, 'travel_date_from', None) else '',
                    'Travel Date To': lead.travel_date_to.strftime('%Y-%m-%d') if getattr(lead, 'travel_date_to', None) else '',
                    'Selling Price': self.safe_getattr(lead, 'selling_price'),
                    'Net': self.safe_getattr(lead, 'net'),
                    'Profit': self.safe_getattr(lead, 'profit'),
                    'Budget Range From': '' if getattr(lead, 'budget_range_from', None) is None else str(getattr(lead, 'budget_range_from')),
                    'Budget Range To': '' if getattr(lead, 'budget_range_to', None) is None else str(getattr(lead, 'budget_range_to')),
                    'Reason of Travel': self.safe_getattr(lead, 'reason_of_travel'),
                    'Why This Destination': self.safe_getattr(lead, 'why_this_destination'),
                    'Travel Dates Flexible': 'Yes' if getattr(lead, 'travel_dates_flexible', False) else 'No',
                    'Special Request': self.safe_getattr(lead, 'special_request'),
                    'Date Notes': self.safe_getattr(lead, 'date_notes'),
                    'Assignment Notes': self.safe_getattr(lead, 'assignment_notes'),
                    'Supplier': self.safe_getattr(lead, 'supplier'),
                    'Finalization Notes': self.safe_getattr(lead, 'finalization_notes'),
                    'Urgent': 'Yes' if getattr(lead, 'urgent', False) else 'No',
                    'Follow Up Date': lead.follow_up.strftime('%Y-%m-%d') if getattr(lead, 'follow_up', None) else '',
                    'Offer Prepared': 'Yes' if getattr(lead, 'offer_prepared', False) else 'No',
                    'Offer Details': self.safe_getattr(lead, 'offer_details'),
                    'Created At': lead.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(lead, 'created_at', None) else '',
                    'Last Modified': lead.last_modified.strftime('%Y-%m-%d %H:%M:%S') if getattr(lead, 'last_modified', None) else '',
                    'Assigned At': lead.assigned_at.strftime('%Y-%m-%d') if getattr(lead, 'assigned_at', None) else '',
                    'Status Changed At': lead.status_changed_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(lead, 'status_changed_at', None) else '',
                    'Is Archived': 'Yes' if getattr(lead, 'is_archived', False) else 'No',
                    'Takeover': 'Yes' if getattr(lead, 'takeover', False) else 'No',
                    'Special Takeover': 'Yes' if getattr(lead, 'special_takeover', False) else 'No',
                    'Takeover Added At': lead.takeover_added_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(lead, 'takeover_added_at', None) else '',
                    'Moved to Negotiation': 'Yes' if getattr(lead, 'moved_to_negotiation', False) else 'No',
                })

    def export_json(self, leads, output_file):
        """Export leads to JSON format"""
        leads_data = []
        
        total = leads.count()
        count = 0
        for lead in leads:
            count += 1
            if count % 100 == 0:
                self.stdout.write(f'Processing lead {count}/{total}...')
            lead_data = {
                'id': lead.id,
                'name': self.safe_getattr(lead, 'name'),
                'country_code': self.safe_getattr(lead, 'country_code'),
                'phone': self.safe_getattr(lead, 'phone'),
                'status': self.safe_getattr(lead, 'status'),
                'sold': getattr(lead, 'sold', False),
                'lost': getattr(lead, 'lost', False),
                'destination': self.safe_getattr(lead, 'destination'),
                'channel': self.safe_getattr(lead, 'channel'),
                'type_of_service': self.safe_getattr(lead, 'type_of_service'),
                'assigned_to': lead.assigned_to.username if lead.assigned_to else '',
                'pax': self.safe_getattr(lead, 'pax'),
                'duration': self.safe_getattr(lead, 'duration'),
                'travel_date_from': lead.travel_date_from.strftime('%Y-%m-%d') if getattr(lead, 'travel_date_from', None) else None,
                'travel_date_to': lead.travel_date_to.strftime('%Y-%m-%d') if getattr(lead, 'travel_date_to', None) else None,
                'selling_price': self.safe_getattr(lead, 'selling_price'),
                'net': self.safe_getattr(lead, 'net'),
                'profit': self.safe_getattr(lead, 'profit'),
                'budget_range_from': getattr(lead, 'budget_range_from', None),
                'budget_range_to': getattr(lead, 'budget_range_to', None),
                'reason_of_travel': self.safe_getattr(lead, 'reason_of_travel'),
                'why_this_destination': self.safe_getattr(lead, 'why_this_destination'),
                'travel_dates_flexible': getattr(lead, 'travel_dates_flexible', False),
                'special_request': self.safe_getattr(lead, 'special_request'),
                'date_notes': self.safe_getattr(lead, 'date_notes'),
                'assignment_notes': self.safe_getattr(lead, 'assignment_notes'),
                'supplier': self.safe_getattr(lead, 'supplier'),
                'finalization_notes': self.safe_getattr(lead, 'finalization_notes'),
                'urgent': getattr(lead, 'urgent', False),
                'follow_up': lead.follow_up.strftime('%Y-%m-%d') if getattr(lead, 'follow_up', None) else None,
                'offer_prepared': getattr(lead, 'offer_prepared', False),
                'offer_details': self.safe_getattr(lead, 'offer_details'),
                'created_at': lead.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(lead, 'created_at', None) else None,
                'last_modified': lead.last_modified.strftime('%Y-%m-%d %H:%M:%S') if getattr(lead, 'last_modified', None) else None,
                'assigned_at': lead.assigned_at.strftime('%Y-%m-%d') if getattr(lead, 'assigned_at', None) else None,
                'status_changed_at': lead.status_changed_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(lead, 'status_changed_at', None) else None,
                'is_archived': getattr(lead, 'is_archived', False),
                'takeover': getattr(lead, 'takeover', False),
                'special_takeover': getattr(lead, 'special_takeover', False),
                'takeover_added_at': lead.takeover_added_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(lead, 'takeover_added_at', None) else None,
                'moved_to_negotiation': getattr(lead, 'moved_to_negotiation', False),
            }
            leads_data.append(lead_data)
        
        with open(output_file, 'w', encoding='utf-8') as jsonfile:
            json.dump(leads_data, jsonfile, indent=2, ensure_ascii=False)

