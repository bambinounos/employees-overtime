from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import F, Avg, Sum
from django.db.models.functions import Coalesce
import hashlib
import hmac
from django.utils import timezone

class JobProfile(models.Model):
    """Defines a job role and the KPIs associated with it."""
    name = models.CharField(max_length=255, unique=True)
    kpis = models.ManyToManyField('KPI', related_name='job_profiles', blank=True)
    earns_commissions = models.BooleanField(default=False, help_text="If true, this profile is eligible for variable sales commissions.")
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class DolibarrInstance(models.Model):
    """Represents a connected Dolibarr ERP instance."""
    name = models.CharField(max_length=255, help_text="Friendly name, e.g., 'Empresa A'")
    professional_id = models.CharField(max_length=100, unique=True, help_text="ID Profesional 1 from Dolibarr Admin Panel")
    api_secret = models.CharField(max_length=128, help_text="Secret key for HMAC validation of webhooks")
    api_base_url = models.URLField(
        blank=True, default='',
        help_text="URL raíz de Dolibarr, ej: https://erp.empresa.com (sin /api). Vacío = sin push de nómina.")
    api_key = models.CharField(
        max_length=128, blank=True, default='',
        help_text="DOLAPIKEY de un usuario Dolibarr con permiso salaries → write. Vacío = sin push de nómina.")

    def __str__(self):
        return f"{self.name} ({self.professional_id})"

    @property
    def push_habilitado(self):
        """True si la instancia tiene URL y clave para enviar nómina."""
        return bool(self.api_base_url and self.api_key)

class DolibarrUserIdentity(models.Model):
    """Links a local Employee to a user in a specific Dolibarr instance."""
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='dolibarr_identities')
    dolibarr_instance = models.ForeignKey(DolibarrInstance, on_delete=models.CASCADE)
    dolibarr_user_id = models.IntegerField(help_text="Numeric User ID in Dolibarr (rowid)")
    dolibarr_login = models.CharField(max_length=100, blank=True, null=True, help_text="Login username in Dolibarr (reference only)")

    class Meta:
        unique_together = ('dolibarr_instance', 'dolibarr_user_id')
        verbose_name_plural = "Dolibarr User Identities"

    def __str__(self):
        return f"{self.employee.name} @ {self.dolibarr_instance.name}"


