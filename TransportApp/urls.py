from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from users.views.zlecenie_views import get_available_kierowcy_ciezarowki

# Automatyczne przekierowanie na logowanie


def redirect_to_login(request):
    return redirect("login")  # Przekierowanie na stronę logowania


urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('', redirect_to_login, name='home'),  # Zmiana domyślnej strony na logowanie
    path("api/get_available_kierowcy_ciezarowki/<int:id_zlec>/", get_available_kierowcy_ciezarowki, name="get_available_kierowcy_ciezarowki"),
]
