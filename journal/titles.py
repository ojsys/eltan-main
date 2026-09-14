"""Putting every article title into the journal's house style.

Titles arrive in whatever the author typed: SHOUTED IN CAPITALS, in sentence
case, in something in between. On a contents page that reads as a fault in the
journal rather than a quirk of the manuscript, so one style is imposed on all of
them — Title Case, with articles, coordinating conjunctions and short
prepositions left lower.

The hard part is not the casing rule, it is everything the rule must not touch.
An ALL-CAPS title has thrown away the information that would tell us which words
are acronyms, so ``ICT`` and ``WAEC`` have to be recognised by name; ``McGregor``
and ``O'Brien`` have to survive; ``Code-Switching`` needs both halves; and a
title already carrying deliberate capitals — ``eLearning``, ``iPad`` — must be
left alone. Each of those is a rule below, and each has a test.

Nothing here guesses at proper nouns in running text: a word that is not an
acronym, not already capitalised and not first is simply Title Cased, which is
the one transformation that is safe in both directions.
"""

import re

# Lowercase unless they open or close the title, or follow a colon. Articles,
# coordinating conjunctions, and prepositions of four letters or fewer — the
# convention most scholarly journals set their contents pages in.
SMALL_WORDS = {
    'a', 'an', 'the',
    'and', 'but', 'or', 'nor', 'for', 'yet', 'so',
    'as', 'at', 'by', 'if', 'in', 'of', 'off', 'on', 'out', 'per', 'to', 'up',
    'via', 'vs', 'v', 'from', 'into', 'onto', 'over', 'upon', 'with', 'near',
    'than', 'atop',
}

# Acronyms a Nigerian ELT journal prints that are not also ordinary words. An
# ALL-CAPS title has thrown away the capitals that would identify them, so these
# are recognised by name and always printed in full capitals. Editors can add
# their own in the admin — see JournalSettings.title_acronyms.
ACRONYMS = {
    # the association and its journal
    'ELTAN', 'JELTAN', 'IATEFL', 'TESOL', 'NELTA',
    # the field
    'ELT', 'ESL', 'EFL', 'ESP', 'EAP', 'L1', 'L2', 'SLA', 'CLT', 'TBLT',
    'CEFR', 'TEFL', 'TESL', 'CLIL', 'LSP',
    # Nigerian institutions and examinations
    'WAEC', 'NECO', 'JAMB', 'UTME', 'NCE', 'NUC', 'NTI', 'UBE', 'SSCE',
    'NYSC', 'FCT', 'NERDC', 'NABTEB', 'JSS', 'SSS',
    # general
    'ICT', 'UNESCO', 'UNICEF', 'NGO', 'NGOS', 'UK', 'USA', 'HIV',
    'COVID', 'DVD', 'PDF', 'URL', 'FAQ', 'GPA', 'SPSS', 'ANOVA',
    'MOOC', 'MOOCS', 'OER', 'PhD',
}

# Acronyms that are also ordinary English words. Forcing these would be worse
# than missing them: in a journal about English teaching, 'the noun phrase'
# becoming 'the NOUN Phrase' is a great deal more embarrassing than the National
# Open University appearing as 'Noun'. They are honoured only when the author's
# own capitals say so — which a shouted title cannot.
AMBIGUOUS_ACRONYMS = {
    'IT', 'US', 'UN', 'AI', 'CALL', 'MALL', 'NOUN', 'STEM', 'AIDS',
    'CD', 'TV', 'QR', 'MTE', 'ACT', 'SET', 'MAP', 'PET', 'CAT',
}

ROMAN_NUMERAL = re.compile(r'^[IVXLCDM]+$', re.IGNORECASE)

# A word is any run of letters, digits and the marks that live inside words.
WORD = re.compile(r"[^\s]+")

# Where a subtitle starts: whatever follows one of these is capitalised however
# small it is. "Teaching at scale: the case for ..." -> "... : The Case for ...".
OPENS_SUBTITLE = ('.', ':', ';', '?', '!', '—', '–', '-', '|', '/')

# Leading and trailing marks that are punctuation rather than part of the word.
LEADING = '([{"‘“«¿¡'
TRAILING = ')]}"’”».,;:!?'


def _is_roman_numeral(word):
    # 'I' and 'V' and 'MIX' are words as often as they are numerals, so only
    # treat a token as a numeral when it was already capitalised and is not a
    # word English uses on its own.
    return bool(ROMAN_NUMERAL.match(word)) and word.upper() not in {'I', 'V', 'X', 'MIX', 'DID', 'MIL'}


