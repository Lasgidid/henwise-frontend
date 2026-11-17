from django.conf import settings
from django.db import models
from django.utils import timezone


class Batch(models.Model):
    name = models.CharField(max_length=80)
    breed = models.CharField(max_length=80, blank=True)
    hatch_date = models.DateField()
    initial_count = models.PositiveIntegerField()
    active = models.BooleanField(default=True)

    @property
    def live_count(self):
        deaths = self.mortalities.aggregate(n=models.Sum("count"))["n"] or 0
        return max(0, self.initial_count - deaths)

    def __str__(self):
        return self.name


class EggCollection(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="collections")
    date = models.DateField(default=timezone.localdate)
    good = models.PositiveIntegerField(default=0)
    cracked = models.PositiveIntegerField(default=0)
    dirty = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-date", "-created_at"]


class FeedMovement(models.Model):
    REASONS = [(x, x.replace("_", " ").title()) for x in ("purchase", "return", "count_up", "fed", "spoiled", "spilled", "rodents", "sold", "transfer", "count_down")]
    date = models.DateField(default=timezone.localdate)
    feed_type = models.CharField(max_length=80)
    reason = models.CharField(max_length=20, choices=REASONS)
    kg = models.DecimalField(max_digits=10, decimal_places=1)
    batch = models.ForeignKey(Batch, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    @property
    def is_in(self): return self.reason in {"purchase", "return", "count_up"}


class Mortality(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="mortalities")
    date = models.DateField(default=timezone.localdate)
    count = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)


class VaccineSchedule(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="vaccines")
    name = models.CharField(max_length=120)
    due_date = models.DateField()
    given_on = models.DateField(null=True, blank=True)
    withdrawal_days = models.PositiveIntegerField(default=0)


class Transaction(models.Model):
    KIND = [("revenue", "Revenue"), ("expense", "Expense")]
    kind = models.CharField(max_length=10, choices=KIND)
    category = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.localdate)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)


class WaitlistEntry(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
