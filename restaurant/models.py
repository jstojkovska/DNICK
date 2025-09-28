from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import ForeignKey, UniqueConstraint, Q
from django.core.exceptions import ValidationError


class User(AbstractUser):
    ROLE_CHOICES = (
        ('client', 'Client'),
        ('waiter', 'Waiter'),
        ('manager', 'Manager')
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)


class Table(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('occupied', 'Occupied')
    )
    number = models.PositiveIntegerField(unique=True)
    chairs = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    top = models.FloatField()
    left = models.FloatField()

    def __str__(self):
        return f'Table {self.number}'


class Reservation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    datetime = models.DateTimeField()
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    def __str__(self):
        return f'Reservation by {self.user.username} on {self.datetime}'

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['table', 'datetime'],
                condition=Q(status='approved'),
                name='uniq_table_datetime_when_approved'
            )
        ]


class MenuItem(models.Model):
    ITEM_TYPE_CHOICES = (
        ('food', 'Food'),
        ('drink', 'Drink')
    )
    name = models.CharField(max_length=100)
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES)
    price = models.IntegerField()
    code = models.CharField(max_length=30, unique=True, db_index=True)

    def __str__(self):
        return f'{self.name} {self.item_type}'

class Order(models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    menu_items = models.ManyToManyField(MenuItem, through='OrderItem')
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_price(self):
        return sum(oi.menu_item.price * oi.quantity for oi in self.orderitem_set.all())

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['table'],
                condition=Q(is_paid=False),
                name='uniq_active_order_per_table'
            )
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    def clean(self):
        if self.quantity < 1:
            raise ValidationError("Количината мора да биде барем 1.")

class Zone(models.Model):
    ZONE_TYPE_CHOICES = (
        ('glass', 'Glass'),
        ('terrace', 'Terrace'),
        ('green', 'Green Area'),
    )

    type = models.CharField(max_length=20, choices=ZONE_TYPE_CHOICES)
    top = models.FloatField(default=0)
    left = models.FloatField(default=0)
    width = models.FloatField(default=200)
    height = models.FloatField(default=100)

    def __str__(self):
        return f'{self.get_type_display()} zone ({self.width}x{self.height})'

