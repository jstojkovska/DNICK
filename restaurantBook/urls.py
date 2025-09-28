# Update your restaurantBook/urls.py file

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from restaurant.views import (
    ReservationViewSet, TableViewSet, MenuItemViewSet, 
    OrderViewSet, MeView, ZoneViewSet, register_user
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

router = DefaultRouter()
router.register(r'reservations', ReservationViewSet)
router.register(r'tables', TableViewSet, basename='table')
router.register(r'menu-items', MenuItemViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'zones', ZoneViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/register/', register_user, name='register'),  # New registration endpoint
    path('api/', include(router.urls)),
    path("api/me/", MeView.as_view(), name="me")
]