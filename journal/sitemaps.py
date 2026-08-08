"""Sitemaps for the journal.

Google Scholar in particular wants to find article landing pages by crawling,
and a sitemap is what tells it they exist without waiting for something to link
to them.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Article, Issue


class ArticleSitemap(Sitemap):
    changefreq = 'yearly'  # A published article does not change.
    priority = 0.9

    def items(self):
        return Article.objects.filter(is_published=True).order_by('-published_at')

    def lastmod(self, obj):
        return obj.updated_at


class IssueSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.7

    def items(self):
        return Issue.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.published_at


class JournalPagesSitemap(Sitemap):
    """The journal's standing pages — scope, board, guidelines, policies.

    These are what a prospective author reads before deciding to submit, so they
    are worth crawling even though they rarely change.
    """

    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return [
            'journal:home', 'journal:about', 'journal:editorial_board',
            'journal:guidelines', 'journal:policies', 'journal:issue_list',
        ]

    def location(self, item):
        return reverse(item)


JOURNAL_SITEMAPS = {
    'journal_articles': ArticleSitemap,
    'journal_issues': IssueSitemap,
    'journal_pages': JournalPagesSitemap,
}