def _has_internal_capital(word):
    """Whether the author capitalised inside the word: eLearning, iPad, McGregor.

    Deliberate, and not something a casing rule can improve on, so such words are
    passed through untouched. An all-caps word does not count — that is the very
    thing being corrected.
    """
    letters = [character for character in word if character.isalpha()]
    if len(letters) < 2:
        return False
    if all(character.isupper() for character in letters):
        return False
    return any(character.isupper() for character in letters[1:])


def _capitalise(word):
    """Capitalise a single word, leaving the rest of it as it is.

    ``str.capitalize`` would lowercase the tail, which destroys ``McGregor`` and
    ``PhD``; ``str.title`` would break on apostrophes, giving ``Don'T``.
    """
    for index, character in enumerate(word):
        if character.isalpha():
            return word[:index] + character.upper() + word[index + 1:]
    return word


def _fix_name_prefixes(word):
    """Restore the capital inside Scottish and Irish names.

    ``MCGREGOR`` and ``O'BRIEN`` come out of a shouted title as ``Mcgregor`` and
    ``O'brien`` unless something puts the inner capital back.
    """
    # O'Brien, D'Angelo — a single letter, an apostrophe, then the name.
    match = re.match(r"^([A-Za-z])(['’])(\w)(.*)$", word)
    if match:
        initial, mark, following, rest = match.groups()
        return f'{initial.upper()}{mark}{following.upper()}{rest}'
    # McGregor, but not "Mch" or a two-letter word.
    if len(word) > 3 and word[:2].lower() == 'mc' and word[2].isalpha():
        return f'Mc{word[2].upper()}{word[3:]}'
    return word


def _cased_word(word, acronyms, force_capital, keep_ambiguous=False):
    """Apply the house style to one whitespace-delimited token."""
    prefix = ''
    suffix = ''
    while word and word[0] in LEADING:
        prefix += word[0]
        word = word[1:]
    while word and word[-1] in TRAILING:
        suffix = word[-1] + suffix
        word = word[:-1]
    if not word:
        return prefix + suffix

    # A hyphenated or slashed compound is cased part by part: Code-Switching,
    # Teacher/Learner. The first part always takes a capital; later parts follow
    # the same small-word rule as the rest of the title.
    if re.search(r'[-–/]', word) and any(character.isalpha() for character in word):
        parts = re.split(r'([-–/])', word)
        rebuilt = []
        first = True
        for part in parts:
            if part in '-–/':
                rebuilt.append(part)
                continue
            rebuilt.append(_cased_word(part, acronyms, force_capital or first, keep_ambiguous))
            if part:
                first = False
        return prefix + ''.join(rebuilt) + suffix

    bare = ''.join(character for character in word if character.isalnum())

    if bare.upper() in acronyms:
        # Print the acronym exactly as the journal spells it — 'PhD', not 'PHD'.
        for known in acronyms:
            if known.upper() == bare.upper():
                return prefix + known + suffix
    # An acronym that is also a word: only when this token's own capitals say so.
    if keep_ambiguous and word.isupper() and bare.upper() in AMBIGUOUS_ACRONYMS:
        return prefix + bare.upper() + suffix
    if _is_roman_numeral(bare) and word.isupper():
        return prefix + word.upper() + suffix
    if _has_internal_capital(word):
        return prefix + word + suffix

    lowered = word.lower()
    if not force_capital and lowered in SMALL_WORDS:
        return prefix + lowered + suffix
    return prefix + _fix_name_prefixes(_capitalise(lowered)) + suffix


def to_title_case(text, extra_acronyms=()):
    """Return ``text`` in the journal's house style.

    ``extra_acronyms`` are the journal's own, from the admin, added to the built-in
    list so a new examination board or project name does not need a deploy.
    """
    if not text or not text.strip():
        return (text or '').strip()

    acronyms = set(ACRONYMS)
    for value in extra_acronyms or ():
        value = (value or '').strip()
        if value:
            acronyms.add(value)

    # Collapse the runs of whitespace a copy-paste from a PDF leaves behind.
    words = WORD.findall(text.strip())
    if not words:
        return text.strip()

    # In a shouted title every word is uppercase, so being uppercase says nothing
    # about which ones are acronyms. Only a title with real case left in it can
    # be trusted on that point.
    letters = [character for character in text if character.isalpha()]
    shouted = bool(letters) and all(character.isupper() for character in letters)

    result = []
    force_capital = True
    for index, word in enumerate(words):
        is_last = index == len(words) - 1
        result.append(_cased_word(
            word, acronyms, force_capital or is_last, keep_ambiguous=not shouted,
        ))
        # The next word opens a subtitle if this one closed a clause.
        force_capital = word.endswith(OPENS_SUBTITLE)

    return ' '.join(result)


def needs_restyling(text, extra_acronyms=()):
    """Whether ``text`` is not already in house style."""
    return bool(text) and text.strip() != to_title_case(text, extra_acronyms)
