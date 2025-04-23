from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from users.models import Ciezarowka, Zlecenie, Serwis, Tankowanie, Kierowca
from users.forms import CiezarowkaForm, SerwisForm, TankowanieForm
from django.contrib import messages
from datetime import datetime
import json
import math


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
def historia_tankowania(request, ciez_id):

    ciezarowka = get_object_or_404(Ciezarowka, pk=ciez_id)
    tankowania = Tankowanie.objects.filter(ciezarowka=ciezarowka).order_by('-data')

    zlecenia_w_realizacji = Zlecenie.objects.filter(ciezarowka=ciezarowka, status="w_realizacji")

    min_do_zatankowania = 0
    max_do_zatankowania = max(0, math.floor(ciezarowka.ciez_bak_max - ciezarowka.ciez_paliwo_litry))

    if request.method == 'POST':
        form = TankowanieForm(request.POST)
        if form.is_valid():
            ilosc = form.cleaned_data['ilosc_litrow']
            cena = form.cleaned_data['cena_za_litr']
            zlecenie = form.cleaned_data['zlecenie']

            if zlecenie and zlecenie.ciezarowka != ciezarowka:
                messages.error(request, "Wybrane zlecenie nie jest przypisane do tej ciężarówki.")
            elif ilosc > max_do_zatankowania:
                messages.error(request, f"Nie można zatankować więcej niż {max_do_zatankowania} litrów!")
            else:
                tankowanie = form.save(commit=False)
                tankowanie.ciezarowka = ciezarowka
                tankowanie.koszt = round(ilosc * cena, 2)
                tankowanie.save()

                # Aktualizacja paliwa w baku
                ciezarowka.ciez_paliwo_litry += ilosc
                ciezarowka.save()

                messages.success(request, f"Zatankowano {ilosc} litrów. Koszt: {tankowanie.koszt} zł.")
                return redirect('historia_tankowania', ciez_id=ciez_id)
    else:
        form = TankowanieForm(initial={'cena_za_litr': 6.26})
        form.fields['zlecenie'].queryset = zlecenia_w_realizacji
        form.fields['kierowca'].queryset = Kierowca.objects.all()

    zlecenia_json = json.dumps([
        {
            "id": z.pk,
            "kierowca": str(z.kierowca),
            "min": round(z.odleglosc_km * (ciezarowka.ciez_spalanie_na_100km / 100), 2),
            "max": round(ciezarowka.ciez_bak_max - ciezarowka.ciez_paliwo_litry, 2)
        } for z in zlecenia_w_realizacji
    ], cls=DjangoJSONEncoder)

    context = {
        "ciezarowka": ciezarowka,
        "tankowania": tankowania,
        "form": form,
        "max_do_zatankowania": max_do_zatankowania,
        "min_do_zatankowania": min_do_zatankowania,
        "zlecenia_json": zlecenia_json,
    }
    return render(request, "users/ciezarowki/historia_tankowania.html", context)


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
