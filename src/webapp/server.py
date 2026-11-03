"""Local web server for the Wordle Lab UI.

The browser sends the full guess history with every request, so the server keeps no game
state; it only caches one solver per answer mode. Early positions come from the opening
book; anything else is searched live.
"""
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from solver import MODES, WordleSolver
from solver.book import OpeningBook

STATIC_DIR = Path(__file__).resolve().parent / 'static'
MAX_CANDIDATES_SHOWN = 60

BOOK = OpeningBook.load()
_solvers = {}
_load_lock = threading.Lock()
# Live two-step rankings are heavy; run one at a time per mode rather than racing
# duplicate work, without a slow search in one mode blocking the other.
_two_step_locks = {mode: threading.Lock() for mode in MODES}


@asynccontextmanager
async def lifespan(app):
    """Loads the default solver in the background so the first request is quick."""
    threading.Thread(target=get_solver, args=('official',), daemon=True).start()
    yield


app = FastAPI(title='Wordle Lab', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


@app.middleware('http')
async def revalidate_ui_files(request, call_next):
    """Makes browsers check for a newer page and assets on every load, instead of
    reusing a cached copy from an older version of the UI."""
    response = await call_next(request)
    if request.url.path == '/' or request.url.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-cache'
    return response


def get_solver(mode):
    if mode not in MODES:
        raise HTTPException(400, f"Unknown mode {mode!r}")
    with _load_lock:
        if mode not in _solvers:
            _solvers[mode] = WordleSolver.load(mode)
        return _solvers[mode]


class Turn(BaseModel):
    guess: str = Field(min_length=5, max_length=5)
    feedback: str = Field(pattern='^[BYGbyg]{5}$')


class Query(BaseModel):
    mode: str = 'official'
    history: list[Turn] = []
    top: int = Field(10, ge=1, le=50)


def candidates_for(solver, query):
    try:
        return solver.candidates([(turn.guess, turn.feedback) for turn in query.history])
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get('/')
def index():
    return FileResponse(STATIC_DIR / 'index.html')


@app.get('/api/words')
def words():
    """Word lists the browser needs to validate guesses and pick secrets in Play mode."""
    solver = get_solver('official')
    return {'guesses': solver.guesses, 'answers': solver.answers}


@app.post('/api/analyze')
def analyze(query: Query):
    """Remaining candidates, the one-step ranking, and per-turn stats. Fast enough for every turn."""
    solver = get_solver(query.mode)
    idx = candidates_for(solver, query)
    history = [(turn.guess, turn.feedback) for turn in query.history]
    book = BOOK.lookup(solver, history)
    result = {
        'source': 'book' if book else 'live',
        # The proven-optimal opener, where one is known; it only applies to the first move.
        'exhaustive': None if history else BOOK.exhaustive(solver),
        'total': len(solver.answers),
        'total_uncertainty': solver.uncertainty(np.arange(len(solver.answers))),
        'turns': solver.turn_stats(history),
        'remaining': int(len(idx)),
        # Bits still needed to pin down the answer: log2(remaining) when all are equally likely.
        'uncertainty': solver.uncertainty(idx),
    }
    if len(idx) == 0:
        return {**result, 'uniform': True, 'candidates': [], 'one_step': []}

    probs = solver.probabilities(idx)
    order = probs.argsort()[::-1][:MAX_CANDIDATES_SHOWN]
    return {
        **result,
        'uniform': bool(probs.max() - probs.min() < 1e-12),
        'candidates': [{'word': solver.answers[idx[i]], 'p': float(probs[i])} for i in order],
        'one_step': [s.to_dict() for s in (book[0][:query.top] if book else solver.rank_one_step(idx, top=query.top))],
    }


@app.post('/api/two-step')
def two_step(query: Query):
    """The two-step ranking; slower, so the UI requests it after the one-step results.

    Returns the whole shortlist (not just `top`) so the UI can show two-step values next
    to one-step suggestions that didn't make the two-step top list.
    """
    solver = get_solver(query.mode)
    idx = candidates_for(solver, query)
    if len(idx) == 0:
        return {'source': 'live', 'two_step': []}

    book = BOOK.lookup(solver, [(turn.guess, turn.feedback) for turn in query.history])
    if book:
        return {'source': 'book', 'two_step': [s.to_dict() for s in book[1]]}
    with _two_step_locks[query.mode]:
        ranked = solver.rank_two_step(idx, top=solver.TWO_STEP_SHORTLIST)
    return {'source': 'live', 'two_step': [s.to_dict() for s in ranked]}
