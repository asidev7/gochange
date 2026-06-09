"""Formulaires comptes & KYC — GoChange."""
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import SetPasswordForm  # noqa: F401 (réutilisé ailleurs)

from .models import CustomUser, KYCDocument

INPUT = (
    "w-full rounded-lg border border-gray-300 px-4 py-2.5 text-[15px] "
    "placeholder-gray-400 focus:border-primary focus:ring-1 focus:ring-primary "
    "focus:outline-none transition"
)


class InscriptionForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Mot de passe", widget=forms.PasswordInput(attrs={"class": INPUT, "placeholder": "8 caractères minimum"})
    )
    password2 = forms.CharField(
        label="Confirmer le mot de passe", widget=forms.PasswordInput(attrs={"class": INPUT, "placeholder": "Retapez votre mot de passe"})
    )
    accept = forms.BooleanField(label="J'accepte les CGU et la politique de confidentialité")

    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "email", "phone", "country"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT, "placeholder": "Prénom"}),
            "last_name": forms.TextInput(attrs={"class": INPUT, "placeholder": "Nom"}),
            "email": forms.EmailInput(attrs={"class": INPUT, "placeholder": "vous@exemple.com"}),
            "phone": forms.TextInput(attrs={"class": INPUT, "placeholder": "+229 ..."}),
            "country": forms.Select(attrs={"class": INPUT}, choices=[("BJ", "Bénin"), ("NG", "Nigeria")]),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
        if p1:
            password_validation.validate_password(p1)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower()
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ConnexionForm(forms.Form):
    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(attrs={"class": INPUT, "placeholder": "vous@exemple.com", "autofocus": True}),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"class": INPUT, "placeholder": "Votre mot de passe"}),
    )


class EmailOnlyForm(forms.Form):
    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(attrs={"class": INPUT, "placeholder": "vous@exemple.com"}),
    )


class NouveauMotDePasseForm(forms.Form):
    password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={"class": INPUT, "placeholder": "8 caractères minimum"}),
    )
    password2 = forms.CharField(
        label="Confirmer",
        widget=forms.PasswordInput(attrs={"class": INPUT}),
    )

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
        if p1:
            password_validation.validate_password(p1)
        return cleaned


class ProfilForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "phone", "country"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT}),
            "last_name": forms.TextInput(attrs={"class": INPUT}),
            "phone": forms.TextInput(attrs={"class": INPUT}),
            "country": forms.Select(attrs={"class": INPUT}, choices=[("BJ", "Bénin"), ("NG", "Nigeria")]),
        }


class ChangerMotDePasseForm(forms.Form):
    old_password = forms.CharField(
        label="Mot de passe actuel",
        widget=forms.PasswordInput(attrs={"class": INPUT}),
    )
    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={"class": INPUT}),
    )
    new_password2 = forms.CharField(
        label="Confirmer le nouveau mot de passe",
        widget=forms.PasswordInput(attrs={"class": INPUT}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old = self.cleaned_data["old_password"]
        if not self.user.check_password(old):
            raise forms.ValidationError("Mot de passe actuel incorrect.")
        return old

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("new_password1"), cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            self.add_error("new_password2", "Les deux mots de passe ne correspondent pas.")
        if p1:
            password_validation.validate_password(p1, self.user)
        return cleaned


class PinForm(forms.Form):
    """Définit / change le code PIN de transaction (4 à 6 chiffres)."""

    PIN_ATTRS = {
        "class": INPUT + " tracking-[0.5em] text-center font-semibold",
        "inputmode": "numeric", "autocomplete": "off",
        "maxlength": "6", "placeholder": "••••",
    }
    pin1 = forms.CharField(label="Nouveau code PIN", widget=forms.PasswordInput(attrs=PIN_ATTRS))
    pin2 = forms.CharField(label="Confirmer le code PIN", widget=forms.PasswordInput(attrs=PIN_ATTRS))

    def clean_pin1(self):
        pin = (self.cleaned_data.get("pin1") or "").strip()
        if not (pin.isdigit() and 4 <= len(pin) <= 6):
            raise forms.ValidationError("Le code PIN doit comporter 4 à 6 chiffres.")
        return pin

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("pin1") and cleaned.get("pin2") and cleaned["pin1"] != cleaned["pin2"]:
            self.add_error("pin2", "Les deux codes PIN ne correspondent pas.")
        return cleaned


class ParametresForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["language", "notify_email"]
        widgets = {
            "language": forms.Select(attrs={"class": INPUT}),
            "notify_email": forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded border-gray-300 text-primary"}),
        }


class KYCUpgradeForm(forms.Form):
    """Upload des documents selon le niveau visé."""

    full_name = forms.CharField(
        label="Nom complet (tel qu'il figure sur la pièce)",
        widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "Nom et prénoms"}),
    )
    id_document = forms.FileField(
        label="Pièce d'identité (CNI, passeport ou CIP)",
        widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm"}),
    )
    selfie = forms.FileField(
        label="Selfie en tenant votre pièce",
        widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm"}),
    )
    address_document = forms.FileField(
        label="Justificatif d'adresse ou registre de commerce (niveau 3)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "block w-full text-sm"}),
    )

    def __init__(self, *args, target_level=2, **kwargs):
        self.target_level = target_level
        super().__init__(*args, **kwargs)
        if target_level == 3:
            self.fields["address_document"].required = True
            # Au niveau 3, la pièce et le selfie sont déjà validés au niveau 2
            self.fields["id_document"].required = False
            self.fields["selfie"].required = False
