import hashlib
import hmac
import json
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.conf import settings
from .models import DolibarrInstance, DolibarrUserIdentity, SalesRecord, WebhookLog, ProductCreationLog

class DolibarrWebhookView(APIView):
    """
    Endpoint to receive webhooks from Dolibarr.
    Validates HMAC signature and processes sales/product events.
    """
    permission_classes = [AllowAny] # We use HMAC for auth

    def post(self, request):
        # 1. Capture Raw Data for logging and verification
        try:
            body_unicode = request.body.decode('utf-8')
        except:
            body_unicode = str(request.body)
            
        professional_id = request.headers.get('X-Dolibarr-Professional-ID')
        signature = request.headers.get('X-Dolibarr-Signature')
        
        # 2. Log reception (Async processing ideally, but sync for now)
        log = WebhookLog.objects.create(
            sender_ip=self.get_client_ip(request),
            headers=dict(request.headers),
            payload=request.data
        )

        try:
            # 3. Authenticate Instance
            if not professional_id or not signature:
                raise ValueError("Missing headers")

            try:
                instance = DolibarrInstance.objects.get(professional_id=professional_id)
            except DolibarrInstance.DoesNotExist:
                raise ValueError("Unknown Instance")

            # 4. Validate HMAC
            # Signature = HMAC-SHA256(Secret + Body)? Or just Body?
            # Standard Dolibarr webhook module usually signs the body.
            # Assuming Hex Digest.
            computed_signature = hmac.new(
                key=instance.api_secret.encode('utf-8'),
                msg=request.body,
                digestmod=hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(computed_signature, signature):
                raise ValueError("Invalid Signature")

            # 5. Process Event
            payload = request.data
            event_type = payload.get('trigger_code') # Dolibarr trigger code e.g. 'BILL_VALIDATE'
            
            if event_type == 'BILL_VALIDATE':
                self.process_invoice(payload, instance)
            elif event_type == 'PROPAL_VALIDATE':
                 # Might log for audit, but Sales Effectiveness mainly cares about conversion
                 # If we need to count total proformas, we should store them too.
                 self.process_proforma(payload, instance)
            elif event_type == 'PRODUCT_CREATE':
                self.process_product_creation(payload, instance)

            log.status = 'processed'
            log.save()
            return Response({'status': 'ok'})

        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.save()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def process_invoice(self, payload, instance):
        # Payload structure depends on Dolibarr version, assuming standard object fields
        # object: { id, ref, total_ht, fk_user_author, ... }
        obj = payload.get('object', {})
        dolibarr_user_id = obj.get('fk_user_author')
        
        # Find Employee
        try:
            identity = DolibarrUserIdentity.objects.get(
                dolibarr_instance=instance,
                dolibarr_user_id=dolibarr_user_id
            )
            employee = identity.employee
        except DolibarrUserIdentity.DoesNotExist:
            # Log warning or create a "Unknown" record?
            # For now, just return, or log warning in WebhookLog
            print(f"Employee not found for user {dolibarr_user_id}")
            return

        SalesRecord.objects.create(
            employee=employee,
            dolibarr_instance=instance,
            dolibarr_id=obj.get('id'),
            dolibarr_ref=obj.get('ref'),
            origin_poforma_id=obj.get('fk_propal', None), # Assuming field name
            status='invoiced',
            amount_untaxed=obj.get('total_ht'),
            date=timezone.now().date() # Or payload date
        )

    def process_proforma(self, payload, instance):
        obj = payload.get('object', {})
        dolibarr_user_id = obj.get('fk_user_author')
        
        try:
            identity = DolibarrUserIdentity.objects.get(
                dolibarr_instance=instance, 
                dolibarr_user_id=dolibarr_user_id
            )
            employee = identity.employee
        except DolibarrUserIdentity.DoesNotExist:
            return

        SalesRecord.objects.create(
            employee=employee,
            dolibarr_instance=instance,
            dolibarr_id=obj.get('id'),
            dolibarr_ref=obj.get('ref'),
            status='proforma',
            amount_untaxed=obj.get('total_ht'),
            date=timezone.now().date()
        )

    def process_product_creation(self, payload, instance):
        obj = payload.get('object', {})
        dolibarr_user_id = obj.get('fk_user_author')
        
        try:
            identity = DolibarrUserIdentity.objects.get(
                dolibarr_instance=instance,
                dolibarr_user_id=dolibarr_user_id
            )
            employee = identity.employee
        except DolibarrUserIdentity.DoesNotExist:
            return

        ProductCreationLog.objects.create(
            employee=employee,
            dolibarr_instance=instance,
            dolibarr_product_id=obj.get('id'),
            product_ref=obj.get('ref'),
            created_at=timezone.now()
        )
