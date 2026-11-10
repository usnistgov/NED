"""Name, locate and deduplicate facilities (Stage 16 of the Experiment split).

Facilities were seeded from free-text location strings, so one lab often
appears under several labels (``Buffalo_NY``, ``University_at_Buffalo`` ...)
with no name. Two kinds of change fix that, applied in this order:

    * each move in ``MOVES`` takes one reference's specimens out of a shared
      facility into their own (creating it if needed), for a facility that
      mixes labs;
    * each rule in ``RULES`` gathers every facility listed in its ``labels``,
      or whose label or location contains any of its ``match`` texts
      (ignoring case), merges them into one facility with the rule's
      ``label``, ``name`` and ``location``, and repoints their specimens.

A facility label is referenced only by ``specimen.json``'s ``facility``
field; no derived id is built from it. So the script edits the JSON
directly, with no database, and writes it in canonical format. It is
idempotent: rerunning it on its own output changes nothing.

It refuses, writing nothing, when a facility matches two rules, when a rule
or move matches nothing, when a label is invalid or taken by another facility
(ignoring case), when the facilities being merged carry different non-blank
notes, or when the result leaves a facility with no specimens.

Usage (from the repository root):

    python scripts/update_facilities.py --dry_run   # report only
    python scripts/update_facilities.py             # write resources/data/

Afterwards, regenerate the fixture from a fresh build and run the standard
checks (README, round-trip protocol).
"""

import argparse
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

NED = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(NED))

from django.core.exceptions import ValidationError

from ned_app.management.import_utils import (
    load_json,
    write_json_files,
)
from ned_app.validators import validate_label

MOVES = [
    {
        # Lee-2007's drywall tests were run by Kyoto University's DPRI (its
        # principal investigator and sponsor). The rest of Japan, Higgins's
        # compiled hybrid stair tests, name no lab and stay general.
        'program': 'Lee-2007',
        'from': 'Japan',
        'label': 'Kyoto_DPRI',
        'name': 'Kyoto University Disaster Prevention Research Institute (DPRI)',
        'location': 'Uji, Japan',
    },
]

RULES = [
    {
        # The New_York and UB_New_York references (Ryu-2019, Tian-2012,
        # Ju-2015) all report tests at UB's SEESL.
        'match': ['buffalo', 'new_york'],
        'label': 'UB_SEESL',
        'name': (
            'University at Buffalo Structural Engineering and Earthquake '
            'Simulation Laboratory (SEESL)'
        ),
        'location': 'Buffalo, NY',
    },
    {
        'match': ['obispo'],
        'label': 'cal_poly_SLO',
        'name': 'Cal Poly San Luis Obispo',
        'location': 'San Luis Obispo, CA',
    },
    {
        'match': ['e-defense'],
        'label': 'E-Defense',
        'name': 'E-Defense',
        'location': 'Miki City, Japan',
    },
    {
        'match': ['reno', 'nevada', 'unr'],
        'label': 'UNR_CCEER',
        'name': (
            'University of Nevada Reno Center for Civil Engineering Earthquake '
            'Research'
        ),
        'location': 'Reno, NV',
    },
    {
        # The general lab for now; the outdoor shake table and the indoor strong
        # wall can be split later. The California and San_Diego references
        # (Astroza-2015, Wang-2016) both report UCSD's outdoor shake table.
        'match': ['ucsd', 'san diego', 'california'],
        'label': 'UCSD',
        'name': 'University of California, San Diego, Structural Laboratories',
        'location': 'San Diego, CA',
    },
    {
        # The New_Zealand reference (Arifin-2020) reports its test set-up at
        # the University of Canterbury.
        'match': ['zealand', 'canterbury'],
        'label': 'U_Canterbury',
        'name': 'University of Canterbury Structural Engineering Laboratory',
        'location': 'Christchurch, New Zealand',
    },
    {
        'match': ['stanford'],
        'label': 'Stanford',
        'name': 'Stanford University Blume Earthquake Engineering Center',
        'location': 'Stanford, CA',
    },
    {
        'match': ['oregon'],
        'label': 'Oregon_State',
        'name': 'Oregon State University',
        'location': 'Corvallis, OR',
    },
    {
        'match': ['penn'],
        'label': 'Penn_State',
        'name': 'The Pennsylvania State University',
        'location': 'University Park, PA',
    },
    {
        'match': ['naples'],
        'label': 'U_Naples',
        'name': 'University of Naples',
        'location': 'Naples, Italy',
    },
    {
        # Neither reference names its lab (Higgins compiles Japanese hybrid
        # stair tests; Blasi-2018 tested in Italy), so these stay general.
        # Exact labels, since 'italy' would also match University_of_Naples_Italy.
        'labels': ['Japan'],
        'label': 'Japan',
        'name': '',
        'location': 'Japan',
    },
    {
        'labels': ['Europe_Italy', 'Italy'],
        'label': 'Italy',
        'name': '',
        'location': 'Italy',
    },
]


