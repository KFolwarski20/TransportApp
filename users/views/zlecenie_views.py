from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from users.forms import ZlecenieForm
from users.models import Zlecenie, Kierowca, Ciezarowka, Tankowanie
from users.views.utils import get_route_geometry, oblicz_odleglosc, wyslij_sms_do_kierowcy
from django.contrib import messages
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from .utils import pobierz_cene_paliwa
from django.http import JsonResponse
from datetime import timedelta
from django.db.models import Q, F, Sum, ExpressionWrapper, DurationField


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
    zlecenie.odleglosc_km, start_coords, end_coords, czas_trasy_sek = oblicz_odleglosc(zlecenie.miejsce_odb,
                                                                                       zlecenie.miejsce_dost)
    zlecenie.save()

    odleglosc = float(zlecenie.odleglosc_km or 0)
    route_geometry = get_route_geometry(start_coords, end_coords) if start_coords and end_coords else None
    CENA_PALIWA_ZA_LITR = pobierz_cene_paliwa()

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

                przewidywany_czas = 1.05 * timedelta(seconds=czas_trasy_sek)
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
    przewidywany_czas = 1.05 * timedelta(seconds=czas_trasy_sek)
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
    CENA_PALIWA_ZA_LITR = pobierz_cene_paliwa()

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
    zlecenie = get_object_or_404(Zlecenie, pk=id_zlec)
    tankowanie_istnieje = Tankowanie.objects.filter(zlecenie=zlecenie).exists()

    if not zlecenie.kierowca or not zlecenie.ciezarowka:
        messages.error(request, "Brak przypisanego kierowcy lub ciężarówki do tego zlecenia!")
        return redirect("zarzadzaj_zleceniami")

    koszt_kierowcy_za_km = zlecenie.kierowca.stawka_za_km

    if request.method == "POST":
        przejechane_km = float(request.POST.get("przejechane_km", 0))
        koszty_dodatkowe = float(request.POST.get("koszty_dodatkowe", 0))
        opis_dodatkowe = request.POST.get("opis_dodatkowe", "").strip()

        rzeczywista_data_rozpoczecia = request.POST.get("rzeczywista_data_rozpoczecia", None)
        rzeczywista_data_zakonczenia = request.POST.get("rzeczywista_data_zakonczenia", None)

        if rzeczywista_data_rozpoczecia:
            rzeczywista_data_rozpoczecia = timezone.make_aware(parse_datetime(rzeczywista_data_rozpoczecia))

        if rzeczywista_data_zakonczenia:
            rzeczywista_data_zakonczenia = timezone.make_aware(parse_datetime(rzeczywista_data_zakonczenia))

        if not tankowanie_istnieje:
            messages.error(request, "Nie można zamknąć zlecenia bez wykonanego tankowania!")
            return redirect("zamknij_zlecenie", id_zlec=zlecenie.pk)

        # 💡 Pobierz tankowania w okresie trwania zlecenia
        tankowania = Tankowanie.objects.filter(
            ciezarowka=zlecenie.ciezarowka,
            data__range=(rzeczywista_data_rozpoczecia, rzeczywista_data_zakonczenia)
        )

        # 🔢 Oblicz rzeczywiste zużycie paliwa i koszt
        spalone_litry = tankowania.aggregate(Sum('ilosc_litrow'))['ilosc_litrow__sum'] or 0
        koszt_paliwa = sum(t.ilosc_litrow * t.cena_za_litr for t in tankowania)

        # 📊 Koszty całkowite
        koszt_kierowcy = float(przejechane_km) * float(koszt_kierowcy_za_km)
        koszt_calkowity = round(koszt_kierowcy + koszt_paliwa + koszty_dodatkowe, 2)
        zysk = float(zlecenie.przychod) - koszt_calkowity

        # 📌 Zapisz dane
        zlecenie.status = "zamkniete"
        zlecenie.rzeczywista_data_rozpoczecia = rzeczywista_data_rozpoczecia
        zlecenie.rzeczywista_data_zakonczenia = rzeczywista_data_zakonczenia
        zlecenie.rzeczywiste_przejechane_km = przejechane_km
        zlecenie.rzeczywiste_spalone_litry = spalone_litry
        zlecenie.rzeczywisty_koszt = koszt_calkowity
        zlecenie.zysk = zysk
        zlecenie.save()

        messages.success(request, f"Zlecenie zamknięte. Koszt paliwa: {koszt_paliwa:.2f} PLN, Spalone litry: {spalone_litry:.1f}")
        return redirect("zarzadzaj_zleceniami")

    context = {
        "zlecenie": zlecenie,
        "koszt_kierowcy_za_km": koszt_kierowcy_za_km,
        "tankowanie_istnieje": tankowanie_istnieje,
    }
    return render(request, "users/zlecenia/zamknij_zlecenie.html", context)


@login_required
def historia_zlecenia(request, id_zlec):
    zlecenie = get_object_or_404(Zlecenie, pk=id_zlec)

    context = {
        "zlecenie": zlecenie,
    }
    return render(request, "users/zlecenia/historia_zlecenia.html", context)