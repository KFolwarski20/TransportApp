from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from users.models import Kierowca, Zlecenie
from users.forms import KierowcaForm
from datetime import datetime
import json


@login_required
def zarzadzaj_kierowcami(request):
    kierowcy = Kierowca.objects.all()
    return render(request, "users/zarzadzanie/zarzadzaj_kierowcami.html", {"kierowcy": kierowcy})


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
