from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from statistics import mean, median, stdev
from users.models import Zlecenie, Kierowca, Ciezarowka
import json
from django.db.models import F, Sum


@login_required
def menu_glowne_view(request):
    return render(request, "users/menu_glowne.html")


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
