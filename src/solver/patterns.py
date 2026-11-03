"""Wordle feedback patterns and the precomputed guess x answer pattern matrix.

A pattern is the row of colours Wordle shows for one guess. It is stored as an int in
base 3, one digit per position (B=0, Y=1, G=2, position 0 is the lowest digit), so every
5-letter pattern fits in 0..242 and the matrix can be a compact uint8 array.
"""
import hashlib
from pathlib import Path

import numpy as np

BLACK, YELLOW, GREEN = 'B', 'Y', 'G'
WORD_LENGTH = 5
NUM_PATTERNS = 3 ** WORD_LENGTH
ALL_GREEN = NUM_PATTERNS - 1

_DIGITS = {BLACK: 0, YELLOW: 1, GREEN: 2}
_COLOURS = {digit: colour for colour, digit in _DIGITS.items()}
_POWERS = 3 ** np.arange(WORD_LENGTH)


def feedback(guess, answer):
    """Returns the colours Wordle shows for guess against answer, e.g. 'YGBBY'.

    Greens are assigned first; each remaining answer letter then turns at most one
    guess letter yellow, left to right, which is how repeated letters are handled.
    """
    colours = [BLACK] * len(guess)
    unmatched = []
    for i, (g_char, a_char) in enumerate(zip(guess, answer)):
        if g_char == a_char:
            colours[i] = GREEN
        else:
            unmatched.append(a_char)

    for i, g_char in enumerate(guess):
        if colours[i] != GREEN and g_char in unmatched:
            colours[i] = YELLOW
            unmatched.remove(g_char)

    return ''.join(colours)


def encode(colours):
    """Converts a colour string like 'YGBBY' to its pattern number."""
    colours = colours.upper()
    if len(colours) != WORD_LENGTH or any(c not in _DIGITS for c in colours):
        raise ValueError(f"Feedback must be {WORD_LENGTH} of B/Y/G, got {colours!r}")
    return sum(_DIGITS[c] * 3 ** i for i, c in enumerate(colours))


def decode(pattern):
    """Converts a pattern number back to its colour string."""
    return ''.join(_COLOURS[(pattern // 3 ** i) % 3] for i in range(WORD_LENGTH))


def words_to_array(words):
    """Encodes words as an (n, WORD_LENGTH) array of letter indices 0..25."""
    return np.array([[ord(c) - ord('a') for c in word] for word in words], dtype=np.int8)


def build_pattern_matrix(guesses, answers, chunk_size=256):
    """Computes the pattern for every (guess, answer) pair as a (len(guesses), len(answers)) uint8 array."""
    guess_letters = words_to_array(guesses)
    answer_letters = words_to_array(answers)
    num_answers = len(answers)

    # answer_onehot[a, j, letter] is True when answer a has that letter at position j.
    answer_onehot = np.zeros((num_answers, WORD_LENGTH, 26), dtype=bool)
    answer_onehot[np.arange(num_answers)[:, None], np.arange(WORD_LENGTH)[None, :], answer_letters] = True

    matrix = np.empty((len(guesses), num_answers), dtype=np.uint8)
    for start in range(0, len(guesses), chunk_size):
        chunk = guess_letters[start:start + chunk_size]
        rows = np.arange(len(chunk))[:, None]
        cols = np.arange(num_answers)[None, :]

        green = chunk[:, None, :] == answer_letters[None, :, :]
        codes = (green * (2 * _POWERS)).sum(axis=-1)

        # How many of each letter in the answer are still unmatched after greens.
        unmatched = np.zeros((len(chunk), num_answers, 26), dtype=np.int8)
        for j in range(WORD_LENGTH):
            unmatched += ~green[:, :, j, None] & answer_onehot[None, :, j, :]

        for j in range(WORD_LENGTH):
            letter = chunk[:, j, None]
            yellow = ~green[:, :, j] & (unmatched[rows, cols, letter] > 0)
            codes += yellow * _POWERS[j]
            unmatched[rows, cols, letter] -= yellow

        matrix[start:start + len(chunk)] = codes

    return matrix


def load_pattern_matrix(guesses, answers, cache_dir):
    """Loads the pattern matrix from cache_dir, building and saving it on first use."""
    digest = hashlib.sha1('\n'.join(guesses + ['|'] + answers).encode()).hexdigest()[:16]
    path = Path(cache_dir) / f'patterns-{digest}.npy'
    if path.exists():
        return np.load(path)

    matrix = build_pattern_matrix(guesses, answers)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, matrix)
    return matrix
