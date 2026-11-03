"""Local web server for the Wordle Lab UI.

The browser sends the full guess history with every request, so the server keeps no game
state; it only caches one solver per answer mode.
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

STATIC_DIR = Path(__file__).resolve().parent / 'static'
MAX_CANDIDATES_SHOWN = 60

_solvers = {}
_load_lock = threading.Lock()
# Two-step rankings are heavy; run one at a time rather than racing duplicate work.
_two_step_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    """Loads the default solver and its two-step opening ranking in the background."""
    def warm():
        solver = get_solver('official')
        with _two_step_lock:
            solver.rank_two_step(solver.candidates([]), top=1)

    threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(title='Wordle Lab', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


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
    result = {
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
        'one_step': [s.to_dict() for s in solver.rank_one_step(idx, top=query.top)],
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
        return {'two_step': []}
    with _two_step_lock:
        ranked = solver.rank_two_step(idx, top=solver.TWO_STEP_SHORTLIST)
    return {'two_step': [s.to_dict() for s in ranked]}
