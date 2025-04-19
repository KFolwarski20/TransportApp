from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import date, datetime
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)  # Możesz dodać inne pola


class Kierowca(models.Model):
    kier_id = models.AutoField(primary_key=True)
    kier_imie = models.CharField(max_length=100, verbose_name="Imię")
    kier_nazwisko = models.CharField(max_length=100, verbose_name="Nazwisko")
    data_urodzenia = models.DateField(verbose_name="Data urodzenia")
    kier_adres = models.TextField(verbose_name="Adres")
    kier_telefon = models.CharField(max_length=15, verbose_name="Telefon")
    kier_email = models.EmailField(verbose_name="Email")
    kier_lata_dosw = models.IntegerField(verbose_name="Lata doświadczenia")
    kier_przejech_km = models.IntegerField(verbose_name="Przejechane km")
    kier_liczba_wykroczen = models.IntegerField(verbose_name="Liczba wykroczeń")
    stawka_za_km = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Stawka za km (PLN)", default=1.50)

    def oblicz_wiek(self):
        today = date.today()
        return today.year - self.data_urodzenia.year - ((today.month, today.day) < (self.data_urodzenia.month, self.data_urodzenia.day))

    def __str__(self):
        return f"{self.kier_imie} {self.kier_nazwisko} - {self.oblicz_wiek()} lat"


class Ciezarowka(models.Model):
    ciez_id = models.AutoField(primary_key=True)
    ciez_marka = models.CharField(max_length=50, verbose_name="Marka")
    ciez_model = models.CharField(max_length=50, verbose_name="Model")

    ciez_moc = models.IntegerField(
        verbose_name="Moc (KM)",
        validators=[MinValueValidator(0, message="Moc nie może być ujemna.")]
    )

    ciez_nr_rejestr = models.CharField(
        max_length=15,
        verbose_name="Numer rejestracyjny",
        validators=[RegexValidator(
            regex=r'^[A-Z0-9]{2,3}\s?[A-Z0-9]{4,6}$',
            message="Podaj poprawny numer rejestracyjny."
        )]
    )

    ciez_przebieg = models.IntegerField(
        verbose_name="Przebieg (km)",
        validators=[MinValueValidator(0, message="Przebieg nie może być ujemny.")]
    )

    ciez_rok_prod = models.IntegerField(
        verbose_name="Rok produkcji",
        validators=[
            MinValueValidator(0, message="Rok produkcji nie może być mniejszy od 0."),
            MaxValueValidator(date.today().year, message=f"Rok produkcji nie może być większy niż {date.today().year}.")
        ]
    )

    ciez_data_zakupu = models.DateField(verbose_name="Data zakupu")
    ciez_data_serwisu = models.DateField(verbose_name="Data ostatniego serwisu")

    ciez_masa_wlasna = models.DecimalField(
        max_digits=7, decimal_places=2,
        verbose_name="Masa własna (t)",
        validators=[MinValueValidator(0.01, message="Masa własna musi być większa od 0.")]
    )

    ciez_masa_ladunku = models.DecimalField(
        max_digits=7, decimal_places=2,
        verbose_name="Masa ładunku (t)",
        validators=[MinValueValidator(0.01, message="Masa ładunku musi być większa od 0.")]
    )

    ciez_dop_masa_calk = models.DecimalField(
        max_digits=7, decimal_places=2,
        verbose_name="Dopuszczalna masa całkowita (t)",
        validators=[MinValueValidator(0.01, message="Dopuszczalna masa całkowita musi być większa od 0.")]
    )

    ciez_spalanie_na_100km = models.DecimalField(
        max_digits=5, decimal_places=2,
        verbose_name="Spalanie na 100 km (l)",
        validators=[MinValueValidator(0, message="Spalanie nie może być mniejsze niż 0.")]
    )

    ciez_paliwo_litry = models.FloatField(
        verbose_name="Stan paliwa (l)",
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )

    ciez_bak_max = models.FloatField(
        verbose_name="Pojemność baku (l)",
        validators=[MinValueValidator(1)],
        null=True,
        blank=True
    )

    @property
    def paliwo_procent(self):
        """Oblicza poziom paliwa jako procent"""
        if self.ciez_paliwo_litry is not None and self.ciez_bak_max:
            return round((self.ciez_paliwo_litry / self.ciez_bak_max) * 100, 1)
        return None

    def clean(self):
        # Sprawdzenie, czy data zakupu została wypełniona
        if self.ciez_data_zakupu:
            if self.ciez_data_zakupu > date.today():
                raise ValidationError({"ciez_data_zakupu": "Data zakupu nie może być późniejsza niż dzisiaj."})

        # Sprawdzenie, czy data serwisu została wypełniona
        if self.ciez_data_serwisu:
            if self.ciez_data_serwisu > date.today():
                raise ValidationError(
                    {"ciez_data_serwisu": "Data ostatniego serwisu nie może być późniejsza niż dzisiaj."})

        # Masa ładunku nie większa niż dopuszczalna masa całkowita
        if self.ciez_masa_ladunku and self.ciez_dop_masa_calk:
            if self.ciez_masa_ladunku > self.ciez_dop_masa_calk:
                raise ValidationError(
                    {"ciez_masa_ladunku": "Masa ładunku nie może być większa niż dopuszczalna masa całkowita."})

        # Dopuszczalna masa całkowita >= masa własna + masa ładunku
        if self.ciez_masa_wlasna and self.ciez_masa_ladunku and self.ciez_dop_masa_calk:
            if self.ciez_dop_masa_calk < (self.ciez_masa_wlasna + self.ciez_masa_ladunku):
                raise ValidationError({
                    "ciez_dop_masa_calk":
                        "Dopuszczalna masa całkowita nie może być mniejsza niż suma masy własnej i masy ładunku."
                })

    def __str__(self):
        return f"{self.ciez_marka} {self.ciez_model} ({self.ciez_nr_rejestr})"


