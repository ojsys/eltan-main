import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import sources
from .forms import AchievementForm, ProfileForm
from .models import Achievement, PortfolioProfile, PortfolioSettings, has_premium


def _profile(user):
    profile, _ = PortfolioProfile.objects.get_or_create(user=user)
    return profile


def _upload_allowance(user):
    """How many more self-reported entries this member may add; None for no limit."""
    if has_premium(user):
        return None
    limit = PortfolioSettings.load().free_upload_limit
    return max(0, limit - user.achievements.count())


@login_required
def overview(request):
    user = request.user
    profile = _profile(user)
    premium = has_premium(user)

    # Without premium the portfolio is the full record, newest first; choosing a
    # period and seeing it summarised is the premium part.
    if premium:
        period, period_label, start, end = sources.resolve_period(request.GET)
    else:
        period, period_label, start, end = 'all', 'All time', None, None

    entries = sources.entries_for(user, start, end)
    category = request.GET.get('category', '')
    shown = [entry for entry in entries if entry.category == category] if category else entries

    goal = profile.cpd_goal_hours if period == 'this_year' else None
    summary = sources.summarise(entries, start, end, goal_hours=goal)

    return render(request, 'portfolio/overview.html', {
        'profile': profile,
        'premium': premium,
        'settings_row': PortfolioSettings.load(),
        'summary': summary,
        'entries': shown,
        'all_categories': sorted({(entry.category, entry.category_label) for entry in entries}),
        'category': category,
        'period': period,
        'period_label': period_label,
        'period_from': request.GET.get('from', ''),
        'period_to': request.GET.get('to', ''),
        'upload_allowance': _upload_allowance(user),
        'query': request.GET.urlencode(),
    })


@login_required
def add(request):
    allowance = _upload_allowance(request.user)
    if allowance == 0:
        messages.info(request, 'You have reached the number of entries included without premium.')
        return redirect('portfolio:overview')

    form = AchievementForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        achievement = form.save(commit=False)
        achievement.user = request.user
        achievement.save()
        messages.success(request, f'"{achievement.title}" added to your portfolio.')
        return redirect('portfolio:overview')
    return render(request, 'portfolio/achievement_form.html', {'form': form})


@login_required
def edit(request, pk):
    achievement = get_object_or_404(Achievement, pk=pk, user=request.user)
    old_evidence = achievement.evidence.name if achievement.evidence else ''
    form = AchievementForm(request.POST or None, request.FILES or None, instance=achievement)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        if old_evidence and old_evidence != (saved.evidence.name if saved.evidence else ''):
            achievement.evidence.storage.delete(old_evidence)
        messages.success(request, 'Entry updated.')
        return redirect('portfolio:overview')
    return render(request, 'portfolio/achievement_form.html', {'form': form, 'achievement': achievement})


@login_required
@require_POST
def delete(request, pk):
    achievement = get_object_or_404(Achievement, pk=pk, user=request.user)
    if achievement.evidence:
        achievement.evidence.delete(save=False)
    achievement.delete()
    messages.success(request, 'Entry removed from your portfolio.')
    return redirect('portfolio:overview')


@login_required
def evidence(request, pk):
    """The evidence file, to its owner only."""
    achievement = get_object_or_404(Achievement, pk=pk, user=request.user)
    if not achievement.evidence:
        raise Http404('No evidence file.')
    return FileResponse(
        achievement.evidence.open('rb'),
        filename=os.path.basename(achievement.evidence.name),
    )


@login_required
def settings_view(request):
    profile = _profile(request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Portfolio settings saved.')
        return redirect('portfolio:overview')
    return render(request, 'portfolio/settings.html', {
        'form': form, 'profile': profile, 'premium': has_premium(request.user),
        'share_url': request.build_absolute_uri(profile.get_share_url()) if profile.share_token else '',
    })


@login_required
@require_POST
def sharing(request):
    """Turn the public link on or off, or replace it with a new one."""
    profile = _profile(request.user)
    action = request.POST.get('action')
    if action in ('enable', 'regenerate') and not has_premium(request.user):
        messages.info(request, 'Sharing your portfolio is a premium feature.')
        return redirect('portfolio:settings')

    if action == 'enable':
        if not profile.share_token:
            profile.new_share_token()
        profile.share_enabled = True
        messages.success(request, 'Your portfolio link is on. Anyone with the link can view it.')
    elif action == 'regenerate':
        profile.new_share_token()
        profile.share_enabled = True
        messages.success(request, 'A new link has been made. The old one no longer works.')
    else:
        profile.share_enabled = False
        messages.success(request, 'Your portfolio link is off.')
    profile.save()
    return redirect('portfolio:settings')


def shared(request, token):
    """The portfolio as someone the member shared it with sees it."""
    profile = get_object_or_404(
        PortfolioProfile.objects.select_related('user'), share_token=token, share_enabled=True,
    )
    # Sharing lapses with premium: the link stops working rather than showing
    # the record to the world on a plan that no longer includes it.
    if not has_premium(profile.user):
        raise Http404()
    entries = sources.entries_for(profile.user, public_only=True)
    return render(request, 'portfolio/shared.html', {
        'profile': profile,
        'member': profile.user,
        'entries': entries,
        'summary': sources.summarise(entries, None, None),
    })


@login_required
def report(request):
    """The period's portfolio as a PDF, for an appraisal file or a promotion panel."""
    if not has_premium(request.user):
        messages.info(request, 'The portfolio report is a premium feature.')
        return redirect('portfolio:overview')

    from journal import typeset

    profile = _profile(request.user)
    period, period_label, start, end = sources.resolve_period(request.GET)
    entries = sources.entries_for(request.user, start, end)
    goal = profile.cpd_goal_hours if period == 'this_year' else None
    html = render_to_string('portfolio/report_pdf.html', {
        'member': request.user,
        'profile': profile,
        'summary': sources.summarise(entries, start, end, goal_hours=goal),
        'period_label': period_label,
        'generated_at': timezone.now(),
        'share_url': (request.build_absolute_uri(profile.get_share_url())
                      if profile.share_enabled and profile.share_token else ''),
        'font_faces': typeset.font_faces(),
        'body_font': typeset.BODY_FONT,
        'ui_font': typeset.UI_FONT,
    })
    pdf = typeset.html_to_pdf(html)
    full_name = f'{request.user.first_name} {request.user.last_name}'.strip() or 'member'
    name = '_'.join(part for part in ''.join(ch if ch.isalnum() else '_' for ch in full_name).split('_') if part)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ELTAN_Portfolio_{name}.pdf"'
    return response
