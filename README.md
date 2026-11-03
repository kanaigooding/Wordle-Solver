# Wordle & Quordle Solver

This repository contains a Wordle and Quordle solver implemented in Python. It includes a graphical user interface (GUI) for both games, allowing users to interactively solve Wordle and Quordle puzzles.

## Table of Contents
- Introduction
- Features
- Installation
- Usage
- Directory Structure
- Contributing
- License

## Introduction

The Wordle and Quordle solvers use frequency analysis of words and letters to optimize guesses and provide feedback to help users find the correct words. The GUI is built using `tkinter`, providing an easy-to-use interface for solving the puzzles interactively.

## Features

- Wordle Solver GUI: A GUI to solve Wordle puzzles.
- Quordle Solver GUI: A GUI to solve Quordle puzzles.
- Frequency Analysis: Uses word and letter frequency maps to optimize guesses.
- Interactive Feedback: Provides feedback on guesses to help narrow down possible solutions.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/your-username/wordle-quordle-solver.git
    cd wordle-quordle-solver
    ```

2. The solver and GUIs only need the standard library (`tkinter` ships with Python). To run the tests, install pytest:
    ```bash
    pip install -r requirements.txt
    ```

3. Optionally, install the package in editable mode to get the `wordle_solver_gui` and `quordle_solver_gui` commands:
    ```bash
    pip install -e .
    ```

## Running the tests

```bash
python -m pytest
```

## Usage

### Wordle Solver

To run the Wordle Solver GUI, use the following command:
```bash
python src/gui/wordle_gui.py
```

### Quordle Solver

To run the Quordle Solver GUI, use the following command:
```bash
python src/gui/quordle_gui.py
```

## Directory Structure

```
wordle-quordle-solver/
├── frequencyMaps/
│   ├── validwords.txt
│   ├── word_freq_map.json
│   ├── letter_freq_map.json
│   ├── regularized_word_freq_map.json
│   ├── regularized_letter_freq_map.json
├── src/
│   ├── gui/
│   │   ├── quordle_gui.py
│   │   ├── wordle_gui.py
│   │   ├── __init__.py
│   ├── solver/
│   │   ├── wordle_solver.py
│   │   ├── __init__.py
├── tests/
│   ├── test_wordle_solver.py
├── pytest.ini
├── README.md
├── requirements.txt
├── .gitignore
├── setup.py
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or new features.

1. Fork the repository
2. Create a new branch (`git checkout -b feature-branch`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature-branch`)
5. Open a pull request