class Zlecenie(models.Model):
    STATUS_CHOICES = [
        ("nie_rozpoczete", "Nie rozpoczęte"),
        ("w_realizacji", "W realizacji"),
        ("zamkniete", "Zamknięte"),
    ]

    id_zlec = models.AutoField(primary_key=True)
    miejsce_odb = models.CharField(max_length=255, verbose_name="Miejsce odbioru")
    miejsce_dost = models.CharField(max_length=255, verbose_name="Miejsce dostawy")
    przychod = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Przychód (PLN)")
    ilosc_ladunku = models.FloatField(verbose_name="Ilość ładunku (tony)")
    towar = models.CharField(max_length=255, verbose_name="Rodzaj towaru")
    data_otrzymania = models.DateField(verbose_name="Data otrzymania zlecenia")
    termin_realizacji = models.DateTimeField(null=True, blank=True, verbose_name="Termin realizacji")
    kierowca = models.ForeignKey('users.Kierowca', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Przypisany kierowca")
    ciezarowka = models.ForeignKey('users.Ciezarowka', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Przypisana ciężarówka")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="nie_rozpoczete", verbose_name="Status zlecenia")
    odleglosc_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    przewidywana_data_rozpoczecia = models.DateTimeField(null=True, blank=True)
    przewidywany_czas_realizacji = models.DurationField(null=True, blank=True)
    przewidywana_data_zakonczenia = models.DateTimeField(null=True, blank=True)
    przewidywany_koszt = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rzeczywista_data_rozpoczecia = models.DateTimeField(null=True, blank=True,
                                                        verbose_name="Rzeczywista data rozpoczęcia")
    rzeczywista_data_zakonczenia = models.DateTimeField(null=True, blank=True,
                                                        verbose_name="Rzeczywista data zakończenia")
    rzeczywiste_przejechane_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                                     verbose_name="Rzeczywiste przejechane km")
    rzeczywiste_spalone_litry = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                                    verbose_name="Rzeczywiste spalone litry paliwa")
    rzeczywisty_koszt = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    zysk = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def numer_zlecenia(self):
        return f"ZT-{self.id_zlec:04d}/{datetime.now().year}"

    def __str__(self):
        return f"Zlecenie {self.id_zlec}: {self.miejsce_odb} → {self.miejsce_dost} ({self.get_status_display()})"


class Serwis(models.Model):
    ciezarowka = models.ForeignKey(Ciezarowka, on_delete=models.CASCADE)
    data = models.DateField()
    opis = models.TextField()
    koszt = models.DecimalField(max_digits=10, decimal_places=2)


class Tankowanie(models.Model):
    ciezarowka = models.ForeignKey(Ciezarowka, on_delete=models.CASCADE)
    data = models.DateField()
    ilosc_litrow = models.DecimalField(max_digits=5, decimal_places=2)
    cena_za_litr = models.DecimalField(max_digits=5, decimal_places=2)
    koszt = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    kierowca = models.ForeignKey(Kierowca, on_delete=models.SET_NULL, null=True, blank=True)
    zlecenie = models.ForeignKey(Zlecenie, on_delete=models.SET_NULL, null=True, blank=True)
    komentarz = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.koszt = self.ilosc_litrow * self.cena_za_litr
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ciezarowka} - {self.data} - {self.ilosc_litrow}l"
