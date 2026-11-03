"""Entropy-based guess ranking on top of the precomputed pattern matrix.

Two strategies are compared side by side:

- One-step: H1(g), the expected information (bits) from the colours guess g produces.
- Two-step: H1(g) plus the expected information from the best follow-up guess, averaged
  over every colour pattern g could produce.

Both scores add P(g), the chance g is the answer, so that late in the game a guess that
could win outright beats an equally informative guess that cannot.
"""
import hashlib
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

from .patterns import ALL_GREEN, NUM_PATTERNS, encode, load_pattern_matrix

REPO_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_DIR / 'frequencyMaps'
CACHE_DIR = REPO_DIR / '.cache'

MODES = ('official', 'all')

# Bound on how many matrix cells one bincount call handles, to keep memory use flat.
_CELLS_PER_CHUNK = 4_000_000
# Below this many candidates, sorting each row beats bincounting into 243 bins per row.
_SORT_THRESHOLD = 32


@dataclass
class Suggestion:
    word: str
    one_step: float
    two_step: float | None
    p_answer: float
    # How many answers this guess is expected to leave, and how many in the worst case.
    expected_left: float | None = None
    worst_left: int | None = None

    @property
    def one_step_score(self):
        return self.one_step + self.p_answer

    @property
    def two_step_score(self):
        return None if self.two_step is None else self.two_step + self.p_answer

    def to_dict(self):
        return asdict(self)


