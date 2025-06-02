from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from statistics import mean, median, stdev
from users.models import Zlecenie, Kierowca, Ciezarowka
import json
from django.db.models import F, Sum
import calendar
from collections import defaultdict
from datetime import datetime


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

    dzisiaj = datetime.today()
    aktualny_miesiac = dzisiaj.strftime('%Y-%m')

    # 🔹 Pobranie miesięcy (unikalne YYYY-MM tylko z przeszłości i bieżącego)
    miesiace = sorted(set(
        z.rzeczywista_data_zakonczenia.strftime('%Y-%m')
        for z in zamkniete_zlecenia
        if z.rzeczywista_data_zakonczenia and z.rzeczywista_data_zakonczenia.strftime('%Y-%m') <= aktualny_miesiac
    ))

    # 🔹 Wskaźnik wykorzystania ciężarówek – uśredniony % czasu pracy
    ciezarowki = Ciezarowka.objects.all()
    godziny_ciezarowek = {m: defaultdict(float) for m in miesiace}

    for ciezarowka in ciezarowki:
        zlecenia = Zlecenie.objects.filter(
            status="zamkniete",
            ciezarowka=ciezarowka,
            rzeczywista_data_zakonczenia__year__in=[int(m[:4]) for m in miesiace]
        )
        for z in zlecenia:
            if z.rzeczywista_data_rozpoczecia and z.rzeczywista_data_zakonczenia:
                czas_trwania = (z.rzeczywista_data_zakonczenia - z.rzeczywista_data_rozpoczecia).total_seconds() / 3600
                miesiac_klucz = z.rzeczywista_data_zakonczenia.strftime("%Y-%m")
                if miesiac_klucz in miesiace:
                    godziny_ciezarowek[miesiac_klucz][ciezarowka.ciez_id] += czas_trwania

    wykorzystanie_ciezarowek_miesieczne = []

    for miesiac in miesiace:
        rok_, mies_ = map(int, miesiac.split("-"))
        max_godz_miesiac = calendar.monthrange(rok_, mies_)[1] * 24

        procenty = [
            (godziny / max_godz_miesiac) * 100
            for godziny in godziny_ciezarowek[miesiac].values()
        ]
        wykorzystanie_ciezarowek_miesieczne.append(round(sum(procenty) / len(ciezarowki), 2) if ciezarowki else 0)

    srednie_wykorzystanie_ciezarowek = round(sum(wykorzystanie_ciezarowek_miesieczne) / len(miesiace),
                                             2) if miesiace else 0

    # 🔹 Wskaźnik wykorzystania kierowców – uśredniony % czasu pracy
    kierowcy = Kierowca.objects.all()
    godziny_kierowcow = {m: defaultdict(float) for m in miesiace}

    for kierowca in kierowcy:
        zlecenia = Zlecenie.objects.filter(
            status="zamkniete",
            kierowca=kierowca,
            rzeczywista_data_zakonczenia__year__in=[int(m[:4]) for m in miesiace]
        )
        for z in zlecenia:
            if z.rzeczywista_data_rozpoczecia and z.rzeczywista_data_zakonczenia:
                czas_trwania = (z.rzeczywista_data_zakonczenia - z.rzeczywista_data_rozpoczecia).total_seconds() / 3600
                miesiac_klucz = z.rzeczywista_data_zakonczenia.strftime("%Y-%m")
                if miesiac_klucz in miesiace:
                    godziny_kierowcow[miesiac_klucz][kierowca.kier_id] += czas_trwania

    wykorzystanie_miesieczne = []

    for miesiac in miesiace:
        max_godz_miesiac = 168  # limit 168h

        procenty = [
            (godziny / max_godz_miesiac) * 100
            for godziny in godziny_kierowcow[miesiac].values()
        ]
        wykorzystanie_miesieczne.append(round(sum(procenty) / len(kierowcy), 2) if kierowcy else 0)

    srednie_wykorzystanie_kierowcow = round(sum(wykorzystanie_miesieczne) / len(miesiace), 2) if miesiace else 0

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
        "wykorzystanie_ciezarowek_procent": srednie_wykorzystanie_ciezarowek,
        "wykorzystanie_kierowcow_procent": srednie_wykorzystanie_kierowcow,
    }

    return render(request, "users/analiza_finansowa.html", context)
