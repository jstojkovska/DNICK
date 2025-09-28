from rest_framework import serializers
from .models import Reservation, Table, Order, MenuItem, OrderItem, Zone

class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = '__all__'

class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = '__all__'

class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_detail = MenuItemSerializer(source='menu_item', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'menu_item', 'quantity', 'menu_item_detail']
        read_only_fields = ['order']

class OrderCreateItemInSerializer(serializers.Serializer):
    menu_item = serializers.PrimaryKeyRelatedField(queryset=MenuItem.objects.all())
    quantity = serializers.IntegerField(min_value=1)

class OrderSerializer(serializers.ModelSerializer):
    orderitem_set = OrderItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'table', 'is_paid', 'created_at', 'orderitem_set', 'total']

    def get_total(self, obj):
        return obj.total_price()

class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderCreateItemInSerializer(many=True, write_only=True)

    class Meta:
        model = Order
        fields = ['id', 'table', 'items']

    def create(self, validated_data):
        items = validated_data.pop('items', [])
        order = Order.objects.create(**validated_data)
        bulk = [
            OrderItem(order=order, menu_item=it['menu_item'], quantity=it['quantity'])
            for it in items
        ]
        if bulk:
            OrderItem.objects.bulk_create(bulk)
        return order

class ReservationSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = Reservation
        fields = ['id', 'table', 'datetime', 'description', 'status', 'user_username']
        read_only_fields = ['status', 'user_username']

    def create(self, validated_data):
        validated_data['status'] = 'pending'
        return super().create(validated_data)

class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = '__all__'