class WordleSolver:
    # In 'all' mode every valid word could be the answer, weighted by commonness: words ranked
    # around COMMON_RANK by corpus frequency get half weight, falling off over COMMON_SPREAD ranks.
    COMMON_RANK = 3000
    COMMON_SPREAD = 300

    # Two-step lookahead is only run on this many of the best one-step guesses.
    TWO_STEP_SHORTLIST = 50

    def __init__(self, guesses, answers, weights=None, cache_dir=CACHE_DIR, name='custom'):
        self.name = name
        self.cache_dir = Path(cache_dir)
        self.answers = list(answers)
        missing = sorted(set(self.answers) - set(guesses))
        self.guesses = list(guesses) + missing
        self.guess_index = {word: i for i, word in enumerate(self.guesses)}
        self.answer_rows = np.array([self.guess_index[word] for word in self.answers])

        weights = np.ones(len(self.answers)) if weights is None else np.asarray(weights, dtype=float)
        self.weights = weights / weights.sum()

        self.matrix = load_pattern_matrix(self.guesses, self.answers, self.cache_dir)
        self._best_entropy_memo = {}
        self._opening_one_step = None

    @property
    def fingerprint(self):
        """Identifies the word lists and weights, so precomputed results can be checked against them."""
        digest = hashlib.sha1('\n'.join(self.guesses + ['|'] + self.answers).encode())
        digest.update(np.round(self.weights, 12).tobytes())
        return digest.hexdigest()[:16]

    @classmethod
    def load(cls, mode='official'):
        """Creates a solver over the bundled data. 'official' uses the 2,315 Wordle answers;
        'all' treats every valid word as a possible answer, weighted by how common it is."""
        guesses = read_words(DATA_DIR / 'validwords.txt')
        if mode == 'official':
            return cls(guesses, read_words(DATA_DIR / 'answers.txt'), name=mode)
        if mode == 'all':
            with open(DATA_DIR / 'regularized_word_freq_map.json') as f:
                freq = json.load(f)
            return cls(guesses, guesses, weights=cls.commonness_weights(guesses, freq), name=mode)
        raise ValueError(f"Unknown mode {mode!r}; expected one of {MODES}")

    @classmethod
    def commonness_weights(cls, words, freq):
        """Weights words by frequency rank through a sigmoid: common ~1, obscure ~0."""
        ranked = sorted(range(len(words)), key=lambda i: -freq.get(words[i], 0))
        weights = np.empty(len(words))
        for rank, i in enumerate(ranked):
            weights[i] = 1 / (1 + math.exp((rank - cls.COMMON_RANK) / cls.COMMON_SPREAD))
        return weights

    # --- Filtering -----------------------------------------------------------------------

    def candidates(self, history):
        """Returns the indices of answers consistent with [(guess, colours), ...]."""
        idx = np.arange(len(self.answers))
        for guess, colours in history:
            row = self.guess_index.get(guess.lower())
            if row is None:
                raise ValueError(f"{guess!r} is not in the word list")
            idx = idx[self.matrix[row, idx] == encode(colours)]
        return idx

    def probabilities(self, idx):
        """Returns the probability of each candidate in idx being the answer."""
        weights = self.weights[idx]
        total = weights.sum()
        return weights / total if total > 0 else np.full(len(idx), 1 / len(idx))

    # --- One-step ------------------------------------------------------------------------

    def entropies(self, idx, probs, rows=None):
        """Expected information, in bits, of each guess (or each guess in rows) over candidates idx."""
        num_rows = len(self.guesses) if rows is None else len(rows)
        out = np.zeros(num_rows)
        if len(idx) <= 1:
            return out

        # Pick columns first: slicing rows of the full matrix would copy all of it.
        columns = self.matrix[:, idx] if rows is None else self.matrix[np.asarray(rows)][:, idx]
        if len(idx) <= _SORT_THRESHOLD:
            return _sorted_entropies(columns, probs)

        per_chunk = max(1, _CELLS_PER_CHUNK // len(idx))
        for start in range(0, num_rows, per_chunk):
            block = columns[start:start + per_chunk].astype(np.int32)
            n = len(block)
            block += (np.arange(n, dtype=np.int32) * NUM_PATTERNS)[:, None]
            mass = np.bincount(block.ravel(), weights=np.broadcast_to(probs, block.shape).ravel(),
                               minlength=n * NUM_PATTERNS).reshape(n, NUM_PATTERNS)
            logs = np.zeros_like(mass)
            np.log2(mass, out=logs, where=mass > 0)
            out[start:start + n] = -(mass * logs).sum(axis=1)
        return out

    def one_step(self, boards):
        """Scores every guess across one or more boards (each a candidate index array).

        Returns (bits, p_answer), arrays over all guesses. With several boards the bits and
        win chances are summed, which is the n-ordle generalisation of one-step entropy.
        """
        if len(boards) == 1 and len(boards[0]) == len(self.answers) and self._opening_one_step is not None:
            return self._opening_one_step

        bits = np.zeros(len(self.guesses))
        p_answer = np.zeros(len(self.guesses))
        for idx in boards:
            probs = self.probabilities(idx)
            bits += self.entropies(idx, probs)
            p_answer[self.answer_rows[idx]] += probs

        if len(boards) == 1 and len(boards[0]) == len(self.answers):
            self._opening_one_step = bits, p_answer
        return bits, p_answer

    def uncertainty(self, idx):
        """Bits still needed to pin down the answer among candidates idx."""
        probs = self.probabilities(idx) if len(idx) else np.zeros(0)
        return max(0.0, float(-(probs * np.log2(probs, where=probs > 0, out=np.zeros_like(probs))).sum()))

    def split_stats(self, idx, rows):
        """For each guess in rows: the expected and worst-case number of candidates left after it."""
        probs = self.probabilities(idx)
        expected = np.zeros(len(rows))
        worst = np.zeros(len(rows), dtype=int)
        for i, row in enumerate(rows):
            patterns = self.matrix[row, idx]
            counts = np.bincount(patterns, minlength=NUM_PATTERNS)
            mass = np.bincount(patterns, weights=probs, minlength=NUM_PATTERNS)
            # Each colour pattern leaves its group behind; weight that group's size by its chance.
            expected[i] = float((mass * counts).sum())
            worst[i] = int(counts.max())
        return expected, worst

    def turn_stats(self, history):
        """How each guess in history did: expected vs actual bits, and answers left afterwards."""
        idx = np.arange(len(self.answers))
        turns = []
        for guess, colours in history:
            row = self.guess_index.get(guess.lower())
            if row is None:
                raise ValueError(f"{guess!r} is not in the word list")
            probs = self.probabilities(idx)
            bits, p_answer = self.one_step([idx])
            best_row = int(np.argmax(bits + p_answer))

            matched = self.matrix[row, idx] == encode(colours)
            seen = float(probs[matched].sum())
            after = idx[matched]
            turns.append({
                'guess': guess.lower(),
                'feedback': colours.upper(),
                'before': int(len(idx)),
                'after': int(len(after)),
                'expected_bits': float(bits[row]),
                'best_word': self.guesses[best_row],
                'best_bits': float(bits[best_row]),
                # The surprise of the colours that actually came back: log2(1 / their chance).
                'actual_bits': -math.log2(seen) if seen > 0 else None,
                'uncertainty_after': self.uncertainty(after),
            })
            idx = after
            if len(idx) == 0:
                break
        return turns

    # --- Two-step ------------------------------------------------------------------------

    def best_entropy(self, idx, probs):
        """The highest one-step entropy any guess achieves over candidates idx (memoised)."""
        if len(idx) <= 1:
            return 0.0
        if len(idx) == 2:
            # Guessing either candidate always separates the pair.
            p = probs / probs.sum()
            return float(-(p * np.log2(p)).sum())

        key = idx.tobytes()
        best = self._best_entropy_memo.get(key)
        if best is None:
            if len(self._best_entropy_memo) > 500_000:
                self._best_entropy_memo.clear()
            probs = probs / probs.sum()
            # No guess can do better than splitting every candidate apart. The candidates
            # themselves often manage that, so try them before scanning every guess.
            ceiling = float(-(probs * np.log2(probs, where=probs > 0, out=np.zeros_like(probs))).sum())
            best = float(self.entropies(idx, probs, rows=self.answer_rows[idx]).max())
            if best < ceiling - 1e-9:
                best = float(self.entropies(idx, probs).max())
            self._best_entropy_memo[key] = best
        return best

    def two_step(self, idx, probs, rows, first_bits):
        """Two-step bits for each guess in rows: its own bits plus the expected best follow-up."""
        out = np.empty(len(rows))
        for i, row in enumerate(rows):
            patterns = self.matrix[row, idx]
            order = np.argsort(patterns, kind='stable')
            sorted_patterns = patterns[order]
            starts = np.flatnonzero(np.r_[True, sorted_patterns[1:] != sorted_patterns[:-1]])
            ends = np.r_[starts[1:], len(order)]

            expected = 0.0
            for start, end in zip(starts, ends):
                if sorted_patterns[start] == ALL_GREEN or end - start == 1:
                    continue
                members = order[start:end]
                bucket_probs = probs[members]
                expected += bucket_probs.sum() * self.best_entropy(idx[members], bucket_probs)
            out[i] = first_bits[i] + expected
        return out

    # --- Rankings ------------------------------------------------------------------------

    def rank_one_step(self, idx, top=10):
        """The top guesses for a single board by one-step score."""
        bits, p_answer = self.one_step([idx])
        rows = self._top_rows(bits + p_answer, top)
        return self._with_stats(idx, [Suggestion(self.guesses[r], float(bits[r]), None, float(p_answer[r])) for r in rows])

    def rank_two_step(self, idx, top=10, shortlist=None):
        """The top guesses for a single board by two-step score.

        Two-step lookahead runs on the best `shortlist` guesses by one-step score; with very
        few candidates left it is the same as one-step, so it short-circuits.
        """
        shortlist = shortlist or self.TWO_STEP_SHORTLIST
        cached = self._load_opening(shortlist) if len(idx) == len(self.answers) else None
        if cached is not None:
            return self._with_stats(idx, cached[:top])

        probs = self.probabilities(idx)
        bits, p_answer = self.one_step([idx])
        rows = self._top_rows(bits + p_answer, shortlist)
        second = self.two_step(idx, probs, rows, bits[rows])
        ranked = sorted(
            (Suggestion(self.guesses[r], float(bits[r]), float(s), float(p_answer[r])) for r, s in zip(rows, second)),
            key=lambda s: -s.two_step_score,
        )
        if len(idx) == len(self.answers):
            self._save_opening(shortlist, ranked)
        return self._with_stats(idx, ranked[:top])

    def _with_stats(self, idx, suggestions):
        expected, worst = self.split_stats(idx, [self.guess_index[s.word] for s in suggestions])
        for s, e, w in zip(suggestions, expected, worst):
            s.expected_left, s.worst_left = float(e), int(w)
        return suggestions

    def best_guess(self, history, strategy='one-step'):
        """The single best next guess, or None if no answer fits the history."""
        return self.choose(self.candidates(history), strategy)

    def choose(self, idx, strategy='one-step'):
        """The single best guess over candidates idx, or None if idx is empty."""
        if len(idx) == 0:
            return None
        if len(idx) <= 2:
            return self.answers[idx[np.argmax(self.probabilities(idx))]]
        if strategy == 'one-step':
            return self.rank_one_step(idx, top=1)[0].word
        if strategy == 'two-step':
            return self.rank_two_step(idx, top=1)[0].word
        raise ValueError(f"Unknown strategy {strategy!r}")

    def _top_rows(self, scores, n):
        n = min(n, len(scores))
        rows = np.argpartition(-scores, n - 1)[:n]
        # A guess with no information and no chance of winning is never worth suggesting.
        rows = [r for r in rows if scores[r] > 1e-12]
        # Sort by score, then alphabetically so ties are stable across runs.
        return sorted(rows, key=lambda r: (-scores[r], self.guesses[r]))

    # --- Opening cache -------------------------------------------------------------------
    # The two-step opening ranking takes a while to compute, and never changes for a
    # given word list, so it is stored next to the pattern matrix.

    def _opening_path(self, shortlist):
        return self.cache_dir / f'two-step-opening-{self.name}-{len(self.answers)}-{shortlist}.json'

    def _load_opening(self, shortlist):
        if self.name == 'custom':
            return None
        path = self._opening_path(shortlist)
        if not path.exists():
            return None
        with open(path) as f:
            return [Suggestion(**row) for row in json.load(f)]

    def _save_opening(self, shortlist, ranked):
        if self.name == 'custom':
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self._opening_path(shortlist), 'w') as f:
            json.dump([s.to_dict() for s in ranked], f, indent=1)


def _sorted_entropies(columns, probs):
    """Entropy of each row of a (rows, k) pattern block, by sorting; faster than bincount for small k."""
    order = np.argsort(columns, axis=1, kind='stable')
    patterns = np.take_along_axis(columns, order, axis=1)
    cumulative = np.cumsum(probs[order], axis=1)

    # A group of equal patterns ends where the next pattern differs; its mass is the
    # cumulative probability there minus the cumulative probability at the previous end.
    is_end = np.ones(patterns.shape, dtype=bool)
    is_end[:, :-1] = patterns[:, 1:] != patterns[:, :-1]
    end_values = np.where(is_end, cumulative, 0.0)
    previous_end = np.zeros_like(cumulative)
    previous_end[:, 1:] = np.maximum.accumulate(end_values[:, :-1], axis=1)
    mass = np.where(is_end, cumulative - previous_end, 0.0)

    logs = np.zeros_like(mass)
    np.log2(mass, out=logs, where=mass > 0)
    return -(mass * logs).sum(axis=1)


def read_words(path):
    with open(path) as f:
        return [line.strip().lower() for line in f if line.strip()]
