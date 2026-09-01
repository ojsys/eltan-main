"""Context the JELTAN shell needs on every one of its pages.

Scoped to the journal by checking the resolved app: the masthead and navigation
need the journal settings, the current issue and whether the viewer is an editor,
but no other page on the ELTAN site should pay for those queries.
"""

from .models import Issue, JournalRole, JournalSettings


def journal_chrome(request):
    match = getattr(request, 'resolver_match', None)
    if not match or match.app_name != 'journal':
        return {}

    return {
        'journal': JournalSettings.load(),
        'current_issue': Issue.objects.filter(is_published=True).first(),
        # Editors get a link to the editorial office in the journal navigation;
        # everyone else never learns it is there.
        'is_journal_editor': JournalRole.is_editor(request.user),
        # Publishing without review, and editing the published record, are
        # chiefs-and-administrators work, so the doors to it are not drawn for
        # anyone who would only meet a 404 behind them.
        'is_journal_chief': JournalRole.is_chief(request.user),
    }
