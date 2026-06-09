"""Formulaires espace connecté — GoChange."""
from decimal import Decimal

from django import forms

from wallet.models import Beneficiary

from .models import NGN, XOF

INPUT = (
    "w-full rounded-lg border border-gray-300 px-4 py-2.5 text-[15px] "
    "placeholder-gray-400 focus:border-primary focus:ring-1 focus:ring-primary "
    "focus:outline-none transition"
)


class DepotForm(forms.Form):
    currency = forms.ChoiceField(
        label="Devise à déposer",
        choices=[(XOF, "FCFA (XOF) — Mobile Money"), (NGN, "Naira (NGN) — Carte / virement")],
        widget=forms.Select(attrs={"class": INPUT, "x-model": "currency"}),
    )
    operator = forms.ChoiceField(
        label="Opérateur Mobile Money",
        required=False,
        choices=[("mtn", "MTN MoMo"), ("moov", "Moov Money"), ("celtiis", "Celtiis Cash")],
        widget=forms.Select(attrs={"class": INPUT}),
    )
    amount = forms.DecimalField(
        label="Montant",
        min_value=Decimal("100"),
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": INPUT, "placeholder": "0", "x-model": "amount"}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("currency") == XOF and not cleaned.get("operator"):
            self.add_error("operator", "Choisissez un opérateur Mobile Money.")
        return cleaned


class EchangeForm(forms.Form):
    from_currency = forms.ChoiceField(
        label="Je convertis",
        choices=[(NGN, "Naira (NGN)"), (XOF, "FCFA (XOF)")],
        widget=forms.Select(attrs={"class": INPUT, "x-model": "fromCur"}),
    )
    amount = forms.DecimalField(
        label="Montant à convertir",
        min_value=Decimal("100"),
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": INPUT, "placeholder": "0", "x-model": "amount"}),
    )


class RetraitForm(forms.Form):
    beneficiary = forms.ModelChoiceField(
        label="Bénéficiaire",
        queryset=Beneficiary.objects.none(),
        widget=forms.Select(attrs={"class": INPUT}),
    )
    amount = forms.DecimalField(
        label="Montant à retirer",
        min_value=Decimal("100"),
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": INPUT, "placeholder": "0"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["beneficiary"].queryset = user.beneficiaries.all()


class BeneficiaireMomoForm(forms.ModelForm):
    class Meta:
        model = Beneficiary
        fields = ["label", "operator", "phone"]
        widgets = {
            "label": forms.TextInput(attrs={"class": INPUT, "placeholder": "Ex. Mon numéro MTN"}),
            "operator": forms.Select(attrs={"class": INPUT}),
            "phone": forms.TextInput(attrs={"class": INPUT, "placeholder": "+229 ..."}),
        }

    def save(self, user, commit=True):
        obj = super().save(commit=False)
        obj.user = user
        obj.kind = Beneficiary.KIND_MOMO
        if commit:
            obj.save()
        return obj


class BeneficiaireBanqueForm(forms.ModelForm):
    """Le nom du titulaire (account_name) est rempli après résolution Paystack."""

    class Meta:
        model = Beneficiary
        fields = ["label", "bank_code", "bank_name", "account_number", "account_name"]
        widgets = {
            "label": forms.TextInput(attrs={"class": INPUT, "placeholder": "Ex. Compte fournisseur Lagos"}),
            "bank_code": forms.HiddenInput(),
            "bank_name": forms.HiddenInput(),
            "account_number": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "10 chiffres",
                "maxlength": "10", "x-model": "accountNumber",
            }),
            "account_name": forms.HiddenInput(),
        }

    def clean_account_number(self):
        num = (self.cleaned_data.get("account_number") or "").strip()
        if not (len(num) == 10 and num.isdigit()):
            raise forms.ValidationError("Le numéro de compte doit comporter 10 chiffres.")
        return num

    def clean_account_name(self):
        name = (self.cleaned_data.get("account_name") or "").strip()
        if not name:
            raise forms.ValidationError(
                "Vérifiez le compte pour afficher le nom du titulaire avant d'enregistrer."
            )
        return name

    def save(self, user, commit=True):
        obj = super().save(commit=False)
        obj.user = user
        obj.kind = Beneficiary.KIND_BANK
        if commit:
            obj.save()
        return obj
