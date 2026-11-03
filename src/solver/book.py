"""Opening book: rankings for the first two turns, computed once and shipped with the repo.

Like a chess opening book, early positions are looked up instead of searched. The book holds
the one-step and two-step rankings for the opening position and for every reply position
after each "book opener" (the one-step best, the two-step best, and the exhaustive-search
optimum where one is known). Any other position falls back to live search.

    python -m solver.book                 # rebuild for every mode
    python -m solver.book --modes official
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from .patterns import ALL_GREEN, decode
from .solver import DATA_DIR, MODES, Suggestion, WordleSolver

BOOK_PATH = DATA_DIR / 'opening_book.json'
BOOK_VERSION = 1
TOP = 10

# The proven-optimal opener from exhaustive search, where one has been published. It only
# applies to the original 2,315-word answer list in normal (not hard) mode.
EXHAUSTIVE = {
    'official': {
        'word': 'salet',
        'average': 3.4212,
        'source': 'Selby (2022); confirmed by Bertsimas & Paskov, Operations Research (2024)',
    },
}

# Suggestions are stored as rows of these fields, which keeps the file compact.
_FIELDS = ('word', 'one_step', 'two_step', 'p_answer', 'expected_left', 'worst_left')


def position_key(history):
    """'' for the opening, 'soare:BYBYB' after one guess, and so on."""
    return ','.join(f'{guess.lower()}:{colours.upper()}' for guess, colours in history)


def _pack(suggestion):
    row = [getattr(suggestion, field) for field in _FIELDS]
    return [round(v, 5) if isinstance(v, float) else v for v in row]


def _unpack(row):
    return Suggestion(**dict(zip(_FIELDS, row)))


class OpeningBook:
    def __init__(self, data):
        self.data = data

    @classmethod
    def load(cls, path=BOOK_PATH):
        """Loads the book, or an empty one if the file doesn't exist."""
        path = Path(path)
        if not path.exists():
            return cls({'version': BOOK_VERSION, 'modes': {}})
        with open(path) as f:
            data = json.load(f)
        if data.get('version') != BOOK_VERSION:
            return cls({'version': BOOK_VERSION, 'modes': {}})
        return cls(data)

    def _mode(self, solver):
        mode = self.data['modes'].get(solver.name)
        # A book built from different word lists or weights would give wrong answers.
        return mode if mode and mode['fingerprint'] == solver.fingerprint else None

    def lookup(self, solver, history):
        """Returns (one_step, two_step) suggestion lists for a book position, or None."""
        mode = self._mode(solver)
        entry = mode and mode['positions'].get(position_key(history))
        if entry is None:
            return None
        return [_unpack(r) for r in entry['one']], [_unpack(r) for r in entry['two']]

    def exhaustive(self, solver):
        mode = self._mode(solver)
        return mode and mode.get('exhaustive')

    def save(self, path=BOOK_PATH):
        with open(path, 'w') as f:
            json.dump(self.data, f, separators=(',', ':'))


def rankings(solver, idx):
    """The one-step top list, and the two-step list for every word either list shows."""
    one = solver.rank_one_step(idx, top=TOP)
    two = solver.rank_two_step(idx, top=solver.TWO_STEP_SHORTLIST)
    # Keep the two-step top list, plus two-step values for the one-step top list's words.
    shown = {s.word for s in one} | {s.word for s in two[:TOP]}
    return one, [s for s in two if s.word in shown]


def build_mode(solver, log=print):
    exhaustive = EXHAUSTIVE.get(solver.name)
    everything = np.arange(len(solver.answers))

    start = time.time()
    one, two = rankings(solver, everything)
    positions = {'': {'one': [_pack(s) for s in one], 'two': [_pack(s) for s in two]}}
    openers = [one[0].word, two[0].word] + ([exhaustive['word']] if exhaustive else [])
    openers = list(dict.fromkeys(openers))
    log(f"[{solver.name}] opening done in {time.time() - start:.0f}s; book openers: {', '.join(openers)}")

    for opener in openers:
        row = solver.guess_index[opener]
        patterns = np.unique(solver.matrix[row])
        start = time.time()
        for pattern in patterns:
            if pattern == ALL_GREEN:
                continue
            history = [(opener, decode(int(pattern)))]
            one, two = rankings(solver, solver.candidates(history))
            positions[position_key(history)] = {'one': [_pack(s) for s in one], 'two': [_pack(s) for s in two]}
        log(f"[{solver.name}] {opener}: {len(patterns)} replies in {time.time() - start:.0f}s")

    return {
        'fingerprint': solver.fingerprint,
        'answers': len(solver.answers),
        'openers': openers,
        'exhaustive': exhaustive,
        'positions': positions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--modes', nargs='+', choices=MODES, default=list(MODES))
    args = parser.parse_args()

    book = OpeningBook.load()
    for mode in args.modes:
        book.data['modes'][mode] = build_mode(WordleSolver.load(mode))
        book.save()  # after each mode, so a long build keeps finished work
    print(f"Wrote {BOOK_PATH} ({BOOK_PATH.stat().st_size / 1e6:.1f} MB)")


if __name__ == '__main__':
    main()
