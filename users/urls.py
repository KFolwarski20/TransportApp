from django.urls import path
from datetime import date
from django.shortcuts import redirect
from .views import (
    menu_glowne_view, zarzadzaj_kierowcami, zarzadzaj_ciezarowkami,
    zarzadzaj_zleceniami, analiza_finansowa, register_view, login_view, logout_view,
    dodaj_kierowce, edytuj_kierowce, usun_kierowce, szczegoly_kierowcy, czas_kierowcy,
    dodaj_ciezarowke, szczegoly_ciezarowki, historia_serwisow, czas_ciezarowki, edytuj_ciezarowke, usun_ciezarowke,
    dodaj_zlecenie, edytuj_zlecenie, usun_zlecenie, przypisz_kierowce_ciezarowke,
    szczegoly_zlecenia, cofnij_status_zlecenia, zamknij_zlecenie, historia_zlecenia,
)

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("menu/", menu_glowne_view, name="menu_glowne"),
    path("kierowcy/", zarzadzaj_kierowcami, name="zarzadzaj_kierowcami"),
    path("kierowcy/dodaj/", dodaj_kierowce, name="dodaj_kierowce"),
    path("kierowcy/edytuj/<int:kier_id>/", edytuj_kierowce, name="edytuj_kierowce"),
    path("kierowcy/usun/<int:kier_id>/", usun_kierowce, name="usun_kierowce"),
    path("kierowcy/szczegoly/<int:kier_id>/", szczegoly_kierowcy, name="szczegoly_kierowcy"),
    path("kierowcy/czas_kierowcy/<int:kier_id>/<int:rok>/", czas_kierowcy, name="czas_kierowcy"),
    path("kierowcy/czas_kierowcy/<int:kier_id>/", lambda request, kier_id: redirect('czas_kierowcy', kier_id=kier_id, rok=date.today().year), name="czas_kierowcy_redirect"),
    path("ciezarowki/", zarzadzaj_ciezarowkami, name="zarzadzaj_ciezarowkami"),
    path("ciezarowki/dodaj/", dodaj_ciezarowke, name="dodaj_ciezarowke"),
    path("ciezarowki/szczegoly/<int:ciez_id>/", szczegoly_ciezarowki, name="szczegoly_ciezarowki"),
    path("ciezarowki/historia_serwisow/<int:ciez_id>/", historia_serwisow, name="historia_serwisow"),
    path("ciezarowki/czas_ciezarowki/<int:ciez_id>/<int:rok>/", czas_ciezarowki, name="czas_ciezarowki"),
    path("ciezarowki/czas_ciezarowki/<int:ciez_id>/", lambda request, ciez_id: redirect('czas_ciezarowki', ciez_id=ciez_id, rok=date.today().year), name="czas_ciezarowki_redirect"),
    path("ciezarowki/edytuj/<int:ciez_id>/", edytuj_ciezarowke, name="edytuj_ciezarowke"),
    path("ciezarowki/usun/<int:ciez_id>/", usun_ciezarowke, name="usun_ciezarowke"),
    path("zlecenia/", zarzadzaj_zleceniami, name="zarzadzaj_zleceniami"),
    path("zlecenia/dodaj/", dodaj_zlecenie, name="dodaj_zlecenie"),
    path("zlecenia/edytuj/<int:id_zlec>/", edytuj_zlecenie, name="edytuj_zlecenie"),
    path("zlecenia/usun/<int:id_zlec>/", usun_zlecenie, name="usun_zlecenie"),
    path("zlecenia/przypisz/<int:id_zlec>/", przypisz_kierowce_ciezarowke, name="przypisz_kierowce_ciezarowke"),
    path('zlecenia/<int:id_zlec>/szczegoly/', szczegoly_zlecenia, name='szczegoly_zlecenia'),
    path('zlecenia/<int:id_zlec>/cofnij_status/', cofnij_status_zlecenia, name='cofnij_status_zlecenia'),
    path('zlecenia/<int:id_zlec>/zamknij/', zamknij_zlecenie, name='zamknij_zlecenie'),
    path('zlecenia/<int:id_zlec>/historia/', historia_zlecenia, name='historia_zlecenia'),
    path("analiza/", analiza_finansowa, name="analiza_finansowa"),
]
