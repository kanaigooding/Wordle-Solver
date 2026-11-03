import json

import pytest

from solver import WordleSolver
from solver.wordle_solver import DATA_DIR

MAX_GUESSES = 10


def simulate_game(solver, target_word, max_guesses=MAX_GUESSES):
    """Plays one game against target_word and returns the number of guesses used."""
    solver.reset()
    for guess_count in range(1, max_guesses + 1):
        guess = solver.get_optimal_guess()
        if guess is None:
            raise AssertionError(f"Solver ran out of words before finding {target_word!r}")
        if guess == target_word:
            return guess_count
        solver.adjust_guess(guess, solver.get_feedback(guess, target_word))
    raise AssertionError(f"Solver did not find {target_word!r} in {max_guesses} guesses")


@pytest.fixture(scope='module')
def solver():
    return WordleSolver.from_default_files()


@pytest.fixture(scope='module')
def small_solver(tmp_path_factory):
    """A solver over the 300 most common words, so full games run quickly."""
    with open(DATA_DIR / 'regularized_word_freq_map.json') as f:
        freq = json.load(f)
    with open(DATA_DIR / 'validwords.txt') as f:
        words = [line.strip() for line in f if line.strip()]
    common = sorted(words, key=lambda word: -freq.get(word, 0))[:300]

    data_dir = tmp_path_factory.mktemp('data')
    (data_dir / 'words.txt').write_text('\n'.join(common))
    (data_dir / 'freq.json').write_text(json.dumps({word: freq[word] for word in common}))
    return WordleSolver(data_dir / 'words.txt', data_dir / 'freq.json', opening_guess=None)


@pytest.mark.parametrize('guess, actual, expected', [
    ('crane', 'crane', 'GGGGG'),
    ('level', 'hello', 'YGBBY'),
    ('speed', 'abide', 'BBYBY'),
    ('eerie', 'there', 'YBYBG'),
    ('llama', 'hello', 'YYBBB'),
])
def test_get_feedback_handles_repeated_letters(solver, guess, actual, expected):
    assert ''.join(solver.get_feedback(guess, actual)) == expected


@pytest.mark.parametrize('guess, answer', [
    ('level', 'hello'),
    ('speed', 'abide'),
    ('eerie', 'there'),
    ('tares', 'proud'),
])
def test_adjust_guess_keeps_the_answer(solver, guess, answer):
    solver.reset()
    solver.adjust_guess(guess, solver.get_feedback(guess, answer))
    assert answer in solver.possible_words
    assert all(
        solver.get_feedback(guess, word) == solver.get_feedback(guess, answer)
        for word in solver.possible_words
    )


def test_adjust_guess_accepts_uppercase_and_string_feedback(solver):
    solver.reset()
    solver.adjust_guess('LEVEL', 'YGBBY')
    assert 'hello' in solver.possible_words


def test_optimal_guess_is_none_when_no_words_remain(solver):
    solver.reset()
    solver.possible_words = []
    assert solver.get_optimal_guess() is None


def test_first_guess_uses_opening_guess(solver):
    solver.reset()
    assert solver.get_optimal_guess() == WordleSolver.OPENING_GUESS


def test_solves_common_words(small_solver):
    targets = small_solver.words[::15]
    results = {target: simulate_game(small_solver, target) for target in targets}
    assert max(results.values()) <= 6, results


def test_missing_word_list_raises():
    with pytest.raises(FileNotFoundError):
        WordleSolver('does-not-exist.txt', DATA_DIR / 'regularized_word_freq_map.json')
