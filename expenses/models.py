import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class OperatingExpense(models.Model):
    """Standalone operating costs (rent, utilities, salaries, etc.)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted"
        VOIDED = "VOIDED", "Voided"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense_no = models.CharField(max_length=32, unique=True, blank=True)
    category = models.ForeignKey(
        "purchases.ExpenseCategory", on_delete=models.PROTECT, related_name="operating_expenses"
    )
    expense_date = models.DateField()
    currency = models.CharField(max_length=3, default="USD")
    exchange_rate_to_usd = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="USD = amount × rate when currency is not USD.",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount_usd = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="posted_operating_expenses",
    )
    void_reason = models.TextField(blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]

    def __str__(self):
        return self.expense_no or str(self.pk)

    def recalc_usd(self):
        if (self.currency or "USD").upper() == "USD":
            self.amount_usd = (self.amount or Decimal("0")).quantize(Decimal("0.01"))
        elif self.exchange_rate_to_usd and self.exchange_rate_to_usd > 0:
            self.amount_usd = ((self.amount or Decimal("0")) * self.exchange_rate_to_usd).quantize(Decimal("0.01"))
        else:
            self.amount_usd = Decimal("0.00")

    def post(self, user=None):
        from django.utils import timezone

        if self.status != self.Status.DRAFT:
            raise ValueError("Only draft expenses can be posted.")
        if (self.currency or "USD").upper() != "USD" and not self.exchange_rate_to_usd:
            raise ValueError("Exchange rate is required for non-USD expenses.")
        self.recalc_usd()
        if not self.expense_no or self.expense_no.startswith("TMP-"):
            from accounts_core.models import DocumentSequence

            self.expense_no = DocumentSequence.next_value("OPEX", "OPEX-", self.expense_date.year)
        self.status = self.Status.POSTED
        self.posted_by = user
        self.posted_at = timezone.now()
        self.save()


class OperatingExpenseAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(OperatingExpense, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="expense_attachments/%Y/%m/")
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]


class EmployeeSalaryEntry(models.Model):
    """Monthly payroll row per employee — not an expense until payment is posted."""

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        PARTIAL = "PARTIAL", "Partially paid"
        SETTLED = "SETTLED", "Settled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        "accounts_core.Employee", on_delete=models.CASCADE, related_name="salary_entries"
    )
    period_year = models.PositiveSmallIntegerField()
    period_month = models.PositiveSmallIntegerField()
    base_salary = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    bonus = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Extra pay for this month (commission, bonus, etc.).",
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_year", "-period_month", "employee__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "period_year", "period_month"],
                name="uniq_employee_salary_period",
            ),
        ]

    def __str__(self):
        return f"{self.employee.name} {self.period_year}-{self.period_month:02d}"


class EmployeeSalaryPayment(models.Model):
    """One salary payment → one posted operating expense."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(EmployeeSalaryEntry, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField()
    operating_expense = models.OneToOneField(
        OperatingExpense,
        on_delete=models.PROTECT,
        related_name="salary_payment",
    )
    notes = models.TextField(blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="salary_payments_posted",
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-posted_at"]


class UpcomingExpenseType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("name"), name="unique_upcoming_expense_type_name",
            ),
        ]

    def __str__(self):
        return self.name


class UpcomingExpensePlan(models.Model):
    class Frequency(models.TextChoices):
        ONCE = "once", "One time"
        MONTHLY = "monthly", "Monthly"

    payment_type = models.ForeignKey(UpcomingExpenseType, on_delete=models.PROTECT)
    description = models.TextField(blank=True)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.ONCE)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_date", "pk"]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="upcoming_plan_positive_amount"),
            models.CheckConstraint(check=models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F("start_date")), name="upcoming_plan_valid_end"),
        ]

    def __str__(self):
        return f"{self.payment_type} — {self.amount} USD"


class UpcomingExpensePayment(models.Model):
    plan = models.ForeignKey(UpcomingExpensePlan, on_delete=models.PROTECT, related_name="payments")
    payment_type = models.ForeignKey(UpcomingExpenseType, on_delete=models.PROTECT)
    description = models.TextField(blank=True)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
    )
    scheduled_for = models.DateField(help_text="Original installment date; not changed when a due date is edited.")
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    is_deleted = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "scheduled_for"], name="unique_upcoming_expense_installment"),
            models.CheckConstraint(check=models.Q(amount__gt=0), name="upcoming_payment_positive_amount"),
            models.CheckConstraint(check=models.Q(amount_paid__gte=0, amount_paid__lte=models.F("amount")), name="upcoming_paid_within_amount"),
        ]

    @property
    def balance(self):
        return self.amount - self.amount_paid

    def __str__(self):
        return f"{self.payment_type} — {self.due_date}"


class UpcomingExpenseReceipt(models.Model):
    request_id = models.UUIDField(null=True, blank=True, unique=True)
    payment = models.ForeignKey(UpcomingExpensePayment, on_delete=models.PROTECT, related_name="receipts")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    recorded_at = models.DateTimeField(auto_now_add=True)
    is_reversed = models.BooleanField(default=False)
