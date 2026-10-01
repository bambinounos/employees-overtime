"""
Management command para reconciliar y reprocesar facturas y pagos desde WebhookLog.

Uso:
    python manage.py reconciliar_webhooks_ventas --dry-run
    python manage.py reconciliar_webhooks_ventas
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from employees.api_views import DolibarrWebhookView
from employees.models import DolibarrInstance, Employee, SalesRecord, WebhookLog


class Command(BaseCommand):
    help = "Reprocesa eventos de facturas y pagos históricos almacenados en WebhookLog."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecuta la reconciliación en modo simulación sin guardar cambios en la base de datos.',
        )
        parser.add_argument(
            '--instance',
            type=str,
            default=None,
            help='Nombre de la instancia de Dolibarr (opcional).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        instance_filter = options['instance']

        instances = DolibarrInstance.objects.all()
        if instance_filter:
            instances = instances.filter(name=instance_filter)

        if not instances.exists():
            self.stdout.write(self.style.ERROR("No se encontraron instancias de Dolibarr activas."))
            return

        instances_by_pro_id = {inst.professional_id: inst for inst in instances if inst.professional_id}
        default_instance = instances.first()

        def resolve_instance(log):
            if isinstance(log.headers, dict):
                for k, v in log.headers.items():
                    if k.lower() == 'x-dolibarr-professional-id' and v in instances_by_pro_id:
                        return instances_by_pro_id[v]
            return default_instance

        self.stdout.write(self.style.NOTICE(
            f"Iniciando reconciliación de webhooks (dry_run={dry_run})..."
        ))

        view = DolibarrWebhookView()
        logs = WebhookLog.objects.order_by('id')

        with transaction.atomic():
            stats = {
                'orders_processed': 0,
                'propals_processed': 0,
                'bills_processed': 0,
                'payments_processed': 0,
            }

            # 1. Orders and Proformas pass (ensure all bases exist)
            for log in logs:
                payload = log.payload
                if not isinstance(payload, dict):
                    continue
                trigger = payload.get('trigger_code')
                if trigger not in ('PROPAL_VALIDATE', 'ORDER_VALIDATE'):
                    continue

                inst = resolve_instance(log)
                if trigger == 'PROPAL_VALIDATE':
                    view.process_proforma(payload, inst)
                    stats['propals_processed'] += 1
                elif trigger == 'ORDER_VALIDATE':
                    view.process_order(payload, inst)
                    stats['orders_processed'] += 1

            # 2. Bills pass (process BILL_VALIDATE)
            for log in logs:
                payload = log.payload
                if not isinstance(payload, dict):
                    continue
                trigger = payload.get('trigger_code')
                if trigger != 'BILL_VALIDATE':
                    continue

                inst = resolve_instance(log)
                fallback_date = log.received_at.date() if log.received_at else None
                view.process_bill_validate(payload, inst, fallback_date=fallback_date)
                stats['bills_processed'] += 1

            # 3. Payments pass (process PAYMENT_CUSTOMER_CREATE)
            for log in logs:
                payload = log.payload
                if not isinstance(payload, dict):
                    continue
                trigger = payload.get('trigger_code')
                if trigger != 'PAYMENT_CUSTOMER_CREATE':
                    continue

                inst = resolve_instance(log)
                view.process_payment(payload, inst)
                stats['payments_processed'] += 1

            self.stdout.write(self.style.SUCCESS(
                f"Eventos procesados: {stats['propals_processed']} proformas, {stats['orders_processed']} pedidos, "
                f"{stats['bills_processed']} facturas, {stats['payments_processed']} pagos."
            ))

            total_invoiced = SalesRecord.objects.filter(status='invoiced').count()
            total_paid = SalesRecord.objects.filter(status='invoiced', payment_date__isnull=False).count()
            self.stdout.write(self.style.SUCCESS(
                f"Estado resultante en DB: {total_invoiced} facturas ({total_paid} con fecha de pago confirmada)."
            ))

            self.stdout.write("\n--- RESUMEN POR EMPLEADO VENDEDOR (Septiembre 2026) ---")
            for emp in Employee.objects.filter(commission_percentage__gt=0).order_by('id'):
                comm = emp.calculate_commissions(2026, 9)
                self.stdout.write(
                    f"\n{emp.name} (Comisión: {emp.commission_percentage}%):\n"
                    f"  Facturas cobradas en Sep: {comm['confirmed_count']} (${comm['confirmed_invoiced']:.2f})\n"
                    f"  Comisión ganada en Sep:   ${comm['commission_amount']:.2f}\n"
                    f"  Facturas provisionales:   {comm['provisional_count']} (${comm['provisional_invoiced']:.2f})"
                )

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("\n[DRY-RUN] Cambios revertidos. La base de datos no fue modificada."))
            else:
                self.stdout.write(self.style.SUCCESS("\n[APLICADO] Cambios confirmados en la base de datos."))
