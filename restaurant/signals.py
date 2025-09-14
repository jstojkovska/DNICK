from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Reservation, Order, Table


@receiver(post_save, sender=Reservation)
def update_table_status_from_reservation(sender, instance, **kwargs):
    if instance.status == 'approved':
        instance.table.status = 'reserved'
        instance.table.save()
    elif instance.status == 'rejected':
        instance.table.status = 'available'
        instance.table.save()


@receiver(post_save, sender=Order)
def update_table_status_from_order(sender, instance, **kwargs):
    if instance.is_paid:
        instance.table.status = 'available'
    else:
        instance.table.status = 'occupied'
    instance.table.save()
