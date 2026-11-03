import numpy as np
import pytest

from solver import WordleSolver, feedback
from solver.book import OpeningBook, position_key, rankings


@pytest.fixture(scope='module')
def official():
    return WordleSolver.load('official')


@pytest.fixture(scope='module')
def book():
    return OpeningBook.load()


def test_position_key():
    assert position_key([]) == ''
    assert position_key([('SOARE', 'byybb')]) == 'soare:BYYBB'
    assert position_key([('soare', 'BYBYB'), ('cutin', 'BYBBB')]) == 'soare:BYBYB,cutin:BYBBB'


@pytest.mark.parametrize('history', [
    [],
    [('soare', feedback('soare', 'proud'))],
    [('slane', feedback('slane', 'humid'))],
    [('salet', feedback('salet', 'crane'))],
])
def test_book_matches_live_search(official, book, history):
    one, two = book.lookup(official, history)
    live_one, live_two = rankings(official, official.candidates(history))
    assert [s.word for s in one] == [s.word for s in live_one]
    assert [s.word for s in two] == [s.word for s in live_two]
    assert [s.one_step for s in one] == pytest.approx([s.one_step for s in live_one], abs=1e-4)
    assert [s.two_step for s in two] == pytest.approx([s.two_step for s in live_two], abs=1e-4)


def test_book_covers_every_reply_to_each_opener(official, book):
    mode = book.data['modes']['official']
    assert mode['openers'] == ['soare', 'slane', 'salet']
    for opener in mode['openers']:
        patterns = {feedback(opener, answer) for answer in official.answers} - {'GGGGG'}
        for colours in patterns:
            assert book.lookup(official, [(opener, colours)]) is not None


def test_positions_outside_the_book_return_none(official, book):
    assert book.lookup(official, [('crane', feedback('crane', 'proud'))]) is None
    history = [('soare', feedback('soare', 'proud')), ('cutin', feedback('cutin', 'proud'))]
    assert book.lookup(official, history) is None


def test_book_is_ignored_for_different_data(official, book, tmp_path):
    other = WordleSolver(official.guesses, official.answers[:-1], cache_dir=tmp_path, name='official')
    assert book.lookup(other, []) is None
    assert book.exhaustive(other) is None


def test_exhaustive_opener_is_salet(official, book):
    assert book.exhaustive(official)['word'] == 'salet'
