"""Formulaire de contact — GoChange."""
from django import forms

INPUT = (
    "w-full rounded-lg border border-gray-300 px-4 py-2.5 text-[15px] "
    "placeholder-gray-400 focus:border-primary focus:ring-1 focus:ring-primary "
    "focus:outline-none transition"
)


class ContactForm(forms.Form):
    name = forms.CharField(
        label="Votre nom",
        widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "Nom et prénoms"}),
    )
    email = forms.EmailField(
        label="Votre e-mail",
        widget=forms.EmailInput(attrs={"class": INPUT, "placeholder": "vous@exemple.com"}),
    )
    subject = forms.CharField(
        label="Sujet",
        widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "Objet de votre message"}),
    )
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={"class": INPUT, "rows": 5, "placeholder": "Comment pouvons-nous vous aider ?"}),
    )
