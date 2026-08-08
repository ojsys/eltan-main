"""Syndication feeds for JELTAN.

Readers subscribe, aggregators poll, and a feed is the cheapest way for either to
learn that a new issue exists without anyone announcing it.
"""

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Atom1Feed

from .models import Article, Issue, JournalSettings


class ArticlesFeed(Feed):
    """The most recently published articles."""

    def title(self):
        return f'{JournalSettings.load().name} — latest articles'

    def link(self):
        return reverse('journal:home')

    def description(self):
        journal = JournalSettings.load()
        return journal.tagline or f'Recently published articles from {journal.name}.'

    def items(self):
        return (
            Article.objects.filter(is_published=True)
            .select_related('issue')
            .prefetch_related('authors')
            .order_by('-published_at')[:25]
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.abstract

    def item_link(self, item):
        return item.get_absolute_url()

    def item_pubdate(self, item):
        return item.published_at

    def item_author_name(self, item):
        return item.author_list or None

    def item_categories(self, item):
        return [keyword.strip() for keyword in (item.keywords or '').split(',') if keyword.strip()]


class ArticlesAtomFeed(ArticlesFeed):
    feed_type = Atom1Feed
    subtitle = ArticlesFeed.description


class IssuesFeed(Feed):
    """Published issues, for readers who follow the journal rather than a topic."""

    def title(self):
        return f'{JournalSettings.load().name} — issues'

    def link(self):
        return reverse('journal:issue_list')

    def description(self):
        return f'Issues of {JournalSettings.load().name} as they are published.'

    def items(self):
        return Issue.objects.filter(is_published=True)[:20]

    def item_title(self, item):
        return f'{item.label}{": " + item.title if item.title else ""}'

    def item_description(self, item):
        return item.description or f'{item.public_articles.count()} articles.'

    def item_link(self, item):
        return item.get_absolute_url()

    def item_pubdate(self, item):
        return item.published_at
