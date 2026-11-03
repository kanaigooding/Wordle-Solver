# Wordle Lab

An experiment in information-theoretic Wordle solving. Wordle Lab ranks every possible guess two ways and shows them side by side:

- **One-step entropy:** the expected information (in bits) from the colours a guess produces.
- **Two-step entropy:** that, plus the expected information from the best follow-up guess, averaged over every colour pattern the first guess could produce.

Both add the chance the guess is the answer itself, so that late in a game a guess that could win outright beats an equally informative one that can't.

It comes with a local web UI for using the solver on a real game or watching it play, and a benchmark that plays every answer with each strategy.

## Installation

```bash
git clone https://github.com/kanaigooding/Wordle-Solver.git
cd Wordle-Solver
pip install -r requirements.txt
```

Optionally install in editable mode to get the `wordle-lab` and `wordle-benchmark` commands:

```bash
pip install -e .
```

## Usage

### Web UI

```bash
python src/webapp
```

This opens `http://127.0.0.1:8000`. The first launch builds and caches the pattern matrix (about 7 seconds for Original answers, about 40 seconds for All words).

- **Assist mode:** type the guess you made in the real game, click the tiles (or press `1`–`5`) to match its colours, then press `Enter`.
- **Play mode:** the app picks a hidden answer and colours your guesses for you.
- `Tab` fills in the top suggestion for the selected strategy; clicking any suggestion or possible answer does the same.
- **Original answers** assumes the 2,315 answers from Wordle's original list. The NYT has since used some words outside it; if none of the original answers fit your colours, the app switches to **All words**, which treats any of the 12,953 valid words as possible, weighted by how common it is.
- On the first move, the **Exhaustive best** card shows SALET: the opener proven optimal by exhaustive search (3.4212 average guesses on the original list; Selby 2022, confirmed by Bertsimas & Paskov, *Operations Research* 2024).

### Opening book

Like a chess opening book, the first two turns are looked up rather than searched. `frequencyMaps/opening_book.json` holds the one-step and two-step rankings for the opening position and for every reply to each book opener (SOARE, SLANE and SALET for Original answers; TARES for All words). Any other position, and every position from turn 3 on, is searched live; the Suggestions header shows which.

The book is tied to the word lists and weights it was built from, and is ignored if they change. Rebuild it with:

```bash
cd src
python -m solver.book    # a few minutes; on a machine without .cache/, the All words two-step opening adds about 40 minutes
```

### Benchmark

```bash
cd src
python -m solver.benchmark                    # both strategies, all 2,315 answers
python -m solver.benchmark --strategy two-step --sample 300
```

### Tests

```bash
python -m pytest
```

## How it works

Every (guess, answer) pair's colour pattern is precomputed into a 12,953 × 2,315 matrix of pattern numbers (0–242), cached in `.cache/`. Filtering candidates and computing entropy for every guess then become numpy array operations; a one-step ranking takes about 20 ms after the first guess. Two-step lookahead runs on the 50 best one-step guesses and is memoised by candidate set.

## Directory Structure

```
Wordle-Solver/
├── frequencyMaps/
│   ├── answers.txt                     # the 2,315 original Wordle answers
│   ├── opening_book.json               # precomputed rankings for the first two turns
│   ├── validwords.txt                  # all 12,953 accepted guesses
│   ├── regularized_word_freq_map.json  # word frequencies, for "All words" mode
│   └── ...
├── src/
│   ├── solver/
│   │   ├── patterns.py                 # feedback rules and the pattern matrix
│   │   ├── solver.py                   # one-step and two-step ranking
│   │   ├── book.py                     # builds and reads the opening book
│   │   └── benchmark.py                # plays every answer with each strategy
│   └── webapp/
│       ├── server.py                   # FastAPI backend
│       └── static/                     # HTML, CSS and JS front end
├── tests/
├── pytest.ini
├── requirements.txt
└── setup.py
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or new features.

1. Fork the repository
2. Create a new branch (`git checkout -b feature-branch`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature-branch`)
5. Open a pull request
