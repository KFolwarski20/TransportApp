from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from .forms import RegisterForm, LoginForm, KierowcaForm, CiezarowkaForm, ZlecenieForm, SerwisForm
from .models import Kierowca, Ciezarowka, Zlecenie, Serwis
import openrouteservice
from geopy.geocoders import Nominatim
from datetime import date, datetime, timedelta
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q, F, Sum, ExpressionWrapper, DurationField
from statistics import mean, median, stdev
import json
from django.conf import settings
import requests


User = get_user_model()  # Pobiera poprawny model użytkownika

ORS_API_KEY = "5b3ce3597851110001cf62485a5adc7a079347dbb10ae922b01de893"


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.save()  # Zapisanie użytkownika do bazy danych
            login(request, user)  # Automatyczne logowanie po rejestracji
            return redirect("home")  # Przekierowanie na stronę główną
    else:
        form = RegisterForm()
    return render(request, "users/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("menu_glowne")  # Przekierowanie do Menu Głównego
    else:
        form = LoginForm()
    return render(request, "users/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


def get_route_geometry(start, end):
    """ Pobiera geometrię trasy między dwoma punktami """
    client = openrouteservice.Client(key=ORS_API_KEY)
    try:
        routes = client.directions(coordinates=[start, end], profile="driving-car", format="geojson")
        return routes["features"][0]["geometry"]["coordinates"]
    except Exception as e:
        print("❌ Błąd OpenRouteService:", str(e))
        return None


def oblicz_odleglosc(miejsce_odbioru, miejsce_dostawy):
    geolocator = Nominatim(user_agent="transport_app")

    lokalizacja_odbioru = geolocator.geocode(miejsce_odbioru)
    if not lokalizacja_odbioru:
        raise ValueError("Nie można znaleźć lokalizacji miejsca odbioru!")

    lokalizacja_dostawy = geolocator.geocode(miejsce_dostawy)
    if not lokalizacja_dostawy:
        raise ValueError("Nie można znaleźć lokalizacji miejsca dostawy!")

    # Współrzędne (lon, lat)
    wsp_odbioru = [lokalizacja_odbioru.longitude, lokalizacja_odbioru.latitude]
    wsp_dostawy = [lokalizacja_dostawy.longitude, lokalizacja_dostawy.latitude]

    # Utwórz klienta OpenRouteService
    client = openrouteservice.Client(key=ORS_API_KEY)

    # Wyznaczanie trasy
    routes = client.directions(coordinates=[wsp_odbioru, wsp_dostawy], profile='driving-car')

    # Odległość w metrach
    odleglosc_m = routes['routes'][0]['summary']['distance']

    # Zamień na kilometry
    odleglosc_km = odleglosc_m / 1000.0
    czas_sekundy = routes['routes'][0]['summary']['duration']  # sekundy

    return round(odleglosc_km, 2), wsp_odbioru, wsp_dostawy, czas_sekundy


@login_required
def menu_glowne_view(request):
    return render(request, "users/menu_glowne.html")


@login_required
def zarzadzaj_kierowcami(request):
    kierowcy = Kierowca.objects.all()
    return render(request, "users/zarzadzanie/zarzadzaj_kierowcami.html", {"kierowcy": kierowcy})


@login_required
def zarzadzaj_ciezarowkami(request):
    return render(request, "users/zarzadzanie/zarzadzaj_ciezarowkami.html")


@login_required
def zarzadzaj_zleceniami(request):
    return render(request, "users/zarzadzanie/zarzadzaj_zleceniami.html")


@login_required
def analiza_finansowa(request):
    return render(request, "users/analiza_finansowa.html")


@login_required
def dodaj_kierowce(request):
    if request.method == "POST":
        form = KierowcaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("zarzadzaj_kierowcami")
    else:
        form = KierowcaForm()
    return render(request, "users/kierowcy/dodaj_kierowce.html", {"form": form})


@login_required
def edytuj_kierowce(request, kier_id):
    kierowca = get_object_or_404(Kierowca, pk=kier_id)
    if request.method == "POST":
        form = KierowcaForm(request.POST, instance=kierowca)
        if form.is_valid():
            form.save()
            return redirect("zarzadzaj_kierowcami")
    else:
        form = KierowcaForm(instance=kierowca)
    return render(request, "users/kierowcy/edytuj_kierowce.html", {"form": form, "kierowca": kierowca})


@login_required
def usun_kierowce(request, kier_id):
    kierowca = get_object_or_404(Kierowca, pk=kier_id)
    if request.method == "POST":
        kierowca.delete()
        return redirect("zarzadzaj_kierowcami")
    return render(request, "users/kierowcy/usun_kierowce.html", {"kierowca": kierowca})


@login_required
def szczegoly_kierowcy(request, kier_id):
    kierowca = get_object_or_404(Kierowca, pk=kier_id)
    return render(request, "users/kierowcy/szczegoly_kierowcy.html", {"kierowca": kierowca})


@login_required
def czas_kierowcy(request, kier_id, rok=2025):
    kierowca = get_object_or_404(Kierowca, pk=kier_id)
    if rok is None:
        rok = datetime.now().year

    zlecenia = Zlecenie.objects.filter(
        status="zamkniete",
        kierowca=kierowca,
        rzeczywista_data_zakonczenia__year=rok
    )

    miesiace = [f"{rok}-{str(m).zfill(2)}" for m in range(1, 13)]
    godziny_miesiac = {m: 0 for m in miesiace}
    historia = {m: [] for m in miesiace}

    for z in zlecenia:
        if z.rzeczywista_data_rozpoczecia and z.rzeczywista_data_zakonczenia:
            czas_trwania = (z.rzeczywista_data_zakonczenia - z.rzeczywista_data_rozpoczecia).total_seconds() / 3600
            miesiac_klucz = z.rzeczywista_data_zakonczenia.strftime("%Y-%m")
            godziny_miesiac[miesiac_klucz] += czas_trwania
            historia[miesiac_klucz].append({
                "numer_zlecenia": z.numer_zlecenia,
                "miejsce_odb": z.miejsce_odb,
                "miejsce_dost": z.miejsce_dost,
                "godziny": czas_trwania
            })

    context = {
        "kierowca": kierowca,
        "rok": rok,
        "miesiace_labels": json.dumps(miesiace),
        "godziny_labels": json.dumps([round(godziny_miesiac[m], 2) for m in miesiace]),
        "historia": historia
    }
    return render(request, "users/kierowcy/czas_kierowcy.html", context)


@login_required
def zarzadzaj_ciezarowkami(request):
    ciezarowki = Ciezarowka.objects.all()
    return render(request, "users/zarzadzanie/zarzadzaj_ciezarowkami.html", {"ciezarowki": ciezarowki})


@login_required
def dodaj_ciezarowke(request):
    if request.method == "POST":
        form = CiezarowkaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('zarzadzaj_ciezarowkami')
    else:
        form = CiezarowkaForm()
    return render(request, "users/ciezarowki/dodaj_ciezarowke.html", {"form": form})


@login_required
def szczegoly_ciezarowki(request, ciez_id):
    ciezarowka = get_object_or_404(Ciezarowka, ciez_id=ciez_id)
    return render(request, "users/ciezarowki/szczegoly_ciezarowki.html", {"ciezarowka": ciezarowka})


@login_required
def historia_serwisow(request, ciez_id):
    ciezarowka = get_object_or_404(Ciezarowka, pk=ciez_id)
    serwisy = Serwis.objects.filter(ciezarowka=ciezarowka).order_by('-data')

    form = SerwisForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            serwis = form.save(commit=False)
            serwis.ciezarowka = ciezarowka
            serwis.save()
            messages.success(request, "Dodano wpis serwisowy.")
            return redirect('historia_serwisow', ciez_id=ciez_id)
        else:
            messages.error(request, "Formularz zawiera błędy. Popraw je i spróbuj ponownie.")

    return render(request, 'users/ciezarowki/historia_serwisow.html', {
        'ciezarowka': ciezarowka,
        'serwisy': serwisy,
        'form': form
    })


@login_required
def czas_ciezarowki(request, ciez_id, rok=2025):
    ciezarowka = get_object_or_404(Ciezarowka, pk=ciez_id)
    if rok is None:
        rok = datetime.now().year

    zlecenia = Zlecenie.objects.filter(
        status="zamkniete",
        ciezarowka=ciezarowka,
        rzeczywista_data_zakonczenia__year=rok
    )

    miesiace = [f"{rok}-{str(m).zfill(2)}" for m in range(1, 13)]
    godziny_miesiac = {m: 0 for m in miesiace}
    historia = {m: [] for m in miesiace}

    for z in zlecenia:
        if z.rzeczywista_data_rozpoczecia and z.rzeczywista_data_zakonczenia:
            czas_trwania = (z.rzeczywista_data_zakonczenia - z.rzeczywista_data_rozpoczecia).total_seconds() / 3600
            miesiac_klucz = z.rzeczywista_data_zakonczenia.strftime("%Y-%m")
            godziny_miesiac[miesiac_klucz] += czas_trwania
            historia[miesiac_klucz].append({
                "numer_zlecenia": z.numer_zlecenia,
                "miejsce_odb": z.miejsce_odb,
                "miejsce_dost": z.miejsce_dost,
                "godziny": czas_trwania
            })

    context = {
        "ciezarowka": ciezarowka,
        "rok": rok,
        "miesiace_labels": json.dumps(miesiace),
        "godziny_labels": json.dumps([round(godziny_miesiac[m], 2) for m in miesiace]),
        "historia": historia
    }
    return render(request, "users/ciezarowki/czas_ciezarowki.html", context)


@login_required
def edytuj_ciezarowke(request, ciez_id):
    ciezarowka = get_object_or_404(Ciezarowka, ciez_id=ciez_id)
    if request.method == "POST":
        form = CiezarowkaForm(request.POST, instance=ciezarowka)
        if form.is_valid():
            form.save()
            return redirect('zarzadzaj_ciezarowkami')
    else:
        form = CiezarowkaForm(instance=ciezarowka)
    return render(request, "users/ciezarowki/edytuj_ciezarowke.html", {"form": form})


@login_required
def usun_ciezarowke(request, ciez_id):
    ciezarowka = get_object_or_404(Ciezarowka, ciez_id=ciez_id)
    if request.method == "POST":
        ciezarowka.delete()
        return redirect('zarzadzaj_ciezarowkami')
    return render(request, "users/ciezarowki/usun_ciezarowke.html", {"ciezarowka": ciezarowka})


@login_required
def zarzadzaj_zleceniami(request):
    zlecenia_nie_rozpoczete = Zlecenie.objects.filter(status='nie_rozpoczete')
    zlecenia_w_realizacji = Zlecenie.objects.filter(status='w_realizacji')
    zlecenia_zamkniete = Zlecenie.objects.filter(status='zamkniete')

    context = {
        'zlecenia_nie_rozpoczete': zlecenia_nie_rozpoczete,
        'zlecenia_w_realizacji': zlecenia_w_realizacji,
        'zlecenia_zamkniete': zlecenia_zamkniete,
    }
    return render(request, 'users/zarzadzanie/zarzadzaj_zleceniami.html', context)


@login_required
def dodaj_zlecenie(request):
    if request.method == 'POST':
        form = ZlecenieForm(request.POST)
        if form.is_valid():
            zlecenie = form.save(commit=False)
            zlecenie.status = 'nie_rozpoczete'  # Ustawienie domyślnego statusu
            zlecenie.save()
            return redirect("zarzadzaj_zleceniami")
    else:
        form = ZlecenieForm()

    return render(request, "users/zlecenia/dodaj_zlecenie.html", {"form": form})


@login_required
def edytuj_zlecenie(request, id_zlec):
    zlecenie = get_object_or_404(Zlecenie, pk=id_zlec)
    if request.method == "POST":
        form = ZlecenieForm(request.POST, instance=zlecenie)
        if form.is_valid():
            form.save()
            return redirect("zarzadzaj_zleceniami")
    else:
        form = ZlecenieForm(instance=zlecenie)
    return render(request, "users/zlecenia/edytuj_zlecenie.html", {"form": form, "zlecenie": zlecenie})


@login_required
def usun_zlecenie(request, id_zlec):
    zlecenie = get_object_or_404(Zlecenie, pk=id_zlec)
    if request.method == "POST":
        zlecenie.delete()
        return redirect("zarzadzaj_zleceniami")
    return render(request, "users/zlecenia/usun_zlecenie.html", {"zlecenie": zlecenie})


@login_required
def przypisz_kierowce_ciezarowke(request, id_zlec):
    """Widok przypisywania kierowcy i ciężarówki do zlecenia."""
    zlecenie = get_object_or_404(Zlecenie, pk=id_zlec)
    error_message = None
    zlecenie.odleglosc_km, start_coords, end_coords, czas_trasy_sek = oblicz_odleglosc(zlecenie.miejsce_odb, zlecenie.miejsce_dost)
    zlecenie.save()

    odleglosc = float(zlecenie.odleglosc_km or 0)
    route_geometry = get_route_geometry(start_coords, end_coords) if start_coords and end_coords else None
    CENA_PALIWA_ZA_LITR = 6.26
    laczny_koszt = None

    if request.method == "POST":
        kierowca_id = request.POST.get("kierowca")
        ciezarowka_id = request.POST.get("ciezarowka")
        data_rozpoczecia_str = request.POST.get("data_rozpoczecia_realizacji")

        if kierowca_id and ciezarowka_id and data_rozpoczecia_str:
            kierowca = get_object_or_404(Kierowca, pk=kierowca_id)
            ciezarowka = get_object_or_404(Ciezarowka, pk=ciezarowka_id)
            data_rozpoczecia_realizacji = parse_datetime(data_rozpoczecia_str)

            if data_rozpoczecia_realizacji and timezone.is_naive(data_rozpoczecia_realizacji):
                data_rozpoczecia_realizacji = timezone.make_aware(data_rozpoczecia_realizacji)

            # 🛠️ Walidacja daty - czy nie jest wcześniejsza niż dzisiejsza
            if data_rozpoczecia_realizacji < timezone.now():
                messages.error(request, "Data rozpoczęcia realizacji nie może być wcześniejsza niż dzisiejsza!")
            else:
                # 🛠️ Koszt obliczamy na podstawie wartości z API (zamiast powtarzać obliczenia)
                koszt_kierowcy = float(kierowca.stawka_za_km) * odleglosc
                koszt_paliwa = float(ciezarowka.ciez_spalanie_na_100km) * (odleglosc / 100) * CENA_PALIWA_ZA_LITR
                przewidywany_koszt = round(koszt_kierowcy + koszt_paliwa, 2)

                przewidywany_czas = timedelta(seconds=czas_trasy_sek)
                przewidywana_data_zakonczenia = data_rozpoczecia_realizacji + przewidywany_czas

                if 'confirm' in request.POST:
                    zlecenie.kierowca = kierowca
                    zlecenie.ciezarowka = ciezarowka
                    zlecenie.status = 'w_realizacji'
                    zlecenie.przewidywana_data_rozpoczecia = data_rozpoczecia_realizacji
                    zlecenie.przewidywany_czas_realizacji = przewidywany_czas
                    zlecenie.przewidywana_data_zakonczenia = przewidywana_data_zakonczenia
                    zlecenie.przewidywany_koszt = przewidywany_koszt
                    zlecenie.save()
                    wyslij_sms_do_kierowcy(kierowca, zlecenie)
                    return redirect("zarzadzaj_zleceniami")
        else:
            messages.error(request, "Wypełnij wszystkie wymagane pola!")

    context = {
        "zlecenie": zlecenie,
        "id_zlec": id_zlec,
        "odleglosc": odleglosc,
        "start_coords": start_coords,
        "end_coords": end_coords,
        "route_geometry": route_geometry,
        "error_message": error_message,
        "czas_trasy_sek": czas_trasy_sek,
    }
    return render(request, "users/zlecenia/przypisz_kierowce_ciezarowke.html", context)


def wyslij_sms_do_kierowcy(kierowca, zlecenie):
    numer_telefonu = kierowca.kier_telefon
    marka = zlecenie.ciezarowka.ciez_marka
    model = zlecenie.ciezarowka.ciez_model
    start = zlecenie.przewidywana_data_rozpoczecia.strftime("%d.%m.%Y %H:%M")
    koniec = zlecenie.przewidywana_data_zakonczenia.strftime("%d.%m.%Y %H:%M")

    zlecenie.odleglosc_km, start_coords, end_coords, czas_trasy_sek = oblicz_odleglosc(
        zlecenie.miejsce_odb, zlecenie.miejsce_dost
    )

    mapa_url = generuj_link_do_mapy(start_coords, end_coords)

    tresc_sms = f"""
🚚 Nowe zlecenie:
Start: {start}
Koniec: {koniec}
Pojazd: {marka} {model}
Odległość: {round(zlecenie.odleglosc_km, 1)} km
Czas: {round(czas_trasy_sek / 3600, 1)} h
Trasa: {mapa_url}
"""

    payload = {
        "to": numer_telefonu,
        "message": tresc_sms.strip(),
        "from": "SMSAPI",  # lub własny nadawca jeśli masz zatwierdzonego
        "format": "json",
        "access_token": settings.SMSAPI_TOKEN
    }

    response = requests.post("https://api.smsapi.pl/sms.do", data=payload)
    response.raise_for_status()  # zgłosi wyjątek jeśli API zwróci błąd

    return response.json()


def generuj_link_do_mapy(start_coords, end_coords):
    """
    Generuje link do mapy OpenRouteService na podstawie współrzędnych początkowych i końcowych.
    Współrzędne w formacie: (lon, lat)
    """
    return (
        f"https://maps.openrouteservice.org/directions?"
        f"n1={start_coords[1]}&n2={start_coords[0]}&n3=10"
        f"&a={start_coords[1]},{start_coords[0]},{end_coords[1]},{end_coords[0]}"
        f"&b=0&c=0&k1=pl-PL&k2=km"
    )


@login_required
def get_available_kierowcy_ciezarowki(request, id_zlec):
    """API zwracające dostępnych kierowców i ciężarówki dla wybranej daty realizacji."""
    data_rozpoczecia_str = request.GET.get("data_rozpoczecia")

    if not data_rozpoczecia_str:
        return JsonResponse({"error": "Brak daty rozpoczęcia"}, status=400)

    try:
        data_rozpoczecia = timezone.make_aware(parse_datetime(data_rozpoczecia_str))
    except ValueError:
        return JsonResponse({"error": "Nieprawidłowy format daty"}, status=400)

    zlecenie = get_object_or_404(Zlecenie, pk=id_zlec)
    odleglosc, _, _, czas_trasy_sek = oblicz_odleglosc(zlecenie.miejsce_odb, zlecenie.miejsce_dost)
    przewidywany_czas = timedelta(seconds=czas_trasy_sek)
    data_zakonczenia = data_rozpoczecia + przewidywany_czas

    # 🛠️ Pobranie listy zajętych kierowców i ciężarówek
    zajeci_kierowcy = Zlecenie.objects.filter(
        status="w_realizacji",
        kierowca__isnull=False
    ).filter(
        Q(przewidywana_data_rozpoczecia__lte=data_zakonczenia) &
        Q(przewidywana_data_rozpoczecia__gte=data_rozpoczecia - F("przewidywany_czas_realizacji"))
    ).values_list("kierowca_id", flat=True)

    zajete_ciezarowki = Zlecenie.objects.filter(
        status="w_realizacji",
        ciezarowka__isnull=False
    ).filter(
        Q(przewidywana_data_rozpoczecia__lte=data_zakonczenia) &
        Q(przewidywana_data_rozpoczecia__gte=data_rozpoczecia - F("przewidywany_czas_realizacji"))
    ).values_list("ciezarowka_id", flat=True)

    # 🛠️ Pobranie dostępnych kierowców i ciężarówek
    dostepni_kierowcy = Kierowca.objects.exclude(pk__in=zajeci_kierowcy)
    dostepne_ciezarowki = Ciezarowka.objects.exclude(pk__in=zajete_ciezarowki)

    miesiac_realizacji = data_rozpoczecia.month
    rok_realizacji = data_rozpoczecia.year
    godziny_przewidywane = przewidywany_czas.total_seconds() / 3600
    LIMIT_GODZIN = 168
    CENA_PALIWA_ZA_LITR = 6.26

    # Filtrowanie kierowców którzy nie przekroczą limitu
    dostepni_kierowcy_z_limitem = []
    for kierowca in dostepni_kierowcy:
        suma_godzin = Zlecenie.objects.filter(
            status="zamkniete",
            kierowca=kierowca,
            rzeczywista_data_zakonczenia__year=rok_realizacji,
            rzeczywista_data_zakonczenia__month=miesiac_realizacji
        ).annotate(
            czas=ExpressionWrapper(
                F("rzeczywista_data_zakonczenia") - F("rzeczywista_data_rozpoczecia"),
                output_field=DurationField()
            )
        ).aggregate(suma=Sum("czas"))["suma"]

        godziny_dotychczas = (suma_godzin.total_seconds() / 3600) if suma_godzin else 0

        if godziny_dotychczas + godziny_przewidywane <= LIMIT_GODZIN:
            dostepni_kierowcy_z_limitem.append(kierowca)

    # Oblicz koszty
    kierowcy_z_kosztami = sorted([
        {
            "id": k.pk,
            "imie": k.kier_imie,
            "nazwisko": k.kier_nazwisko,
            "koszt": round(float(k.stawka_za_km) * odleglosc, 2)
        }
        for k in dostepni_kierowcy_z_limitem
    ], key=lambda x: x["koszt"])

    ciezarowki_z_kosztami = sorted([
        {
            "id": c.pk,
            "marka": c.ciez_marka,
            "model": c.ciez_model,
            "koszt": round(float(c.ciez_spalanie_na_100km) * (odleglosc / 100) * CENA_PALIWA_ZA_LITR, 2)
        }
        for c in dostepne_ciezarowki
    ], key=lambda x: x["koszt"])

    return JsonResponse({"kierowcy": kierowcy_z_kosztami, "ciezarowki": ciezarowki_z_kosztami})


@login_required
def szczegoly_zlecenia(request, id_zlec):
    zlecenie = get_object_or_404(Zlecenie, id_zlec=id_zlec)

    error_message = None

    # 🛠 Obliczenie przewidywanego zysku (jeśli `przewidywany_koszt` istnieje)
    przewidywany_zysk = None
    if zlecenie.przewidywany_koszt is not None:
        przewidywany_zysk = zlecenie.przychod - zlecenie.przewidywany_koszt

    context = {
        'zlecenie': zlecenie,
        "przewidywany_zysk": przewidywany_zysk,
        'error_message': error_message,
    }
    return render(request, 'users/zlecenia/szczegoly_zlecenia.html', context)


@login_required
def cofnij_status_zlecenia(request, id_zlec):
    zlecenie = get_object_or_404(Zlecenie, id_zlec=id_zlec)

    if request.method == 'POST':
        zlecenie.status = "nie_rozpoczete"
        zlecenie.kierowca = None
        zlecenie.ciezarowka = None
        zlecenie.save()
        return redirect('zarzadzaj_zleceniami')

    return render(request, 'users/zlecenia/potwierdz_cofniecie_statusu.html', {'zlecenie': zlecenie})


@login_required
def zamknij_zlecenie(request, id_zlec):
    """Widok zamykania zlecenia z dynamicznym obliczaniem kosztów."""
    zlecenie = get_object_or_404(Zlecenie, pk=id_zlec)

    if not zlecenie.kierowca or not zlecenie.ciezarowka:
        messages.error(request, "Brak przypisanego kierowcy lub ciężarówki do tego zlecenia!")
        return redirect("zarzadzaj_zleceniami")

    koszt_kierowcy_za_km = zlecenie.kierowca.stawka_za_km
    spalanie_ciezarowki_na_100km = zlecenie.ciezarowka.ciez_spalanie_na_100km
    cena_paliwa = 6.26  # Taka sama wartość jak w `przypisz_kierowce_ciezarowke`

    if request.method == "POST":
        przejechane_km = float(request.POST.get("przejechane_km", 0))
        spalone_litry = float(request.POST.get("spalone_litry", 0))
        koszty_dodatkowe = float(request.POST.get("koszty_dodatkowe", 0))
        opis_dodatkowe = request.POST.get("opis_dodatkowe", "").strip()
        rzeczywista_data_rozpoczecia = request.POST.get("rzeczywista_data_rozpoczecia", None)
        rzeczywista_data_zakonczenia = request.POST.get("rzeczywista_data_zakonczenia", None)

        if rzeczywista_data_rozpoczecia:
            rzeczywista_data_rozpoczecia = timezone.make_aware(parse_datetime(rzeczywista_data_rozpoczecia))

        if rzeczywista_data_zakonczenia:
            rzeczywista_data_zakonczenia = timezone.make_aware(parse_datetime(rzeczywista_data_zakonczenia))

        # Obliczamy rzeczywiste koszty
        koszt_kierowcy = float(przejechane_km) * float(koszt_kierowcy_za_km)
        koszt_paliwa = float(spalone_litry) * float(cena_paliwa)
        koszt_calkowity = round(koszt_kierowcy + koszt_paliwa + koszty_dodatkowe, 2)

        zysk = float(zlecenie.przychod) - koszt_calkowity

        # 📌 Aktualizacja zlecenia
        zlecenie.status = "zamkniete"
        zlecenie.rzeczywista_data_rozpoczecia = rzeczywista_data_rozpoczecia
        zlecenie.rzeczywista_data_zakonczenia = rzeczywista_data_zakonczenia
        zlecenie.rzeczywiste_przejechane_km = przejechane_km
        zlecenie.rzeczywiste_spalone_litry = spalone_litry
        zlecenie.rzeczywisty_koszt = koszt_calkowity
        zlecenie.zysk = zysk
        zlecenie.save()

        return redirect("zarzadzaj_zleceniami")

    context = {
        "zlecenie": zlecenie,
        "koszt_kierowcy_za_km": koszt_kierowcy_za_km,
        "spalanie_ciezarowki_na_100km": spalanie_ciezarowki_na_100km,
        "cena_paliwa": cena_paliwa,
    }
    return render(request, "users/zlecenia/zamknij_zlecenie.html", context)


@login_required
def historia_zlecenia(request, id_zlec):
    zlecenie = get_object_or_404(Zlecenie, pk=id_zlec)

    context = {
        "zlecenie": zlecenie,
    }
    return render(request, "users/zlecenia/historia_zlecenia.html", context)


@login_required
def analiza_finansowa(request):
    zamkniete_zlecenia = Zlecenie.objects.filter(status="zamkniete")

    # 🔹 Pobranie miesięcy (unikalne wartości YYYY-MM)
    miesiace = sorted(set(
        z.rzeczywista_data_zakonczenia.strftime('%Y-%m')
        for z in zamkniete_zlecenia if z.rzeczywista_data_zakonczenia
    ))

    def decimal_to_float(value):
        return float(value) if value is not None else 0.0

    # 🔹 Przychody, koszty, zyski
    przychody = [
        decimal_to_float(
            zamkniete_zlecenia.filter(rzeczywista_data_zakonczenia__startswith=m)
            .aggregate(suma=Sum('przychod'))['suma']
        ) for m in miesiace
    ]
    srednia_przychod = mean(przychody) if przychody else 0
    min_przychod = min(przychody) if przychody else 0
    max_przychod = max(przychody) if przychody else 0
    mediana_przychod = median(przychody) if przychody else 0
    odchylenie_przychod = stdev(przychody) if len(przychody) > 1 else 0

    koszty = [
        decimal_to_float(
            zamkniete_zlecenia.filter(rzeczywista_data_zakonczenia__startswith=m)
            .aggregate(suma=Sum('rzeczywisty_koszt'))['suma']
        ) for m in miesiace
    ]
    srednia_koszt = mean(koszty) if koszty else 0
    min_koszt = min(koszty) if koszty else 0
    max_koszt = max(koszty) if koszty else 0
    mediana_koszt = median(koszty) if koszty else 0
    odchylenie_koszt = stdev(koszty) if len(koszty) > 1 else 0

    zyski = [p - k for p, k in zip(przychody, koszty)]
    srednia_zysk = mean(zyski) if zyski else 0
    min_zysk = min(zyski) if zyski else 0
    max_zysk = max(zyski) if zyski else 0
    mediana_zysk = median(zyski) if zyski else 0
    odchylenie_zysk = stdev(zyski) if len(zyski) > 1 else 0

    # 🔹 Liczba zrealizowanych zleceń w miesiącach
    liczba_zlecen = [
        zamkniete_zlecenia.filter(rzeczywista_data_zakonczenia__startswith=m).count()
        for m in miesiace
    ]

    # 🔹 Rodzaje towarów
    towary = list(zamkniete_zlecenia.values_list("towar", flat=True))
    unikalne_towary = list(set(towary))
    towary_ilosc = [towary.count(t) for t in unikalne_towary]

    # 🔹 Terminowość dostaw
    na_czas = zamkniete_zlecenia.filter(rzeczywista_data_zakonczenia__lte=F('termin_realizacji')).count()
    opoznienia = zamkniete_zlecenia.filter(rzeczywista_data_zakonczenia__gt=F('termin_realizacji')).count()

    # Wskaźnik wykorzystania floty
    wszystkie_ciezarowki = Ciezarowka.objects.count()
    uzyte_w_zleceniach = Ciezarowka.objects.filter(zlecenie__status='zamkniete').distinct().count()
    wykorzystanie_floty = round((uzyte_w_zleceniach / wszystkie_ciezarowki) * 100, 2) if wszystkie_ciezarowki else 0

    # Wskaźnik wykorzystania kierowcow
    wszyscy_kierowcy = Kierowca.objects.count()
    uzyte_w_zleceniach = Kierowca.objects.filter(zlecenie__status='zamkniete').distinct().count()
    wykorzystanie_kierowcow = round((uzyte_w_zleceniach / wszyscy_kierowcy) * 100, 2) if wszyscy_kierowcy else 0

    # 🔹 Konwersja do JSON
    context = {
        "miesiace_json": json.dumps(miesiace),
        "przychody_json": json.dumps(przychody),
        "koszty_json": json.dumps(koszty),
        "zysk_json": json.dumps(zyski),
        "liczba_zlecen_json": json.dumps(liczba_zlecen),
        "srednia_przychod": srednia_przychod,
        "min_przychod": min_przychod,
        "max_przychod": max_przychod,
        "mediana_przychod": mediana_przychod,
        "odchylenie_przychod": odchylenie_przychod,
        "srednia_koszt": srednia_koszt,
        "min_koszt": min_koszt,
        "max_koszt": max_koszt,
        "mediana_koszt": mediana_koszt,
        "odchylenie_koszt": odchylenie_koszt,
        "srednia_zysk": srednia_zysk,
        "min_zysk": min_zysk,
        "max_zysk": max_zysk,
        "mediana_zysk": mediana_zysk,
        "odchylenie_zysk": odchylenie_zysk,
        "terminowosc_json": json.dumps([na_czas, opoznienia]),
        "rodzaje_towarow_json": json.dumps(towary_ilosc),
        "rodzaje_towarow_labels_json": json.dumps(unikalne_towary),
        "wykorzystanie_floty": wykorzystanie_floty,
        "wykorzystanie_kierowcow": wykorzystanie_kierowcow,
    }

    return render(request, "users/analiza_finansowa.html", context)
