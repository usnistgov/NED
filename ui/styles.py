import streamlit as st

_CSS = """
<style>
/* ── Global ── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #ffffff;
    font-family: "Inter", "Segoe UI", sans-serif;
}

/* ── Top navigation ── */
/* The header is a flex row of logo | nav | toolbar actions. Centering inside
   the nav alone isn't enough: the logo and the toolbar are different widths,
   so the nav's own box is off-center and the links land left of the header's
   midpoint. Giving both flanking sections an equal flex basis makes them the
   same width, which puts the nav box — and so its centered links — at the
   true midpoint. The nav keeps a grow factor so its box stays wider than its
   contents; shrinking it to fit would sit right on the threshold at which the
   nav collapses its links into a "more" menu. */
[data-testid="stToolbar"] > div > *:first-child,
[data-testid="stToolbar"] > div > *:last-child {
    flex: 1 1 0;
    /* A zero flex-basis lets these shrink past their contents, and the logo
       image carries `min-width: 0` and `max-width: 100%`, so on a narrow
       window it would otherwise be squeezed to nothing. Floor them at their
       natural width: wide enough that the equal split still applies, so this
       only bites once the header genuinely runs out of room. */
    min-width: max-content;
}
/* `width: auto` is the load-bearing part: Streamlit gives the nav
   `width: 100%`, which makes it claim the whole row and leaves nothing for
   the flanking sections to grow into. Sizing it to its links instead lets the
   free space split three ways, and keeps its box wider than its contents so
   the nav doesn't sit on the threshold where it collapses the links into a
   "more" menu. Listed after the rule above so it wins for the nav itself. */
[data-testid="stToolbar"] > div > .rc-overflow {
    width: auto;
    flex: 1 1 auto;
    justify-content: center;
}

/* Streamlit reserves 8rem above the content to clear the top nav bar, which
   leaves a wide empty band under it. 60px of this is the header itself. */
[data-testid="stMainBlockContainer"] {
    padding-top: 5rem;
}

/* ── Main header area ── */
.ned-header h1 {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 0.15rem;
}
.ned-header p {
    font-size: 0.95rem;
    color: #555;
    margin-top: 0;
}

/* ── Summary metric boxes ── */
.metric-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.metric-box {
    background: #f4f5f7;
    border-radius: 10px;
    padding: 0.75rem 1.25rem;
    min-width: 140px;
}
.metric-box .metric-label {
    font-size: 0.78rem;
    color: #777;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.2rem;
}
.metric-box .metric-value {
    font-size: 1.45rem;
    font-weight: 700;
    color: #1a1a2e;
}

/* ── Dataframe tweaks ── */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}

/* ── Inline selectbox labels ── */
div[data-testid="stSelectbox"] {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.75rem;
}
div[data-testid="stSelectbox"] label {
    white-space: nowrap;
    margin-bottom: 0;
    min-width: fit-content;
}
div[data-testid="stSelectbox"] > div {
    flex: 1;
}

/* ── Data dictionary tables ── */
/* Every schema table is Field | Type | Required | Description. Automatic
   column sizing gives Type and Required only as much room as the header word,
   so their short, formulaic values wrap over three lines and inflate the row
   height. Pinning the widths trades a little Description width for far fewer
   wrapped rows.

   Tuned per table rather than applied to all of them: the tables further down
   (Experiment, Fragility Model, Fragility Curve) carry much longer Type values
   and shorter descriptions, and these same widths make those *taller*, so they
   keep the browser's automatic sizing. Table order follows the section order in
   assets/data_dictionary.md — 1 is Reference, 2 is Component. */
.st-key-data-dictionary table:nth-of-type(1),
.st-key-data-dictionary table:nth-of-type(2) {
    table-layout: fixed;
    width: 100%;
}
/* Reference: widen Required so "Required (defaults to `Other`)" fits on two
   lines instead of three. */
.st-key-data-dictionary table:nth-of-type(1) :is(th, td):nth-child(1) { width: 10%; }
.st-key-data-dictionary table:nth-of-type(1) :is(th, td):nth-child(2) { width: 12%; }
.st-key-data-dictionary table:nth-of-type(1) :is(th, td):nth-child(3) { width: 15%; }
/* Component: widen Type so "String (max 10), primary key" stops wrapping. */
.st-key-data-dictionary table:nth-of-type(2) :is(th, td):nth-child(1) { width: 12%; }
.st-key-data-dictionary table:nth-of-type(2) :is(th, td):nth-child(2) { width: 16%; }
.st-key-data-dictionary table:nth-of-type(2) :is(th, td):nth-child(3) { width: 12%; }

/* ── In-page navigation links ── */
/* The View / Back controls are st.page_link rather than st.button, so they
   can carry a query param. Style them to match the plain buttons they
   replaced: same border, radius, padding, min-height, font size and weight
   (the background differs by a couple of RGB points, from Streamlit's own
   base-vs-secondary color tokens). Only the in-page links need this — the
   top nav bar is Streamlit's own chrome and is styled above. */
[data-testid="stPageLink"] a[data-testid="stPageLink-NavLink"] {
    border: 1px solid rgba(49, 51, 63, 0.2);
    border-radius: 8px;
    padding: 4px 12px;
    min-height: 40px;
    display: inline-flex;
    justify-content: center;
    align-items: center;
    color: rgb(49, 51, 63);
    background-color: rgb(255, 255, 255);
    text-decoration: none;
    line-height: 1.6;
}
[data-testid="stPageLink"] a[data-testid="stPageLink-NavLink"]:hover {
    border: 1px solid rgba(49, 51, 63, 0.2);
    color: rgb(49, 51, 63);
    background-color: rgba(151, 166, 195, 0.15);
}

/* ── Component detail attribute grid ── */
.attr-grid {
    display: grid;
    grid-template-columns: 200px 1fr;
    row-gap: 0.6rem;
    column-gap: 1rem;
    margin-bottom: 1.5rem;
}
.attr-label {
    font-size: 0.88rem;
    color: #555;
    font-weight: 600;
}
.attr-value {
    font-size: 0.95rem;
    color: #1a1a2e;
}
.attr-hint {
    grid-column: 2;
    font-size: 0.78rem;
    color: #888;
    margin-top: -0.4rem;
}

/* ── Compare Fragilities: divider between baseline/comparison attributes ── */
[class*="st-key-cmp-attr-right-"] {
    border-left: 1px solid #d8dce3;
    padding-left: 0.75rem;
}

/* ── Compare Fragilities: damage-state comparison table ── */
.ds-cmp-table {
    width: 100%;
    table-layout: fixed;
    border-collapse: collapse;
    font-size: 0.88rem;
}
.ds-cmp-table th,
.ds-cmp-table td {
    padding: 0.45rem 0.6rem;
    text-align: left;
    vertical-align: top;
    white-space: normal;
    overflow-wrap: break-word;
    border-bottom: 1px solid #ececec;
}
.ds-cmp-table th.ds-cmp-attr,
.ds-cmp-table td.ds-cmp-attr {
    font-weight: 600;
    color: #1a1a2e;
}
.ds-cmp-table th.ds-cmp-group {
    background-color: #eef1f5;
    font-weight: 700;
    color: #1a1a2e;
    text-align: center;
    border-bottom: 1px solid #d8dce3;
}
.ds-cmp-table th.ds-cmp-side {
    font-size: 0.76rem;
    font-weight: 600;
    color: #777;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.ds-cmp-table th.ds-cmp-shaded,
.ds-cmp-table td.ds-cmp-shaded {
    background-color: #f4f5f7;
}
.ds-cmp-table th.ds-cmp-group-start,
.ds-cmp-table td.ds-cmp-group-start {
    border-left: 2px solid #c9ccd3;
}
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
