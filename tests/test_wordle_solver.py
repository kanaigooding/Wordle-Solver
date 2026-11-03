import itertools
import math
import random
from collections import defaultdict

import numpy as np
import pytest

from solver import WordleSolver, decode, encode, feedback
from solver.benchmark import memoised_chooser, play
from solver.patterns import build_pattern_matrix
from solver.solver import DATA_DIR, _sorted_entropies, read_words


@pytest.fixture(scope='module')
def official():
    return WordleSolver.load('official')


@pytest.fixture(scope='module')
def small(tmp_path_factory):
    """A solver over 200 answers and 600 guesses, small enough to brute-force check."""
    rng = random.Random(0)
    answers = rng.sample(read_words(DATA_DIR / 'answers.txt'), 200)
    others = sorted(set(read_words(DATA_DIR / 'validwords.txt')) - set(answers))
    guesses = answers + rng.sample(others, 400)
    return WordleSolver(guesses, answers, cache_dir=tmp_path_factory.mktemp('cache'))


# --- Patterns ------------------------------------------------------------------------

@pytest.mark.parametrize('guess, answer, expected', [
    ('crane', 'crane', 'GGGGG'),
    ('level', 'hello', 'YGBBY'),
    ('speed', 'abide', 'BBYBY'),
    ('eerie', 'there', 'YBYBG'),
    ('llama', 'hello', 'YYBBB'),
])
def test_feedback_handles_repeated_letters(guess, answer, expected):
    assert feedback(guess, answer) == expected


def test_encode_decode_round_trip():
    for colours in map(''.join, itertools.product('BYG', repeat=5)):
        assert decode(encode(colours)) == colours
    assert encode('ggggg') == 242


@pytest.mark.parametrize('bad', ['BYG', 'BYGBX', 'BBBBBB'])
def test_encode_rejects_bad_feedback(bad):
    with pytest.raises(ValueError):
        encode(bad)


def test_pattern_matrix_matches_reference_feedback(small):
    for gi, guess in enumerate(small.guesses):
        for ai, answer in enumerate(small.answers[:40]):
            assert decode(int(small.matrix[gi, ai])) == feedback(guess, answer)


def test_pattern_matrix_handles_chunk_boundaries():
    words = ['level', 'hello', 'eerie', 'there', 'llama', 'speed', 'abide']
    assert (build_pattern_matrix(words, words, chunk_size=3) == build_pattern_matrix(words, words)).all()


# --- Filtering -----------------------------------------------------------------------

@pytest.mark.parametrize('guess, answer', [('level', 'hello'), ('speed', 'abide'), ('soare', 'proud')])
def test_candidates_keep_the_answer(official, guess, answer):
    idx = official.candidates([(guess, feedback(guess, answer))])
    words = {official.answers[i] for i in idx}
    assert answer in words
    assert all(feedback(guess, word) == feedback(guess, answer) for word in words)


def test_candidates_reject_unknown_words(official):
    with pytest.raises(ValueError):
        official.candidates([('zzzzz', 'BBBBB')])


# --- One-step ------------------------------------------------------------------------

def naive_entropy(solver, guess, idx):
    probs = solver.probabilities(idx)
    mass = defaultdict(float)
    for i, p in zip(idx, probs):
        mass[feedback(guess, solver.answers[i])] += p
    return -sum(p * math.log2(p) for p in mass.values())


def test_entropies_match_naive_calculation(small):
    idx = np.arange(len(small.answers))
    bits = small.entropies(idx, small.probabilities(idx))
    for word in ['crane', small.guesses[5], small.guesses[300]]:
        if word in small.guess_index:
            assert bits[small.guess_index[word]] == pytest.approx(naive_entropy(small, word, idx))


def test_sorted_entropies_match_bincount(small):
    rng = np.random.default_rng(1)
    for size in [2, 5, 17, 31]:
        idx = np.sort(rng.choice(len(small.answers), size, replace=False))
        probs = rng.random(size)
        probs /= probs.sum()
        columns = small.matrix[:, idx]
        expected = [naive_entropy_from_columns(columns[r], probs) for r in range(0, len(small.guesses), 50)]
        assert _sorted_entropies(columns, probs)[::50] == pytest.approx(expected)


