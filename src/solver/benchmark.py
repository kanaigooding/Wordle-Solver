"""Plays every answer (or a sample) with each strategy and reports how many guesses it took.

    python -m solver.benchmark                      # both strategies, all 2,315 answers
    python -m solver.benchmark --strategy two-step --sample 300
"""
import argparse
import random
import time
from collections import Counter

import numpy as np

from .solver import MODES, WordleSolver

STRATEGIES = ('one-step', 'two-step')
MAX_TURNS = 12


def play(solver, answer, choose):
    """Plays one game against answer and returns the number of guesses used."""
    idx = np.arange(len(solver.answers))
    answer_col = solver.answers.index(answer)
    for turn in range(1, MAX_TURNS + 1):
        guess = choose(idx)
        if guess == answer:
            return turn
        row = solver.guess_index[guess]
        idx = idx[solver.matrix[row, idx] == solver.matrix[row, answer_col]]
    raise RuntimeError(f"{answer!r} not solved in {MAX_TURNS} guesses")


def memoised_chooser(solver, strategy):
    """Wraps solver.choose so positions shared by many games are only solved once."""
    memo = {}

    def choose(idx):
        key = idx.tobytes()
        if key not in memo:
            memo[key] = solver.choose(idx, strategy)
        return memo[key]

    return choose


def run(solver, answers, strategy):
    choose = memoised_chooser(solver, strategy)
    start = time.time()
    results = {answer: play(solver, answer, choose) for answer in answers}
    return results, time.time() - start


def report(strategy, results, seconds):
    counts = Counter(results.values())
    average = sum(results.values()) / len(results)
    failures = sum(n for turns, n in counts.items() if turns > 6)
    print(f"\n{strategy}: {average:.4f} average guesses over {len(results)} games ({seconds:.0f}s)")
    for turns in sorted(counts):
        bar = '#' * max(1, round(60 * counts[turns] / len(results)))
        print(f"  {turns:>2} {counts[turns]:>5}  {bar}")
    print(f"  failures (more than 6 guesses): {failures}")
    worst = sorted(results, key=results.get, reverse=True)[:5]
    print(f"  hardest: {', '.join(f'{w} ({results[w]})' for w in worst)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--strategy', choices=STRATEGIES + ('both',), default='both')
    parser.add_argument('--mode', choices=MODES, default='official')
    parser.add_argument('--sample', type=int, help='play a random sample of this many answers')
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()

    solver = WordleSolver.load(args.mode)
    answers = list(solver.answers)
    if args.mode == 'all':
        # Every valid word is a possible answer here; benchmark on the official list so
        # results are comparable, while the solver still assumes any word could be it.
        from .solver import DATA_DIR, read_words
        answers = read_words(DATA_DIR / 'answers.txt')
    if args.sample:
        answers = random.Random(args.seed).sample(answers, args.sample)

    strategies = STRATEGIES if args.strategy == 'both' else (args.strategy,)
    for strategy in strategies:
        report(strategy, *run(solver, answers, strategy))


if __name__ == '__main__':
    main()