class Employee(models.Model):
    """Represents an employee in the company."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    hire_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    profile = models.ForeignKey(JobProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', help_text="Job Profile determining active KPIs for this employee.")
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Porcentaje de comision sobre ventas netas facturadas (ej: 5.00 = 5%). Maximo 100%."
    )
    dias_vacaciones_anuales = models.PositiveSmallIntegerField(
        default=15,
        help_text="Días de vacaciones por año calendario que descuentan del saldo."
    )


    def __str__(self):
        return self.name

    def saldo_vacaciones(self, year=None):
        """Días de vacaciones disponibles en el año: cupo anual menos los días
        hábiles de solicitudes APROBADAS de tipos que descuentan saldo."""
        if year is None:
            year = date.today().year
        usados = self.solicitudes_ausencia.filter(
            estado='APROBADA',
            tipo__descuenta_saldo=True,
            fecha_inicio__year=year,
        ).aggregate(total=Coalesce(Sum('dias_habiles'), Decimal('0')))['total']
        return Decimal(self.dias_vacaciones_anuales) - usados

    @property
    def is_active(self):
        """Returns True if the employee is currently active.
        An employee with a future end_date is still active until that date."""
        if self.end_date is None:
            return True
        return self.end_date >= date.today()

    def _period_closing_cutoff(self, year, month):
        """
        Devuelve el instante límite (timezone-aware datetime) del período (year, month)
        para distinguir los errores/eventos registrados dentro del propio mes (on-time)
        frente a hallazgos registrados en meses posteriores (retroactivos).
        """
        import calendar
        from datetime import datetime, time
        last_day = calendar.monthrange(year, month)[1]
        tz = timezone.get_current_timezone()
        month_end_dt = timezone.make_aware(
            datetime.combine(date(year, month, last_day), time(23, 59, 59, 999999)),
            tz,
        )
        recibo = self.recibos.filter(year=year, month=month, dolibarr_salary_id__isnull=False).first()
        if recibo and recibo.generado_en and recibo.generado_en < month_end_dt:
            return recibo.generado_en
        return month_end_dt

    def calculate_ipac(self, year, month, include_retroactive=False):
        """
        Calculates the Quality-Adjusted Productivity Index (IPAC) for a given month.
        IPAC = (Completed Tasks * On-time Factor * Quality Factor) / Business Days

        El resultado son "tareas efectivas por día hábil". El tiempo de
        ejecución (creado -> completado) se eliminó deliberadamente: medía
        tiempo de cola, castigaba crear tareas con anticipación y hacía el
        target inalcanzable. Para el mes en curso se usan los días hábiles
        transcurridos a la fecha, de modo que el índice sea legible a mitad
        de mes; los meses cerrados siempre usan el mes completo.

        Solo cuentan las tareas con fecha límite (due_date): una tarea sin
        fecha no acredita productividad y antes inflaba el índice sin
        riesgo de atraso (contaba en el numerador pero se excluía del
        factor de puntualidad).
        """
        # 1. Tasks completed in the given month/year, with a due date.
        completed_tasks = Task.objects.filter(
            assigned_to=self,
            completed_at__year=year,
            completed_at__month=month
        ).exclude(due_date__isnull=True)
        num_completed_tasks = completed_tasks.count()

        if num_completed_tasks == 0:
            return Decimal('0.00')

        # 2. On-time Factor
        on_time_count = completed_tasks.filter(completed_at__date__lte=F('due_date')).count()
        on_time_factor = Decimal(on_time_count) / Decimal(num_completed_tasks)

        # 3. Quality Factor (based on manually logged errors)
        # This assumes that any KPI measured as 'count_lt' (less is better) is an error-tracking KPI.
        error_kpis = KPI.objects.filter(measurement_type='count_lt')
        error_qs = ManualKpiEntry.objects.filter(
            employee=self,
            kpi__in=error_kpis,
            date__year=year,
            date__month=month
        )
        if not include_retroactive:
            cutoff = self._period_closing_cutoff(year, month)
            error_qs = error_qs.filter(created_at__lte=cutoff)
        num_errors = error_qs.aggregate(total_errors=Coalesce(Sum('value'), Decimal('0')))['total_errors']

        error_rate = Decimal(num_errors) / Decimal(num_completed_tasks)
        quality_factor = max(Decimal('0.0'), Decimal('1.0') - error_rate)

        # 4. Business days (Mon-Fri): full month for closed periods,
        #    elapsed days so far for the current month.
        import calendar
        today = timezone.localtime(timezone.now()).date()
        last_day = calendar.monthrange(year, month)[1]
        if (year, month) == (today.year, today.month):
            last_day = min(last_day, today.day)
        business_days = sum(
            1 for d in range(1, last_day + 1)
            if date(year, month, d).weekday() < 5
        )
        business_days = max(business_days, 1)

        # 5. Final IPAC Calculation
        numerator = Decimal(num_completed_tasks) * on_time_factor * quality_factor
        ipac_score = numerator / Decimal(business_days)

        return ipac_score.quantize(Decimal('0.01'))

    def calculate_commissions(self, year, month):
        """
        Calculates sales commissions for a given month.

        Rules:
        - Confirmed: invoices paid this month (payment_date in target month)
        - Provisional: invoices not yet paid (informational, NOT added to salary)
        - Negative: credit notes issued this month (deducted from salary)
          Credit notes are attributed to the employee who made the original invoice,
          not the user who issued the credit note.

        Commission = confirmed_net * commission_percentage / 100
        """
        zero = Decimal('0.00')
        pct = self.commission_percentage

        if pct <= 0:
            return {
                'commission_amount': zero,
                'confirmed_invoiced': zero,
                'confirmed_count': 0,
                'provisional_invoiced': zero,
                'provisional_count': 0,
                'credit_notes_amount': zero,
                'credit_note_count': 0,
                'net_confirmed': zero,
                'commission_percentage': zero,
            }

        my_sales = self.sales_records

        # Confirmed: invoices paid this month
        confirmed = my_sales.filter(
            status='invoiced',
            payment_date__year=year,
            payment_date__month=month,
        )
        confirmed_invoiced = confirmed.aggregate(
            total=Sum('amount_untaxed')
        )['total'] or zero

        # Provisional: invoices not yet paid (all months, still pending)
        provisional = my_sales.filter(
            status='invoiced',
            payment_date__isnull=True,
        )
        provisional_invoiced = provisional.aggregate(
            total=Sum('amount_untaxed')
        )['total'] or zero

        # Negative: credit notes in this month (already stored as negative)
        credit_notes = my_sales.filter(
            status='credit_note',
            date__year=year,
            date__month=month,
        )
        credit_notes_amount = credit_notes.aggregate(
            total=Sum('amount_untaxed')
        )['total'] or zero  # negative value

        # Net confirmed = paid invoices + credit notes (credit notes are negative)
        net_confirmed = confirmed_invoiced + credit_notes_amount

        # Raw commission before clawback
        raw_commission = (net_confirmed * pct / Decimal('100')).quantize(Decimal('0.01'))

        # Apply clawback: use running balance to recover past debts
        bal, _ = CommissionBalance.objects.get_or_create(employee=self)

        last_computed = (bal.last_computed_year, bal.last_computed_month)
        requested = (year, month)

        if requested == last_computed:
            # Same month recalculation (new invoices arrived): use pre-month snapshot
            carry_forward = bal.pre_month_balance
            adjusted = raw_commission + carry_forward
            commission_amount = max(zero, adjusted)
            remaining_debt = min(zero, adjusted)
            bal.balance = remaining_debt
            bal.save()
        elif requested > last_computed:
            # New month (forward): snapshot and advance
            carry_forward = bal.balance
            bal.pre_month_balance = bal.balance
            adjusted = raw_commission + carry_forward
            commission_amount = max(zero, adjusted)
            remaining_debt = min(zero, adjusted)
            bal.balance = remaining_debt
            bal.last_computed_year = year
            bal.last_computed_month = month
            bal.save()
        else:
            # Past month query: read-only, do NOT modify balance
            carry_forward = zero
            commission_amount = max(zero, raw_commission)
            remaining_debt = zero

        return {
            'commission_amount': commission_amount,
            'raw_commission': raw_commission,
            'carry_forward_applied': carry_forward,
            'remaining_debt': remaining_debt,
            'confirmed_invoiced': confirmed_invoiced,
            'confirmed_count': confirmed.count(),
            'provisional_invoiced': provisional_invoiced,
            'provisional_count': provisional.count(),
            'credit_notes_amount': abs(credit_notes_amount),
            'credit_note_count': credit_notes.count(),
            'net_confirmed': net_confirmed,
            'commission_percentage': pct,
        }

    def _evaluate_kpis_for_period(self, year, month, include_retroactive=False):
        """
        Evalúa todos los KPIs del perfil del empleado para (year, month).
        - Si include_retroactive=False: usa solo los ManualKpiEntry registrados hasta
          el corte del período (lo que realmente se pagó al cierre de ese mes).
        - Si include_retroactive=True: incluye también los ManualKpiEntry con fecha
          en (year, month) que fueron descubiertos/registrados en meses posteriores.
        Devuelve un dict:
            {kpi.id: {'kpi': kpi, 'actual_value': Decimal, 'target_met': bool, 'bonus': Decimal}}
        """
        if not self.profile:
            return {}
        eligible_kpis = self.profile.kpis.all()
        cutoff = None if include_retroactive else self._period_closing_cutoff(year, month)
        results = {}

        for kpi in eligible_kpis:
            target_met = False
            actual_value = Decimal('0.00')

            if kpi.internal_code == 'SALES_EFFECTIVENESS':
                sales_records = self.sales_records.filter(
                    date__year=year,
                    date__month=month
                )
                total_proformas = sales_records.filter(status='proforma').count()

                if total_proformas >= kpi.min_volume_threshold and total_proformas > 0:
                    invoices_count = sales_records.filter(
                        status='invoiced',
                        origin_proforma_id__isnull=False
                    ).count()
                    actual_value = (Decimal(invoices_count) / Decimal(total_proformas)) * 100
                else:
                    actual_value = Decimal('0.00')

            elif kpi.internal_code == 'PRODUCT_CREATION':
                actual_value = Decimal(ProductCreationLog.objects.filter(
                    employee=self,
                    created_at__year=year,
                    created_at__month=month,
                    is_suspect_duplicate=False,
                ).count())

            elif kpi.measurement_type == 'percentage':
                tasks = Task.objects.filter(assigned_to=self, kpi=kpi, due_date__year=year, due_date__month=month)
                total_tasks = tasks.count()
                if total_tasks > 0:
                    completed_tasks = tasks.filter(completed_at__isnull=False, list__name__iexact="Hecho").count()
                    actual_value = (Decimal(completed_tasks) / Decimal(total_tasks)) * 100
                else:
                    actual_value = Decimal('0.00')

            elif kpi.measurement_type == 'count_lt':
                entries = ManualKpiEntry.objects.filter(
                    employee=self, kpi=kpi, date__year=year, date__month=month
                )
                if cutoff is not None:
                    entries = entries.filter(created_at__lte=cutoff)
                actual_value = sum((entry.value for entry in entries), Decimal('0.00'))

            elif kpi.measurement_type == 'count_gt':
                actual_value = Decimal(Task.objects.filter(
                    assigned_to=self,
                    kpi=kpi,
                    completed_at__year=year,
                    completed_at__month=month
                ).count())

            elif kpi.measurement_type == 'composite_ipac':
                actual_value = self.calculate_ipac(year, month, include_retroactive=include_retroactive)

            bonus_amount_for_kpi = Decimal('0.00')

            if kpi.measurement_type == 'count_lt':
                if actual_value < kpi.target_value:
                    target_met = True
            else:
                if actual_value >= kpi.target_value:
                    target_met = True

            rule = BonusRule.objects.filter(kpi=kpi).first()
            if rule and target_met:
                bonus_amount_for_kpi = rule.bonus_amount

            for tier in kpi.tiers.all():
                if kpi.measurement_type == 'count_lt':
                    tier_reached = actual_value <= tier.threshold
                else:
                    tier_reached = actual_value >= tier.threshold
                if tier_reached and tier.bonus_amount > bonus_amount_for_kpi:
                    bonus_amount_for_kpi = tier.bonus_amount
                    target_met = True

            results[kpi.id] = {
                'kpi': kpi,
                'actual_value': Decimal(str(actual_value)),
                'target_met': target_met,
                'bonus': bonus_amount_for_kpi,
            }

        return results

    def calculate_performance_bonus(self, year, month):
        """
        Calculates the total performance bonus for a given employee, year, and month.
        It also creates EmployeePerformanceRecord entries for each KPI.
        """
        if not self.profile:
            return Decimal('0.00')

        import calendar
        last_day = calendar.monthrange(year, month)[1]
        record_date = date(year, month, last_day)

        evaluated = self._evaluate_kpis_for_period(year, month, include_retroactive=False)
        total_bonus = Decimal('0.00')

        for item in evaluated.values():
            kpi = item['kpi']
            actual_value = item['actual_value']
            target_met = item['target_met']
            bonus_amount_for_kpi = item['bonus']
            total_bonus += bonus_amount_for_kpi

            EmployeePerformanceRecord.objects.update_or_create(
                employee=self,
                kpi=kpi,
                date=record_date,
                defaults={
                    'actual_value': actual_value,
                    'target_met': target_met,
                    'bonus_awarded': bonus_amount_for_kpi
                }
            )

        return total_bonus

    def sync_retroactive_bonus_deductions(self):
        """
        Sincroniza los descuentos retroactivos de bono (DescuentoRetroactivoBono)
        cuando existen registros ManualKpiEntry cuya fecha de evento pertenece a
        un mes pasado/cerrado pero fueron detectados y registrados después del
        cierre de ese mes.

        Implementa la Opción A (recálculo integral del mes pasado): evalúa tanto
        el KPI directo ('count_lt') como el IPAC ('composite_ipac') de ese mes
        pasado y descuenta en el próximo mes abierto únicamente el bono que se
        cobró en exceso, sin contaminar los KPIs del mes actual ni cobrar dos veces.
        """
        def _fmt_num(val):
            d = Decimal(str(val)).normalize()
            if d == d.to_integral_value():
                d = d.quantize(Decimal(1))
            return f"{d:n}"

        def _next_month(y, m):
            return (y + 1, 1) if m == 12 else (y, m + 1)

        # Recolectar todos los períodos origen con entradas manuales o descuentos previos
        entry_dates = ManualKpiEntry.objects.filter(employee=self).values_list('date', flat=True)
        periods = {(d.year, d.month) for d in entry_dates}
        existing_origins = DescuentoRetroactivoBono.objects.filter(
            employee=self
        ).values_list('origin_year', 'origin_month')
        periods.update(existing_origins)

        for orig_year, orig_month in sorted(periods):
            cutoff = self._period_closing_cutoff(orig_year, orig_month)
            retro_entries = ManualKpiEntry.objects.filter(
                employee=self,
                date__year=orig_year,
                date__month=orig_month,
                created_at__gt=cutoff,
            )

            if not retro_entries.exists():
                # Si no hay entradas retroactivas, limpiar descuentos abiertos de este origen
                open_deductions = DescuentoRetroactivoBono.objects.filter(
                    employee=self, origin_year=orig_year, origin_month=orig_month
                )
                for ded in open_deductions:
                    closed = self.recibos.filter(
                        year=ded.applied_year, month=ded.applied_month,
                        dolibarr_salary_id__isnull=False
                    ).exists()
                    if not closed:
                        ded.delete()
                continue

            baseline_eval = self._evaluate_kpis_for_period(orig_year, orig_month, include_retroactive=False)
            recalc_eval = self._evaluate_kpis_for_period(orig_year, orig_month, include_retroactive=True)

            orig_recibo = self.recibos.filter(year=orig_year, month=orig_month).first()
            recibo_bonus_by_kpi = {}
            if orig_recibo and isinstance(orig_recibo.datos, dict):
                recibo_bonus_by_kpi = orig_recibo.datos.get('bonus_by_kpi') or {}

            latest_reg = timezone.localtime(retro_entries.aggregate(m=models.Max('created_at'))['m'])
            apply_year, apply_month = latest_reg.year, latest_reg.month
            if (apply_year, apply_month) <= (orig_year, orig_month):
                apply_year, apply_month = _next_month(orig_year, orig_month)

            # Si el mes destino ya fue cerrado/enviado a Dolibarr antes del hallazgo, avanzar al siguiente
            while self.recibos.filter(
                year=apply_year, month=apply_month
            ).filter(
                models.Q(dolibarr_salary_id__isnull=False) | models.Q(generado_en__lt=latest_reg)
            ).exists():
                apply_year, apply_month = _next_month(apply_year, apply_month)

            for kpi_id, base_info in baseline_eval.items():
                kpi = base_info['kpi']
                curr_info = recalc_eval.get(kpi_id, base_info)

                if str(kpi_id) in recibo_bonus_by_kpi:
                    base_bonus = Decimal(str(recibo_bonus_by_kpi[str(kpi_id)]))
                else:
                    base_bonus = base_info['bonus']
                curr_bonus = curr_info['bonus']

                total_overpaid = max(Decimal('0.00'), base_bonus - curr_bonus)

                existing_for_kpi = list(DescuentoRetroactivoBono.objects.filter(
                    employee=self, kpi=kpi, origin_year=orig_year, origin_month=orig_month
                ))
                closed_deductions = []
                open_deductions = []
                for ded in existing_for_kpi:
                    is_closed = (
                        (ded.applied_year, ded.applied_month) != (apply_year, apply_month)
                        and self.recibos.filter(
                            year=ded.applied_year, month=ded.applied_month
                        ).exists()
                    )
                    if is_closed:
                        closed_deductions.append(ded)
                    else:
                        open_deductions.append(ded)

                already_deducted = sum((d.amount for d in closed_deductions), Decimal('0.00'))
                pending_amount = max(Decimal('0.00'), total_overpaid - already_deducted)

                if pending_amount > Decimal('0.00'):
                    if kpi.measurement_type == 'count_lt':
                        reason = (
                            f"{kpi.name} ({orig_month:02d}/{orig_year}): pasó de "
                            f"{_fmt_num(base_info['actual_value'])} a {_fmt_num(curr_info['actual_value'])} "
                            f"error(es) tras registro retroactivo"
                        )
                    elif kpi.measurement_type == 'composite_ipac':
                        reason = (
                            f"{kpi.name} ({orig_month:02d}/{orig_year}): índice bajó de "
                            f"{_fmt_num(base_info['actual_value'])} a {_fmt_num(curr_info['actual_value'])} "
                            f"(meta {_fmt_num(kpi.target_value)}) por error retroactivo"
                        )
                    else:
                        reason = f"{kpi.name} ({orig_month:02d}/{orig_year}): ajuste retroactivo de bono"

                    obj, _ = DescuentoRetroactivoBono.objects.update_or_create(
                        employee=self,
                        kpi=kpi,
                        origin_year=orig_year,
                        origin_month=orig_month,
                        applied_year=apply_year,
                        applied_month=apply_month,
                        defaults={
                            'amount': pending_amount,
                            'reason': reason,
                        },
                    )
                    for ded in open_deductions:
                        if ded.pk != obj.pk:
                            ded.delete()
                else:
                    for ded in open_deductions:
                        ded.delete()

    def calculate_salary(self, year, month):
        """
        Calculates the final salary for a given month and year, including base pay,
        overtime, performance bonus, sales commissions, and retroactive bonus deductions.
        Returns a dictionary with a detailed breakdown of the salary.
        """
        # Find the salary effective on the first day of the target month
        target_date = date(year, month, 1)
        salary_record = self.salaries.filter(
            effective_date__lte=target_date
        ).first()  # ordered by -effective_date, so first() = most recent
        if not salary_record:
            return None
        base_salary = salary_record.base_amount

        # Sincronizar cualquier descuento retroactivo pendiente antes de calcular
        self.sync_retroactive_bonus_deductions()

        # 1. Calculate pay from worked hours and overtime
        work_logs = WorkLog.objects.filter(employee=self, date__year=year, date__month=month)
        total_hours_worked = sum(log.hours_worked for log in work_logs)
        total_overtime_hours = sum(log.overtime_hours for log in work_logs)

        # Load company settings to determine the basis for salary calculation
        settings = CompanySettings.load()
        monthly_hours = Decimal('0.00')
        work_days_in_month = 0

        if settings.calculation_basis == 'monthly':
            monthly_hours = settings.base_hours
        elif settings.calculation_basis == 'weekly':
            # Approximate monthly hours by multiplying by the average number of weeks in a month
            monthly_hours = settings.base_hours * Decimal('4.333')
        elif settings.calculation_basis == 'daily':
            # Calculate the number of working days (Mon-Fri) in the given month and year
            import calendar
            cal = calendar.Calendar()
            for day in cal.itermonthdays2(year, month):
                if day[0] != 0 and day[1] < 5: # day[1] is the weekday (0=Mon, 6=Sun)
                    work_days_in_month += 1
            monthly_hours = settings.base_hours * Decimal(work_days_in_month)

        if monthly_hours <= 0:
             # Fallback to a default if hours are not set, to avoid division by zero
            monthly_hours = Decimal('160')

        hourly_rate = base_salary / monthly_hours
        overtime_rate = hourly_rate * Decimal(1.5)

        work_pay = total_hours_worked * hourly_rate
        overtime_pay = total_overtime_hours * overtime_rate

        # 2. Calculate performance bonus
        performance_bonus = self.calculate_performance_bonus(year, month)
        records_for_month = EmployeePerformanceRecord.objects.filter(
            employee=self, date__year=year, date__month=month
        )
        bonus_by_kpi = {str(r.kpi_id): r.bonus_awarded for r in records_for_month}

        # 3. Calculate sales commissions
        commissions = self.calculate_commissions(year, month)
        commission_amount = commissions['commission_amount']

        # 4. Calculate retroactive bonus deductions applicable to this month
        deductions_qs = DescuentoRetroactivoBono.objects.filter(
            employee=self, applied_year=year, applied_month=month
        ).select_related('kpi').order_by('origin_year', 'origin_month', 'kpi__name')
        retroactive_bonus_deduction = sum((d.amount for d in deductions_qs), Decimal('0.00'))
        retroactive_deductions = [
            {
                'id': d.id,
                'kpi_name': d.kpi.name,
                'origin_year': d.origin_year,
                'origin_month': d.origin_month,
                'origin_period': f"{d.origin_month:02d}/{d.origin_year}",
                'amount': d.amount,
                'reason': d.reason,
            }
            for d in deductions_qs
        ]

        # Informativo si este mes fue origen de descuentos aplicados en meses futuros
        origin_deductions_qs = DescuentoRetroactivoBono.objects.filter(
            employee=self, origin_year=year, origin_month=month
        ).select_related('kpi').order_by('applied_year', 'applied_month', 'kpi__name')
        retroactive_from_this_month = [
            {
                'id': d.id,
                'kpi_name': d.kpi.name,
                'applied_period': f"{d.applied_month:02d}/{d.applied_year}",
                'amount': d.amount,
                'reason': d.reason,
            }
            for d in origin_deductions_qs
        ]

        # 5. Calculate final total salary
        gross_salary = work_pay + overtime_pay + performance_bonus + commission_amount
        total_salary = max(Decimal('0.00'), gross_salary - retroactive_bonus_deduction)

        # 6. Return a detailed dictionary
        result = {
            'base_salary': base_salary,
            'work_pay': work_pay,
            'overtime_pay': overtime_pay,
            'performance_bonus': performance_bonus,
            'bonus_by_kpi': bonus_by_kpi,
            'commission_amount': commission_amount,
            'retroactive_bonus_deduction': retroactive_bonus_deduction,
            'retroactive_deductions': retroactive_deductions,
            'retroactive_from_this_month': retroactive_from_this_month,
            'total_salary': total_salary,
            'total_hours_worked': total_hours_worked,
            'total_overtime_hours': total_overtime_hours,
            'hourly_rate': hourly_rate,
            'overtime_rate': overtime_rate,
            'calculation_basis': settings.calculation_basis,
            'base_hours': settings.base_hours,
            'monthly_hours': monthly_hours,
            'work_days_in_month': work_days_in_month,
        }
        result.update(commissions)
        return result

class Salary(models.Model):
    """Represents a salary record for an employee with date-based history."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='salaries')
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    effective_date = models.DateField()

    class Meta:
        ordering = ['-effective_date']
        unique_together = ('employee', 'effective_date')
        verbose_name_plural = 'Salaries'

    def __str__(self):
        return f"{self.employee.name} - ${self.base_amount} (desde {self.effective_date})"

