from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .forms import CustomUserCreationForm, CustomUserChangeForm

from .models import User, Table, MenuItem, Reservation, Order, OrderItem


class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role Info', {'fields': ('role',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'role', 'password1', 'password2'),
        }),
    )


class TableAdmin(admin.ModelAdmin):

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return False

    def has_delete_permission(self, request, obj=...):
        if request.user.is_superuser:
            return True
        return False


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('id', 'table', 'is_paid', 'created_at')
    list_filter = ('is_paid',)
    search_fields = ('table__number',)


class ReservationAdmin(admin.ModelAdmin):
    list_display = ('user', 'table', 'datetime', 'status')
    list_filter = ('status', 'datetime')
    search_fields = ('user__username',)


class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "item_type", "price")
    search_fields = ("code", "name")
    list_filter = ("item_type",)


admin.site.register(User, UserAdmin)
admin.site.register(Table, TableAdmin)
admin.site.register(MenuItem, MenuItemAdmin)
admin.site.register(Reservation, ReservationAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem)
