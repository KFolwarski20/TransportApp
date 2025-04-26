from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Kierowca, Ciezarowka, Zlecenie, Serwis, Tankowanie
import re
from datetime import date
from django.utils import timezone

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User  # Używamy CustomUser zamiast auth.User!
        fields = ["username", "email", "password1", "password2"]


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Nazwa użytkownika",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Wpisz nazwę użytkownika"})
    )
    password = forms.CharField(
        label="Hasło",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Wpisz hasło"})
    )


class KierowcaForm(forms.ModelForm):
    class Meta:
        model = Kierowca
        fields = "__all__"
        labels = {
            "kier_imie": "Imię",
            "kier_nazwisko": "Nazwisko",
            "data_urodzenia": "Data urodzenia",
            "kier_adres": "Adres",
            "kier_telefon": "Telefon",
            "kier_email": "Email",
            "kier_lata_dosw": "Lata doświadczenia",
            "kier_przejech_km": "Przejechane km",
            "kier_liczba_wykroczen": "Liczba wykroczeń",
            "stawka_za_km": "Stawka za km (PLN)",
        }

    def __init__(self, *args, **kwargs):
        super(KierowcaForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

    # Zaktualizowana walidacja daty urodzenia
    def clean_data_urodzenia(self):
        data_urodzenia = self.cleaned_data['data_urodzenia']
        today = date.today()

        # Sprawdzenie, czy data nie jest z przyszłości
        if data_urodzenia > today:
            raise forms.ValidationError("Data urodzenia nie może być z przyszłości!")

        # Obliczenie wieku
        wiek = today.year - data_urodzenia.year - (
                    (today.month, today.day) < (data_urodzenia.month, data_urodzenia.day))

        # Sprawdzenie, czy kierowca ma minimum 18 lat
        if wiek < 18:
            raise forms.ValidationError("Kierowca musi mieć co najmniej 18 lat!")

        return data_urodzenia

    # Walidacja przejechanych km
    def clean_kier_przejech_km(self):
        km = self.cleaned_data['kier_przejech_km']
        if km < 0:
            raise forms.ValidationError("Wartość przejechanych km nie może być ujemna!")
        return km

    # Walidacja lat doświadczenia
    def clean_kier_lata_dosw(self):
        lata = self.cleaned_data['kier_lata_dosw']
        if lata < 0:
            raise forms.ValidationError("Lata doświadczenia nie mogą być ujemne!")
        return lata

    # Walidacja stawki za km
    def clean_stawka_za_km(self):
        stawka = self.cleaned_data['stawka_za_km']
        if stawka < 0:
            raise forms.ValidationError("Stawka za km nie może być ujemna!")
        return stawka

    # Walidacja numeru telefonu
    def clean_kier_telefon(self):
        telefon = self.cleaned_data['kier_telefon']

        # Usuwamy spacje do sprawdzenia długości i cyfr
        tylko_cyfry = re.sub(r'\D', '', telefon)

        if not 9 <= len(tylko_cyfry) <= 15:
            raise forms.ValidationError("Numer telefonu powinien zawierać od 9 do 15 cyfr.")

        # Sprawdzenie ogólnego formatu (cyfry i spacje, opcjonalny + na początku)
        pattern = r'^\+?\d{1,4}(\s?\d{2,4}){2,4}$'
        if not re.match(pattern, telefon.replace(" ", " ")):  # zamieniamy twarde spacje na zwykłe
            raise forms.ValidationError("Podaj poprawny numer telefonu, np. +48 534 342 342.")

        return telefon

    # Walidacja emaila
    def clean_kier_email(self):
        email = self.cleaned_data['kier_email']
        if not re.match(r'^[\w.-]+@[\w.-]+\.\w+$', email):
            raise forms.ValidationError("Podaj poprawny adres email.")
        return email


class CiezarowkaForm(forms.ModelForm):
    class Meta:
        model = Ciezarowka
        fields = "__all__"
        labels = {
            "ciez_marka": "Marka",
            "ciez_model": "Model",
            "ciez_moc": "Moc (KM)",
            "ciez_nr_rejestr": "Numer rejestracyjny",
            "ciez_przebieg": "Przebieg (km)",
            "ciez_rok_prod": "Rok produkcji",
            "ciez_data_zakupu": "Data zakupu",
            "ciez_data_serwisu": "Data ostatniego serwisu",
            "ciez_masa_wlasna": "Masa własna (t)",
            "ciez_masa_ladunku": "Masa ładunku (t)",
            "ciez_dop_masa_calk": "Dopuszczalna masa całkowita (t)",
            "ciez_spalanie_na_100km": "Spalanie na 100 km (l)",
        }

    def __init__(self, *args, **kwargs):
        super(CiezarowkaForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})


class ZlecenieForm(forms.ModelForm):
    class Meta:
        model = Zlecenie
        fields = ['miejsce_odb', 'miejsce_dost', 'przychod', 'ilosc_ladunku',
                  'towar', 'data_otrzymania', 'termin_realizacji']
        labels = {
            "miejsce_odb": "Miejsce odbioru",
            "miejsce_dost": "Miejsce dostawy",
            "przychod": "Przychód (PLN)",
            "ilosc_ladunku": "Ilość ładunku (tony)",
            "towar": "Rodzaj towaru",
            "data_otrzymania": "Data otrzymania",
            "termin_realizacji": "Termin realizacji",
            "kierowca": "Przypisany kierowca",
            "ciezarowka": "Przypisana ciężarówka",
            "status": "Status zlecenia",
        }

    def __init__(self, *args, **kwargs):
        super(ZlecenieForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

    def clean_przychod(self):
        przychod = self.cleaned_data.get('przychod')
        if przychod <= 0:
            raise ValidationError("Przychód musi być większy od 0.")
        return przychod

    def clean_ilosc_ladunku(self):
        ilosc_ladunku = self.cleaned_data.get('ilosc_ladunku')
        if ilosc_ladunku <= 0:
            raise ValidationError("Ilość ładunku musi być większa od 0.")
        return ilosc_ladunku

    def clean_data_otrzymania(self):
        data_otrzymania = self.cleaned_data.get('data_otrzymania')
        if data_otrzymania > date.today():
            raise ValidationError("Data otrzymania nie może być późniejsza niż dzisiejsza.")
        return data_otrzymania

    def clean_termin_realizacji(self):
        termin_realizacji = self.cleaned_data.get('termin_realizacji')

        if termin_realizacji is None:
            raise ValidationError("Musisz podać termin realizacji.")

        if termin_realizacji < timezone.now():
            raise ValidationError("Termin realizacji nie może być wcześniejszy niż bieżący czas.")

        return termin_realizacji


class SerwisForm(forms.ModelForm):
    class Meta:
        model = Serwis
        fields = ['data', 'opis', 'koszt']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'opis': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'koszt': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
        }

    def clean_data(self):
        data = self.cleaned_data.get('data')
        if data and data > date.today():
            raise forms.ValidationError("Data serwisu nie może być późniejsza niż dzisiaj.")
        return data

    def clean_koszt(self):
        koszt = self.cleaned_data.get('koszt')
        if koszt is not None and koszt < 0:
            raise forms.ValidationError("Koszt serwisu nie może być ujemny.")
        return koszt


class TankowanieForm(forms.ModelForm):
    class Meta:
        model = Tankowanie
        fields = ['data', 'kierowca', 'zlecenie', 'ilosc_litrow', 'cena_za_litr', 'komentarz']
        widgets = {
            'zlecenie': forms.Select(attrs={'id': 'id_zlecenie'}),
        }