class WorkLog(models.Model):
    """Logs the hours worked and overtime for an employee on a specific day."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    hours_worked = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    ausencia = models.ForeignKey(
        'SolicitudAusencia', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='worklogs',
        help_text="Si el día proviene de una ausencia remunerada aprobada."
    )

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.name} on {self.date}"


def contar_dias_habiles(inicio, fin):
    """Días lunes-viernes en el rango [inicio, fin], ambos inclusive."""
    dias = 0
    dia = inicio
    while dia <= fin:
        if dia.weekday() < 5:
            dias += 1
        dia += timedelta(days=1)
    return dias


class TipoAusencia(models.Model):
    """Catálogo de tipos de ausencia (vacaciones, permiso médico, etc.)."""
    nombre = models.CharField(max_length=100, unique=True)
    descuenta_saldo = models.BooleanField(
        default=True, help_text="Si los días aprobados descuentan del saldo anual de vacaciones.")
    es_remunerada = models.BooleanField(
        default=True, help_text="Si los días aprobados se pagan (generan WorkLog de 8 horas).")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de ausencia"
        verbose_name_plural = "Tipos de ausencia"

    def __str__(self):
        return self.nombre


class SolicitudAusencia(models.Model):
    """Solicitud de vacaciones o permiso con flujo de aprobación."""
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
        ('CANCELADA', 'Cancelada'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='solicitudes_ausencia')
    tipo = models.ForeignKey(TipoAusencia, on_delete=models.PROTECT)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    dias_habiles = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    motivo = models.TextField(blank=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='PENDIENTE')
    decidida_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='ausencias_decididas')
    comentario_decision = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    decidida_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creada_en']
        verbose_name = "Solicitud de ausencia"
        verbose_name_plural = "Solicitudes de ausencia"

    def __str__(self):
        return f"{self.employee.name}: {self.tipo} {self.fecha_inicio} a {self.fecha_fin} ({self.get_estado_display()})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.fecha_fin and self.fecha_inicio and self.fecha_fin < self.fecha_inicio:
            raise ValidationError("La fecha de fin no puede ser anterior a la de inicio.")
        if self.employee_id and self.fecha_inicio and self.fecha_fin:
            solapadas = SolicitudAusencia.objects.filter(
                employee_id=self.employee_id,
                estado__in=['PENDIENTE', 'APROBADA'],
                fecha_inicio__lte=self.fecha_fin,
                fecha_fin__gte=self.fecha_inicio,
            ).exclude(pk=self.pk)
            if solapadas.exists():
                raise ValidationError(
                    "Ya existe una solicitud pendiente o aprobada que se solapa con esas fechas.")

    def save(self, *args, **kwargs):
        if self.fecha_inicio and self.fecha_fin:
            self.dias_habiles = Decimal(contar_dias_habiles(self.fecha_inicio, self.fecha_fin))
        super().save(*args, **kwargs)


class ReciboNomina(models.Model):
    """Snapshot inmutable de la liquidación mensual de un empleado.

    Se genera explícitamente al cierre de mes; el PDF se renderiza siempre
    desde `datos`, nunca recalculando, para que el histórico no cambie si
    cambian reglas de bonos/comisiones."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='recibos')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    datos = models.JSONField(help_text="Desglose completo de calculate_salary al momento de emisión.")
    total = models.DecimalField(max_digits=10, decimal_places=2)
    generado_en = models.DateTimeField(auto_now_add=True)
    generado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    dolibarr_salary_id = models.IntegerField(
        null=True, blank=True,
        help_text="rowid en llx_salary si el recibo ya fue enviado a Dolibarr.")
    dolibarr_synced_at = models.DateTimeField(null=True, blank=True)
    dolibarr_error = models.TextField(
        blank=True, default='',
        help_text="Último error al intentar el envío a Dolibarr; vacío si OK o nunca intentado.")

    class Meta:
        unique_together = ('employee', 'year', 'month')
        ordering = ['-year', '-month']
        verbose_name = "Recibo de nómina"
        verbose_name_plural = "Recibos de nómina"

    def __str__(self):
        return f"Recibo {self.employee.name} {self.year}-{self.month:02d} (${self.total})"

