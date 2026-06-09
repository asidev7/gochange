"""Sitemap des pages publiques pour gochange.store."""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"

    def items(self):
        return [
            ("core:landing", 1.0),
            ("core:taux", 0.9),
            ("core:faq", 0.7),
            ("core:a_propos", 0.6),
            ("core:contact", 0.6),
            ("core:cgu", 0.3),
            ("core:confidentialite", 0.3),
            ("accounts:inscription", 0.8),
            ("accounts:connexion", 0.5),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]


STATIC_SITEMAPS = StaticViewSitemap