def naive_entropy_from_columns(patterns, probs):
    mass = defaultdict(float)
    for pattern, p in zip(patterns, probs):
        mass[pattern] += p
    return -sum(p * math.log2(p) for p in mass.values() if p > 0)


def test_opening_one_step_guess_is_soare(official):
    top = official.rank_one_step(official.candidates([]), top=1)[0]
    assert top.word == 'soare'
    assert top.one_step == pytest.approx(5.886, abs=1e-3)


def test_one_step_sums_over_boards(small):
    a = small.candidates([('crane', 'BBBBB')]) if 'crane' in small.guess_index else np.arange(50)
    b = np.arange(len(small.answers))
    bits_a, p_a = small.one_step([a])
    bits_b, p_b = small.one_step([b])
    bits_ab, p_ab = small.one_step([a, b])
    assert bits_ab == pytest.approx(bits_a + bits_b)
    assert p_ab == pytest.approx(p_a + p_b)


def test_useless_guesses_are_not_suggested(official):
    idx = official.candidates([('soare', feedback('soare', 'humid')), ('humor', feedback('humor', 'humid'))])
    suggestions = official.rank_one_step(idx, top=10)
    assert all(s.one_step > 0 or s.p_answer > 0 for s in suggestions)
    if len(idx) == 1:
        assert [s.word for s in suggestions] == ['humid']


# --- Two-step ------------------------------------------------------------------------

def naive_two_step(solver, guess, idx):
    probs = solver.probabilities(idx)
    buckets = defaultdict(list)
    for i in idx:
        buckets[feedback(guess, solver.answers[i])].append(i)
    expected = 0.0
    for colours, members in buckets.items():
        if colours == 'GGGGG' or len(members) == 1:
            continue
        members = np.array(members)
        best = max(naive_entropy(solver, g, members) for g in solver.guesses)
        expected += probs[np.isin(idx, members)].sum() * best
    return naive_entropy(solver, guess, idx) + expected


def test_two_step_matches_naive_calculation(small):
    idx = np.arange(len(small.answers))
    for s in small.rank_two_step(idx, top=3, shortlist=5):
        assert s.two_step == pytest.approx(naive_two_step(small, s.word, idx))


def test_two_step_is_at_least_one_step(small):
    idx = np.arange(len(small.answers))
    for s in small.rank_two_step(idx, top=10, shortlist=20):
        assert s.two_step >= s.one_step - 1e-9


# --- Full games ----------------------------------------------------------------------

@pytest.mark.parametrize('strategy', ['one-step', 'two-step'])
def test_solves_every_answer_in_six(small, strategy):
    choose = memoised_chooser(small, strategy)
    results = {answer: play(small, answer, choose) for answer in small.answers}
    assert max(results.values()) <= 6, {w: n for w, n in results.items() if n > 6}


def test_choose_returns_none_without_candidates(small):
    assert small.choose(np.array([], dtype=int)) is None


def test_load_rejects_unknown_mode():
    with pytest.raises(ValueError):
        WordleSolver.load('nope')


# --- Stats ---------------------------------------------------------------------------

def test_split_stats_match_group_sizes(small):
    idx = np.arange(len(small.answers))
    row = 7
    groups = defaultdict(int)
    for answer in small.answers:
        groups[feedback(small.guesses[row], answer)] += 1
    expected, worst = small.split_stats(idx, [row])
    assert worst[0] == max(groups.values())
    assert expected[0] == pytest.approx(sum(n * n for n in groups.values()) / len(idx))


def test_turn_stats_track_each_guess(official):
    history = [(g, feedback(g, 'proud')) for g in ['soare', 'cutin', 'proud']]
    turns = official.turn_stats(history)
    assert [t['after'] for t in turns] == [59, 3, 1]
    assert turns[0]['before'] == 2315
    assert turns[0]['expected_bits'] == pytest.approx(5.886, abs=1e-3)
    assert turns[0]['actual_bits'] == pytest.approx(math.log2(2315 / 59))
    assert turns[0]['best_word'] == 'soare'
    assert turns[-1]['uncertainty_after'] == 0.0


def test_turn_stats_stop_when_nothing_matches(official):
    turns = official.turn_stats([('soare', 'GGGGB'), ('crane', 'BBBBB')])
    assert len(turns) == 1
    assert turns[0]['after'] == 0
    assert turns[0]['actual_bits'] is None