class SalesRecord(models.Model):
    """Tracks a sales event synced from Dolibarr."""
    STATUS_CHOICES = [
        ('proforma', 'Proforma/Proposal'),
        ('order', 'Pedido/Order'),
        ('invoiced', 'Facturado/Invoiced'),
        ('cancelled', 'Cancelado/Cancelled'),
        ('credit_note', 'Nota de Crédito/Credit Note'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='sales_records')
    dolibarr_instance = models.ForeignKey(DolibarrInstance, on_delete=models.CASCADE)
    dolibarr_id = models.IntegerField(help_text="RowID of the object in Dolibarr")
    dolibarr_ref = models.CharField(max_length=100, help_text="Reference (e.g., FA23-001)")

    origin_proforma_id = models.IntegerField(null=True, blank=True, help_text="RowID of the proforma")
    origin_order_id = models.IntegerField(null=True, blank=True, help_text="RowID of the order")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    amount_untaxed = models.DecimalField(max_digits=12, decimal_places=2, help_text="Base imponible (Total HT)")

    date = models.DateField(help_text="Date of validation or invoicing")
    payment_date = models.DateField(null=True, blank=True, help_text="Date when invoice was paid (set by PAYMENT_CUSTOMER_CREATE webhook)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('dolibarr_instance', 'dolibarr_id', 'status') # Prevent duplicate processing of same event type
        ordering = ['-date']

    def __str__(self):
        return f"{self.dolibarr_ref} - {self.status} ({self.amount_untaxed})"

class ProductCreationLog(models.Model):
    """Tracks product creations for the 'Product Creation' KPI to prevent fraud."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    dolibarr_instance = models.ForeignKey(DolibarrInstance, on_delete=models.CASCADE)
    dolibarr_product_id = models.IntegerField()
    product_ref = models.CharField(max_length=255, help_text="SKU/Ref of the product")
    created_at = models.DateTimeField()
    is_suspect_duplicate = models.BooleanField(
        default=False,
        help_text="Flagged if same SKU was already created this month (anti-fraud per FEASIBILITY_REPORT 3.2.C.4)"
    )

    class Meta:
        unique_together = ('dolibarr_instance', 'dolibarr_product_id')


class CommissionBalance(models.Model):
    """Tracks running commission balance for clawback.
    A negative balance means the employee has a debt from past credit notes
    that will be deducted from future commissions."""
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='commission_balance')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Running balance. Negative = debt to recover from future commissions.")
    pre_month_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Snapshot of balance BEFORE the current month's calculation. Used for idempotent recalculation.")
    last_computed_year = models.IntegerField(default=0)
    last_computed_month = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.employee.name}: ${self.balance}"


class WebhookLog(models.Model):
    """Raw log of incoming webhooks for audit and debugging."""
    received_at = models.DateTimeField(auto_now_add=True)
    sender_ip = models.GenericIPAddressField(null=True, blank=True)
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='pending') # pending, processed, error
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"Webhook {self.id} at {self.received_at} ({self.status})"


# --- Trello-like & Performance Management Models ---

class KPI(models.Model):
    """Key Performance Indicator."""
    name = models.CharField(max_length=255, help_text="E.g., Productividad General")
    description = models.TextField(blank=True, help_text="E.g., Porcentaje de tareas completadas a tiempo.")

    MEASUREMENT_CHOICES = [
        ('percentage', 'Percentage'),
        ('count_lt', 'Count (Less Than)'),
        ('count_gt', 'Count (Greater Than)'),
        ('composite_ipac', 'Composite IPAC'),
    ]
    measurement_type = models.CharField(max_length=20, choices=MEASUREMENT_CHOICES)

    
    # New fields for implementation
    INTERNAL_CODE_CHOICES = [
        ('', '(ninguno — usa measurement_type)'),
        ('SALES_EFFECTIVENESS', 'SALES_EFFECTIVENESS — Conversión proformas→facturas'),
        ('PRODUCT_CREATION', 'PRODUCT_CREATION — Productos creados (excluye duplicados)'),
    ]
    internal_code = models.SlugField(
        max_length=50, blank=True, null=True,
        choices=INTERNAL_CODE_CHOICES,
        help_text="Codigo interno que activa logica especial. Si esta vacio, se usa el measurement_type."
    )
    min_volume_threshold = models.IntegerField(default=0, help_text="Minimum volume of records required to trigger this KPI (e.g. 10 proformas)")
    
    target_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="E.g., 95 for percentage, 3 for count.")
    is_warning_kpi = models.BooleanField(default=False, help_text="Check if this KPI represents a disciplinary warning that should trigger an email.")

    def __str__(self):
        return self.name

class BonusRule(models.Model):
    """Rule that links a KPI to a bonus amount."""
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount of the bonus if the KPI target is met.")
    description = models.CharField(max_length=255, help_text="E.g., 'Completar >= 95% de las tareas'")

    def __str__(self):

        return f"{self.kpi.name} - ${self.bonus_amount}"

class KPIBonusTier(models.Model):
    """Defines tiered bonuses for a KPI (e.g. >90%: $50, >95%: $100)."""
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name='tiers')
    threshold = models.DecimalField(max_digits=10, decimal_places=2, help_text="Value required to reach this tier.")
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['threshold']

    def __str__(self):
        return f"{self.kpi.name} > {self.threshold}: ${self.bonus_amount}"


class TaskBoard(models.Model):
    """A board for an employee's tasks."""
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class TaskList(models.Model):
    """A list (column) on a task board."""
    board = models.ForeignKey(TaskBoard, related_name='lists', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, help_text="E.g., Pendiente, En Progreso, Hecho")
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.board.employee.name})"

