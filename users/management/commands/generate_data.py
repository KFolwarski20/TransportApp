import random
from django.core.management.base import BaseCommand
from faker import Faker
from users.models import Kierowca, Ciezarowka, Zlecenie, Tankowanie
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from django.utils.timezone import now

fake = Faker('pl_PL')


class Command(BaseCommand):
    help = 'Generuje testowych 100 kierowców i 100 ciężarówek'

    def handle(self, *args, **kwargs):
        # Kierowcy
        for _ in range(100):
            Kierowca.objects.create(
                kier_imie=fake.first_name(),
                kier_nazwisko=fake.last_name(),
                data_urodzenia=fake.date_of_birth(minimum_age=25, maximum_age=65),
                kier_adres=fake.address(),
                kier_telefon=fake.phone_number(),
                kier_email=fake.unique.email(),
                kier_lata_dosw=random.randint(1, 40),
                kier_przejech_km=random.randint(50000, 1000000),
                kier_liczba_wykroczen=random.randint(0, 10),
                stawka_za_km=round(random.uniform(1.2, 3.0), 2)
            )

        # Ciężarówki
        marki = ["MAN", "Volvo", "DAF", "Mercedes", "Scania", "Iveco", "Renault"]
        modele = ["XF", "Actros", "T", "FH", "Stralis", "TGX"]

        for _ in range(100):
            rok_prod = random.randint(2008, 2024)
            Ciezarowka.objects.create(
                ciez_marka=random.choice(marki),
                ciez_model=random.choice(modele),
                ciez_moc=random.randint(280, 600),
                ciez_nr_rejestr=fake.license_plate(),
                ciez_przebieg=random.randint(50000, 900000),
                ciez_rok_prod=rok_prod,
                ciez_data_zakupu=date(rok_prod, random.randint(1, 12), random.randint(1, 28)),
                ciez_data_serwisu=now().date() - timedelta(days=random.randint(0, 365)),
                ciez_masa_wlasna=round(random.uniform(6.0, 9.0), 2),
                ciez_masa_ladunku=round(random.uniform(5.0, 25.0), 2),
                ciez_dop_masa_calk=round(random.uniform(15.0, 40.0), 2),
                ciez_spalanie_na_100km=round(random.uniform(20.0, 40.0), 2),
                ciez_paliwo_litry=round(random.uniform(5.0, 400.0), 2),
                ciez_bak_max=round(random.uniform(900.0, 1000.0), 2),
            )

        self.stdout.write(self.style.SUCCESS("✅ Wygenerowano 100 kierowców i 100 ciężarówek"))

        # Dodaj listę przykładowych towarów i miejsc
        towary_lista = ["Meble", "Elektronika", "Zboże", "Chemikalia", "Maszyny", "Materiały budowlane"]
        miasta = ["Warszawa", "Kraków", "Gdańsk", "Poznań", "Wrocław", "Lublin", "Łódź", "Katowice", "Szczecin",
                  "Białystok"]

        # Wygeneruj 1000 zleceń
        kierowcy = list(Kierowca.objects.all())
        ciezarowki = list(Ciezarowka.objects.all())

        for _ in range(1000):
            kierowca = random.choice(kierowcy)
            ciezarowka = random.choice(ciezarowki)

            data_otrzymania = fake.date_between(start_date='-6M', end_date='-1M')
            termin_realizacji = datetime.combine(
                data_otrzymania + timedelta(days=random.randint(2, 10)),
                time(hour=random.randint(8, 18), minute=random.choice([0, 15, 30, 45]))
            )
            rzeczywista_data_rozpoczecia = termin_realizacji - timedelta(days=2)
            rzeczywista_data_zakonczenia = termin_realizacji + timedelta(hours=random.randint(-2, 5))

            odleglosc_km = round(random.uniform(100, 1000), 2)
            stawka_kierowcy = float(kierowca.stawka_za_km)
            spalanie_na_100km = float(ciezarowka.ciez_spalanie_na_100km)

            spalone_litry = round((odleglosc_km / 100) * spalanie_na_100km, 2)
            cena_za_litr = 6.26
            koszt_paliwa = round(spalone_litry * cena_za_litr, 2)
            koszt_kierowcy = round(stawka_kierowcy * odleglosc_km, 2)
            koszt_laczny = round(koszt_kierowcy + koszt_paliwa + random.uniform(100, 300), 2)
            przychod = round(koszt_laczny + random.uniform(500, 2000), 2)
            zysk = round(przychod - koszt_laczny, 2)

            # ✅ Najpierw utwórz zlecenie
            zlecenie = Zlecenie.objects.create(
                miejsce_odb=random.choice(miasta),
                miejsce_dost=random.choice(miasta),
                przychod=Decimal(str(przychod)),
                ilosc_ladunku=round(random.uniform(1.0, float(ciezarowka.ciez_masa_ladunku)), 2),
                towar=random.choice(towary_lista),
                data_otrzymania=data_otrzymania,
                termin_realizacji=termin_realizacji,
                kierowca=kierowca,
                ciezarowka=ciezarowka,
                status="zamkniete",
                odleglosc_km=odleglosc_km,
                rzeczywista_data_rozpoczecia=rzeczywista_data_rozpoczecia,
                rzeczywista_data_zakonczenia=rzeczywista_data_zakonczenia,
                rzeczywiste_przejechane_km=odleglosc_km + random.uniform(-5, 15),
                rzeczywiste_spalone_litry=spalone_litry,
                rzeczywisty_koszt=Decimal(str(koszt_laczny)),
                zysk=Decimal(str(zysk))
            )

            # ✅ Teraz możesz przypisać to zlecenie do tankowania
            Tankowanie.objects.create(
                data=rzeczywista_data_rozpoczecia - timedelta(hours=1),
                ciezarowka=ciezarowka,
                kierowca=kierowca,
                zlecenie=zlecenie,
                ilosc_litrow=spalone_litry,
                cena_za_litr=cena_za_litr,
                komentarz="Tankowanie przed zleceniem"
            )
