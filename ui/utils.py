import html
import re

import pandas as pd
import streamlit as st


def fmt(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return '—'
    s = str(val).strip()
    return s if s else '—'


def esc(val) -> str:
    return html.escape(fmt(val), quote=True)


def strip_prefix(val) -> str:
    s = fmt(val)
    parts = s.split(' - ', 1)
    return parts[1] if len(parts) == 2 else s


def attr(
    label: str,
    value: str,
    caption: str | None = None,
    help_text: str | None = None,
) -> None:
    c1, c2 = st.columns([1, 3])
    c1.markdown(f'**{label}**', help=help_text)
    c2.markdown(value)
    if caption:
        c2.caption(caption)


# Pop-up helper descriptions for database fields, keyed by model field name.
# Wording follows the data dictionary (assets/data_dictionary.md); update both
# together if a definition changes.
FIELD_HELP = {
    'comp_detail': (
        'Classification or short description of the component '
        'attachment/connection detailing (e.g., perimeter-fixed vs. '
        'back-braced ceilings).'
    ),
    'material': (
        'General material grouping of the component, if applicable '
        '(e.g., CPVC vs. iron sprinkler pipes).'
    ),
    'size_class': (
        'General size grouping of this component relative to others of the '
        'same type, if applicable (e.g., large gridded area of ceiling tiles '
        'or specific equipment size).'
    ),
    'ds_class': (
        'First-pass classification of whether the observed damage is '
        'consequential:\n'
        '- **No damage** — no change in state was observed from the test.\n'
        '- **Inconsequential** — (aesthetic) damage was observed but is '
        'unlikely to require repair or impact system operation (no action '
        'required).\n'
        '- **Consequential** — damage that may require repair or impact '
        'system operation (observable and requires action).\n'
        '- **Unknown** — a damage state class could not be identified by '
        'the reviewer.'
    ),
    'specimen_inspection_sequence': (
        'Which test of this specimen the observation comes from (the ith '
        'test), when a specimen was tested/inspected multiple times.'
    ),
    'loading_protocol': (
        'Name, ID, or general description of the ground motion or loading '
        'protocol used in the test.'
    ),
    'governing_design_standard': (
        'Name of the standard governing the design of the specimen, if applicable.'
    ),
    'design_objective': (
        'Performance level to which the specimen was designed, e.g., code '
        'compliant, common construction practice, low-damage design, or '
        'meeting a certain damage objective under a specific loading '
        'condition.'
    ),
    'ds_rank': (
        'Integer rank ordering this observed damage relative to other damage '
        'observed in the same specimen (1 = first/least severe), as recorded '
        'by the original author in the reference. Blank if not noted in the '
        'reference.'
    ),
    'prior_damage': (
        'Description of any damage noted during a previous test of this '
        'specimen, including if and how the specimen was repaired before '
        'this test. Empty if no prior damage was noted.'
    ),
    'prior_damage_repaired': (
        'TRUE if prior damage was noted and repaired before this test; '
        'FALSE if noted and not repaired; or a general description of the '
        'previous damage that was repaired.'
    ),
}


_DOI_RE = re.compile(r'^10\.\d{4,9}/\S+$')
_MD_ESCAPE_RE = re.compile(r'([\\\[\]*_`])')


def _md_escape(text: str) -> str:
    """Escape characters that would otherwise be interpreted as markdown."""
    return _MD_ESCAPE_RE.sub(r'\\\1', text)


def _md_link(url: str, text: str | None = None) -> str:
    """Build a safe markdown link. Parens in the target are URL-encoded
    so they don't terminate the link, and the display text is escaped."""
    if text is None:
        text = url
    target = url.replace('(', '%28').replace(')', '%29').replace(' ', '%20')
    return f'[{_md_escape(text)}]({target})'


def doi_url(doi) -> str | None:
    """Return a normalized http(s) URL for a DOI, or None if the value
    doesn't match a recognized DOI or http(s) URL form."""
    if not doi:
        return None
    s = str(doi).strip()
    if _DOI_RE.match(s):
        return f'https://doi.org/{s}'
    if s.startswith(('http://', 'https://')) and ' ' not in s:
        return s
    return None


def doi_link(doi) -> str | None:
    """Return a safe markdown link for a DOI, or None if the value
    doesn't match a recognized DOI or http(s) URL form."""
    url = doi_url(doi)
    return _md_link(url) if url else None


def _format_author(a: dict) -> str:
    family = (a.get('family') or '').strip()
    given = (a.get('given') or '').strip()
    if family and given:
        initials = ''.join(f'{p[0]}.' for p in re.split(r'[\s\-]+', given) if p)
        return f'{family}, {initials}'
    return family or given


def _join_authors(names: list[str]) -> str:
    names = [n for n in names if n]
    if not names:
        return ''
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f'{names[0]} & {names[1]}'
    return ', '.join(names[:-1]) + ', & ' + names[-1]


def build_citation(csl: dict, markdown: bool = True) -> str:
    """Build an APA-ish citation from a CSL-JSON dict, as markdown by
    default or plain text with markdown=False (e.g. for CSV export).
    Returns an empty string if there's nothing useful to render."""
    if not isinstance(csl, dict):
        return ''

    authors = _join_authors([
        _format_author(a) for a in csl.get('author', []) if isinstance(a, dict)
    ])

    year = ''
    dp = (
        csl.get('issued', {}).get('date-parts')
        if isinstance(csl.get('issued'), dict)
        else None
    )
    if dp and isinstance(dp, list) and dp and dp[0]:
        year = str(dp[0][0])

    title = (csl.get('title') or '').strip().replace('\n', ' ')
    venue = (
        csl.get('container-title')
        or csl.get('event-title')
        or csl.get('publisher')
        or csl.get('genre')
        or ''
    ).strip()

    pieces = []
    head = ''
    if authors:
        head = authors
    if year:
        head = f'{head} ({year})' if head else f'({year})'
    if head:
        pieces.append(head + '.')
    if title:
        pieces.append((_md_escape(title) if markdown else title) + '.')
    if venue:
        pieces.append(f'*{_md_escape(venue)}*.' if markdown else f'{venue}.')

    raw_doi = csl.get('DOI') or csl.get('URL') or ''
    doi = doi_link(raw_doi) if markdown else doi_url(raw_doi)
    if doi:
        pieces.append(doi)

    return ' '.join(pieces).strip()


def csv_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Prefix string cells beginning with formula triggers (=, +, -, @,
    tab, CR) with a single quote so Excel won't evaluate them on open."""
    out = df.copy()
    triggers = ('=', '+', '-', '@', '\t', '\r')
    for col in out.select_dtypes(include='object').columns:
        out[col] = out[col].map(
            lambda v: "'" + v if isinstance(v, str) and v and v[0] in triggers else v
        )
    return out