def matches(rule, facility):
    """Whether a rule gathers a facility: by exact label, or by text it contains."""
    if facility['label'] in rule.get('labels', ()):
        return True
    text = f'{facility["label"]} {facility["location"]}'.lower()
    return any(m.lower() in text for m in rule.get('match', ()))


def refuse(problems):
    """Stop without writing anything if there are problems."""
    if problems:
        sys.exit('Nothing written:\n  ' + '\n  '.join(problems))


def label_problems(label, facilities, allowed):
    """A new label's problems: invalid, or held by a facility not in allowed."""
    problems = []
    try:
        validate_label(label)
    except ValidationError as exc:
        problems.append(f'{label}: {" ".join(exc.messages)}')
    taken = [
        f['label']
        for f in facilities
        if f['label'].lower() == label.lower() and f['label'] not in allowed
    ]
    if taken:
        problems.append(f'{label}: label taken by {taken[0]}')
    return problems


def apply_moves(facilities, specimens, moves):
    """
    Move each listed reference's specimens into their own facility.

    Returns:
        list[tuple[dict, int]]: Each move with the number of its specimens.
    """
    problems = []
    done = []
    for move in moves:
        mine = [s for s in specimens if s['program'] == move['program']]
        if not mine:
            problems.append(f'{move["label"]}: {move["program"]} has no specimens')
        stray = {s['facility'] for s in mine} - {move['from'], move['label']}
        if stray:
            problems.append(
                f'{move["label"]}: {move["program"]} also has specimens at '
                f'{", ".join(sorted(stray))}'
            )
        problems += label_problems(move['label'], facilities, {move['label']})
        done.append((move, len(mine)))
    refuse(problems)
    for move, _ in done:
        target = next((f for f in facilities if f['label'] == move['label']), None)
        if target is None:
            target = {'label': move['label'], 'notes': ''}
            facilities.append(target)
        target.update(name=move['name'], location=move['location'])
        for s in specimens:
            if s['program'] == move['program']:
                s['facility'] = move['label']
    return done


def plan(facilities, rules):
    """
    Work out each rule's merge, refusing any conflict.

    Returns:
        list[tuple[dict, list[dict]]]: Each rule with the facilities it gathers.
    """
    problems = []
    planned = []
    claimed = {}
    for rule in rules:
        matched = [f for f in facilities if matches(rule, f)]
        if not matched:
            problems.append(f'{rule["label"]}: matches no facility')
        for f in matched:
            if f['label'] in claimed:
                problems.append(
                    f'{f["label"]}: matches both {claimed[f["label"]]} and '
                    f'{rule["label"]}'
                )
            claimed[f['label']] = rule['label']
        gathered = {f['label'] for f in matched}
        problems += label_problems(rule['label'], facilities, gathered)
        notes = {f['notes'] for f in matched if f['notes']}
        if len(notes) > 1:
            problems.append(
                f'{rule["label"]}: merged facilities have different notes'
            )
        planned.append((rule, matched))
    refuse(problems)
    return planned


def apply(facilities, specimens, planned):
    """Merge each rule's facilities into its first, and repoint specimens."""
    new_label = {}
    dropped = set()
    for rule, matched in planned:
        keep = matched[0]
        notes = next((f['notes'] for f in matched if f['notes']), '')
        for f in matched:
            new_label[f['label']] = rule['label']
            if f is not keep:
                dropped.add(id(f))
        keep.update(
            label=rule['label'],
            name=rule['name'],
            location=rule['location'],
            notes=notes,
        )
    facilities = [f for f in facilities if id(f) not in dropped]
    for s in specimens:
        s['facility'] = new_label.get(s['facility'], s['facility'])
    return facilities, specimens


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data_dir', default=str(NED / 'resources' / 'data'))
    parser.add_argument(
        '--dry_run', action='store_true', help='report the changes, write nothing'
    )
    args = parser.parse_args()

    facilities = load_json('facility.json', args.data_dir)
    specimens = load_json('specimen.json', args.data_dir)
    before = deepcopy((facilities, specimens))

    for move, moved in apply_moves(facilities, specimens, MOVES):
        print(f'{move["label"]}  ({move["location"]})')
        print(f'    <- {moved} specimens of {move["program"]} from {move["from"]}')

    count = Counter(s['facility'] for s in specimens)
    planned = plan(facilities, RULES)
    for rule, matched in planned:
        print(f'{rule["label"]}  ({rule["location"]})')
        for f in matched:
            print(
                f'    <- {f["label"]}  [{f["location"]}]  {count[f["label"]]} specimens'
            )

    facilities, specimens = apply(facilities, specimens, planned)
    used = {s['facility'] for s in specimens}
    refuse([
        f'{f["label"]}: left with no specimens'
        for f in facilities
        if f['label'] not in used
    ])
    print(f'{len(before[0])} facilities -> {len(facilities)}')
    if (facilities, specimens) == before:
        print('Nothing to change.')
        return
    if args.dry_run:
        print('Dry run: nothing written.')
        return
    write_json_files(
        {'facility.json': facilities, 'specimen.json': specimens},
        data_dir=args.data_dir,
    )
    print(f'Wrote facility.json and specimen.json in {args.data_dir}.')


if __name__ == '__main__':
    main()