class Task(models.Model):
    """A task (card) on a task list."""
    RECURRENCE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('unfulfilled', 'Unfulfilled'),
    ]

    list = models.ForeignKey(TaskList, related_name='tasks', on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(Employee, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks', null=True)
    kpi = models.ForeignKey(KPI, on_delete=models.SET_NULL, null=True, blank=True, help_text="The KPI this task contributes to.")

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField()
    due_date = models.DateTimeField(null=True, blank=True)  # Changed to DateTimeField
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending') # New status field
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by_manager = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    reminder_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Último aviso por email de vencimiento (idempotencia del cron diario).")

    # Recurrence fields
    is_recurring = models.BooleanField(default=False)
    recurrence_frequency = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, null=True, blank=True)
    recurrence_end_date = models.DateField(null=True, blank=True)

    # For tracking the chain of recurring tasks
    parent_task = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')


    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title

class Checklist(models.Model):
    """A checklist within a task."""
    task = models.ForeignKey(Task, related_name='checklists', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title

class ChecklistItem(models.Model):
    """An item in a checklist."""
    checklist = models.ForeignKey(Checklist, related_name='items', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.text

class Comment(models.Model):
    """A comment on a task."""
    task = models.ForeignKey(Task, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.task.title}"

class EmployeePerformanceRecord(models.Model):
    """A record of an employee's performance for a specific KPI in a given month."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE)
    date = models.DateField(help_text="The month and year this record applies to (e.g., 2024-08-31).")
    actual_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="The measured performance value.")
    target_met = models.BooleanField(default=False, help_text="Was the KPI target met for this period?")
    bonus_awarded = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('employee', 'kpi', 'date')

    def __str__(self):
        return f"{self.employee.name} - {self.kpi.name} - {self.date.strftime('%Y-%m')}"

class ManualKpiEntry(models.Model):
    """Represents a single, manually logged data point for a KPI."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, help_text="The KPI this entry is for, e.g., 'Calidad Administrativa'.")
    date = models.DateField(
        default=date.today,
        help_text="Fecha real en que ocurrió el evento/error. Si pertenece a un mes anterior ya cerrado, se descontará retroactivamente en el sueldo futuro."
    )
    value = models.DecimalField(max_digits=10, decimal_places=2, default=1, help_text="The value of the entry, e.g., '1' for one error.")
    notes = models.TextField(blank=True, help_text="Additional context or comments.")
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha y hora en que se registró el evento en el sistema."
    )

    @property
    def is_retroactive(self):
        """Indica si el evento se registró después del cierre del mes al que corresponde."""
        if not self.employee_id or not self.date or not self.created_at:
            return False
        cutoff = self.employee._period_closing_cutoff(self.date.year, self.date.month)
        return self.created_at > cutoff

    def save(self, *args, **kwargs):
        if self._state.adding and self.employee_id and self.date and self.created_at:
            cutoff = self.employee._period_closing_cutoff(self.date.year, self.date.month)
            if self.created_at > cutoff:
                already_evaluated = (
                    EmployeePerformanceRecord.objects.filter(
                        employee_id=self.employee_id,
                        date__year=self.date.year,
                        date__month=self.date.month,
                    ).exists()
                    or ReciboNomina.objects.filter(
                        employee_id=self.employee_id,
                        year=self.date.year,
                        month=self.date.month,
                    ).exists()
                )
                if not already_evaluated:
                    self.created_at = cutoff
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Entry for {self.employee.name} regarding {self.kpi.name} on {self.date}"


class DescuentoRetroactivoBono(models.Model):
    """
    Descuento retroactivo de bono por errores administrativos ('count_lt')
    detectados después de haberse cerrado/cobrado el mes de origen.
    El descuento se imputa al sueldo de un período futuro/abierto (applied_year, applied_month).
    """
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='descuentos_retroactivos',
        verbose_name="Empleado"
    )
    kpi = models.ForeignKey(
        KPI, on_delete=models.CASCADE, related_name='descuentos_retroactivos',
        verbose_name="KPI afectado"
    )
    origin_year = models.PositiveSmallIntegerField(verbose_name="Año de origen")
    origin_month = models.PositiveSmallIntegerField(verbose_name="Mes de origen")
    applied_year = models.PositiveSmallIntegerField(verbose_name="Año de descuento")
    applied_month = models.PositiveSmallIntegerField(verbose_name="Mes de descuento")
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Monto a descontar"
    )
    reason = models.TextField(blank=True, verbose_name="Motivo / Detalle")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-applied_year', '-applied_month', '-origin_year', '-origin_month', 'employee__name']
        unique_together = ('employee', 'kpi', 'origin_year', 'origin_month', 'applied_year', 'applied_month')
        verbose_name = "Descuento retroactivo de bono"
        verbose_name_plural = "Descuentos retroactivos de bonos"

    def __str__(self):
        return (
            f"{self.employee.name} — {self.kpi.name} "
            f"(origen {self.origin_month:02d}/{self.origin_year} → descuento {self.applied_month:02d}/{self.applied_year}): "
            f"-${self.amount}"
        )

class CompanySettings(models.Model):
    """Singleton model to store company-wide settings."""
    name = models.CharField(max_length=255, default="Default Settings", unique=True)

    CALCULATION_BASIS_CHOICES = [
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
    ]
    calculation_basis = models.CharField(
        max_length=10,
        choices=CALCULATION_BASIS_CHOICES,
        default='monthly',
        help_text="The basis for salary calculation (e.g., monthly, weekly, or daily hours)."
    )
    base_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=160.00,
        help_text="The number of base hours corresponding to the selected calculation basis."
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Enforce a single instance of settings
        self.pk = 1
        super(CompanySettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        # Convenience method to get the single settings object
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

class SiteConfiguration(models.Model):
    """Singleton model to store site-wide configuration, like the favicon."""
    favicon = models.ImageField(upload_to='favicons/', null=True, blank=True, help_text="Upload a custom favicon for the site.")

    def __str__(self):
        return "Site Configuration"

    def save(self, *args, **kwargs):
        # Enforce a single instance of settings
        self.pk = 1
        super(SiteConfiguration, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        # Convenience method to get the single settings object
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
