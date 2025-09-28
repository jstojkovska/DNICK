from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction, IntegrityError
from django.db.models import Prefetch
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Reservation, Table, MenuItem, OrderItem, Order, Zone
from .permissions import IsManager, IsClient, IsManagerOrWaiter, MenuitemPermission
from .serializers import (
    ReservationSerializer, TableSerializer, MenuItemSerializer,
    OrderSerializer, OrderCreateSerializer, ZoneSerializer
)
def _fresh_order(order_id: int) -> Order:
    return (
        Order.objects
        .select_related('table')
        .prefetch_related(Prefetch('orderitem_set', queryset=OrderItem.objects.select_related('menu_item')))
        .get(pk=order_id)
    )
class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsManager])
    def approve(self, request, pk=None):
        reservation = self.get_object()

        exists = Reservation.objects.filter(
            table=reservation.table,
            datetime=reservation.datetime,
            status='approved'
        ).exclude(pk=reservation.pk).exists()

        if exists:
            return Response({"detail": "There is already an approved reservation for that table and time."},
                            status=status.HTTP_400_BAD_REQUEST)

        reservation.status = 'approved'
        reservation.save()
        return Response({"detail": "Reservation is approved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsManager])
    def reject(self, request, pk=None):
        reservation = self.get_object()
        reservation.status = 'rejected'
        reservation.save()
        return Response({"detail": "Reservation is rejected."}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        user = self.request.user
        table = serializer.validated_data['table']
        dt = serializer.validated_data['datetime']

        if Reservation.objects.filter(table=table, datetime=dt, status='approved').exists():
            raise ValidationError("The date is already booked.")

        serializer.save(user=user, status='pending')

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.role == 'client':
            qs = qs.filter(user=user)
        elif user.role in ['manager', 'waiter']:
            pass
        else:
            qs = qs.none()

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        return qs

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsClient()]
        return [IsAuthenticated()]

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        u = request.user
        return Response({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": getattr(u, "role", None),
        })

class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    permission_classes = [IsAuthenticated,MenuitemPermission]


class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.all()
    serializer_class = TableSerializer

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsManagerOrWaiter])
    def status(self, request):

        tables = Table.objects.all()
        orders = (
            Order.objects.filter(is_paid=False)
            .prefetch_related('orderitem_set__menu_item')
        )
        active_by_table = {o.table_id: o for o in orders}

        data = []
        for t in tables:
            row = TableSerializer(t).data
            o = active_by_table.get(t.id)
            if o:
                row['active_order'] = {
                    'order_id': o.id,
                    'items_count': o.orderitem_set.count(),
                    'total': o.total_price(),
                }
            else:
                row['active_order'] = None
            data.append(row)
        return Response(data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsManagerOrWaiter])
    def seat(self, request, pk=None):
        table = self.get_object()
        table.status = 'occupied'
        table.save()
        return Response({"detail": "Guests seated. Table is now occupied."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsManagerOrWaiter])
    def free(self, request, pk=None):
        table = self.get_object()
        has_unpaid = Order.objects.filter(table=table, is_paid=False).exists()
        if has_unpaid:
            return Response({"detail": "Table has an active unpaid order."}, status=status.HTTP_400_BAD_REQUEST)
        table.status = 'available'
        table.save()
        return Response({"detail": "Table is now available."}, status=status.HTTP_200_OK)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().select_related('table').prefetch_related('orderitem_set__menu_item')
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsManagerOrWaiter]

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()
        if user.role in ['waiter', 'manager']:
            return super().get_queryset()
        return Order.objects.none()

    def perform_create(self, serializer):
        table = serializer.validated_data['table']
        if table.status == 'reserved':
            raise ValidationError("Table is reserved. Seat the guests first.")
        try:
            order = serializer.save()
            return order
        except IntegrityError:
            raise ValidationError("There is already an active order for this table.")

    def _ensure_not_paid(self, order: Order):
        if order.is_paid:
            raise ValidationError("The order has already been paid for.")

    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        order = self.get_object()
        self._ensure_not_paid(order)

        menu_item_id = request.data.get('menu_item')
        qty = int(request.data.get('quantity', 1))
        if qty < 1:
            raise ValidationError("The quantity must be at least 1.")

        try:
            mi = MenuItem.objects.get(pk=menu_item_id)
        except MenuItem.DoesNotExist:
            raise ValidationError("Non-existing item.")

        oi, created = OrderItem.objects.get_or_create(
            order=order, menu_item=mi, defaults={'quantity': qty}
        )
        if not created:
            oi.quantity += qty
            oi.save()

        fresh = _fresh_order(order.id)
        return Response(OrderSerializer(fresh).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def set_item_qty(self, request, pk=None):
        order = self.get_object()
        self._ensure_not_paid(order)

        oi_id = request.data.get('order_item_id')
        qty = int(request.data.get('quantity', 1))
        if qty < 1:
            raise ValidationError("The quantity must be at least 1.")

        try:
            oi = OrderItem.objects.get(pk=oi_id, order=order)
        except OrderItem.DoesNotExist:
            raise ValidationError("The item does not exist for this order.")

        oi.quantity = qty
        oi.save()

        fresh = _fresh_order(order.id)
        return Response(OrderSerializer(fresh).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def remove_item(self, request, pk=None):
        order = self.get_object()
        self._ensure_not_paid(order)

        oi_id = request.data.get('order_item_id')
        try:
            oi = OrderItem.objects.get(pk=oi_id, order=order)
        except OrderItem.DoesNotExist:
            raise ValidationError("The item does not exist for this order.")

        oi.delete()

        fresh = _fresh_order(order.id)
        return Response(OrderSerializer(fresh).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.get_object()
        self._ensure_not_paid(order)

        with transaction.atomic():
            order.is_paid = True
            order.save()
        return Response({"detail": "The payment has been recorded."}, status=status.HTTP_200_OK)

class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer


User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):

    data = request.data

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password1 = data.get('password1', '')
    password2 = data.get('password2', '')
    role = data.get('role', 'client')

    errors = {}

    if not username:
        errors['username'] = ['Username is required']
    elif len(username) < 3:
        errors['username'] = ['Username must be at least 3 characters']
    elif User.objects.filter(username=username).exists():
        errors['username'] = ['Username already exists']

    if not email:
        errors['email'] = ['Email is required']
    elif '@' not in email or '.' not in email:
        errors['email'] = ['Please enter a valid email address']
    elif User.objects.filter(email=email).exists():
        errors['email'] = ['Email already exists']

    if not password1:
        errors['password1'] = ['Password is required']
    elif len(password1) < 6:
        errors['password1'] = ['Password must be at least 6 characters']

    if not password2:
        errors['password2'] = ['Password confirmation is required']
    elif password1 != password2:
        errors['password2'] = ['Passwords do not match']

    if role not in ['client', 'waiter', 'manager']:
        errors['role'] = ['Invalid role selected']

    if password1 and not errors.get('password1'):
        try:
            validate_password(password1)
        except ValidationError as e:
            errors['password1'] = list(e.messages)

    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                role=role
            )

        return Response({
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        }, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response({
            'non_field_errors': ['User with this username or email already exists']
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'non_field_errors': ['Registration failed. Please try again.']
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)