import pytest
from fastapi.testclient import TestClient

from solver import feedback
from webapp.server import app

# Not used as a context manager, so the startup warm-up thread doesn't run.
client = TestClient(app)


def turn(guess, answer):
    return {'guess': guess, 'feedback': feedback(guess, answer)}


def test_index_serves_the_ui():
    response = client.get('/')
    assert response.status_code == 200
    assert 'Wordle Lab' in response.text


def test_words_lists_guesses_and_answers():
    data = client.get('/api/words').json()
    assert len(data['answers']) == 2315
    assert set(data['answers']) <= set(data['guesses'])


def test_analyze_filters_and_ranks():
    data = client.post('/api/analyze', json={'history': [turn('soare', 'proud')]}).json()
    assert data['remaining'] == 59
    assert 'proud' in {c['word'] for c in data['candidates']}
    assert data['one_step'][0]['word'] == 'cutin'
    assert data['one_step'][0]['worst_left'] >= data['one_step'][0]['expected_left'] > 0
    assert data['total'] == 2315
    assert [t['after'] for t in data['turns']] == [59]


def test_analyze_reports_no_matches():
    data = client.post('/api/analyze', json={'history': [{'guess': 'soare', 'feedback': 'GGGGB'}]}).json()
    assert data['remaining'] == 0
    assert data['one_step'] == []


def test_two_step_returns_shortlist():
    data = client.post('/api/two-step', json={'history': [turn('soare', 'proud')]}).json()
    assert data['two_step'][0]['word'] == 'futon'
    assert all(s['two_step'] is not None for s in data['two_step'])


@pytest.mark.parametrize('body', [
    {'history': [{'guess': 'zzzzz', 'feedback': 'BBBBB'}]},
    {'history': [{'guess': 'soare', 'feedback': 'BBXBB'}]},
    {'mode': 'nope'},
])
def test_bad_requests_are_rejected(body):
    assert client.post('/api/analyze', json=body).status_code in (400, 422)
