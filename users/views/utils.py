import openrouteservice
from geopy.geocoders import Nominatim
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from datetime import datetime


ORS_API_KEY = "5b3ce3597851110001cf62485a5adc7a079347dbb10ae922b01de893"


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


@require_GET
def get_cena_paliwa(request):
    data_str = request.GET.get("data")
    if not data_str:
        return JsonResponse({"error": "Brak daty"}, status=400)

    try:
        # API Orlen
        response = requests.get("https://tool.orlen.pl/api/wholesalefuelprices")
        response.raise_for_status()
        data = response.json()

        # Format daty z formularza (YYYY-MM-DD)
        target_date = datetime.strptime(data_str, "%Y-%m-%d").date()

        for entry in data:
            effective_date = datetime.fromisoformat(entry["effectiveDate"]).date()
            if entry["productName"] == "ONEkodiesel" and effective_date == target_date:
                cena_litr = round(float(entry["value"]) / 1000, 3)
                return JsonResponse({"cena": cena_litr})

        return JsonResponse({"error": "Brak danych dla podanej daty"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)