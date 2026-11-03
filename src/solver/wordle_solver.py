import json
import math
from collections import defaultdict
from pathlib import Path

# frequencyMaps/ lives at the repository root, two levels above this package.
DATA_DIR = Path(__file__).resolve().parents[2] / 'frequencyMaps'


class WordleSolver:
    BLACK = 'B'
    YELLOW = 'Y'
    GREEN = 'G'

    # Words ranked around COMMON_RANK by corpus frequency get half weight as likely answers;
    # COMMON_SPREAD controls how sharply the weight falls off past that rank.
    COMMON_RANK = 3000
    COMMON_SPREAD = 300

    # Best first guess for the bundled word list and frequency map. Searching all words against
    # all words takes minutes, so it is computed once offline; recompute it if the data changes
    # by calling get_optimal_guess(use_opening_guess=False) on a fresh solver.
    OPENING_GUESS = 'tares'

    def __init__(self, valid_words_file, word_freq_file, opening_guess=OPENING_GUESS):
        self.words = self.load_words(valid_words_file)
        self.word_freq = self.load_freq(word_freq_file)
        self.opening_guess = opening_guess if opening_guess in self.words else None
        self.priors = self.compute_priors()
        self.possible_words = self.words.copy()

    @classmethod
    def from_default_files(cls):
        """Creates a solver from the word list and frequency map bundled in frequencyMaps/."""
        return cls(DATA_DIR / 'validwords.txt', DATA_DIR / 'regularized_word_freq_map.json')

    def load_words(self, file):
        """Loads valid words from a file, one per line."""
        try:
            with open(file, 'r') as f:
                return [line.strip().lower() for line in f if line.strip()]
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Word list {file} not found") from e

    def load_freq(self, file):
        """Loads frequency data from a JSON file."""
        try:
            with open(file, 'r') as f:
                return json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Frequency map {file} not found") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Frequency map {file} is not valid JSON: {e}") from e

    def compute_priors(self):
        """Weights each word by how likely it is to be an answer, using its frequency rank.

        Raw corpus frequencies are extremely skewed ('which' is ~2.5% of the total), so the
        rank is passed through a sigmoid: common words weigh ~1, obscure words ~0.
        """
        ranked = sorted(self.words, key=lambda word: -self.word_freq.get(word, 0))
        return {
            word: 1 / (1 + math.exp((rank - self.COMMON_RANK) / self.COMMON_SPREAD))
            for rank, word in enumerate(ranked)
        }

    def adjust_guess(self, guessed_word, feedback):
        """Keeps only the words that would have produced this feedback for the guessed word."""
        guessed_word = guessed_word.lower()
        feedback = list(feedback)
        self.possible_words = [
            word for word in self.possible_words if self.is_possible(word, guessed_word, feedback)
        ]

    def is_possible(self, word, guessed_word, feedback):
        """Checks if a word is a possible solution based on the guessed word and feedback."""
        return self.get_feedback(guessed_word, word) == list(feedback)

    def answer_probabilities(self):
        """Returns the probability of each remaining word being the answer."""
        weights = {word: self.priors[word] for word in self.possible_words}
        total = sum(weights.values())
        if total == 0:
            return {word: 1 / len(weights) for word in weights}
        return {word: weight / total for word, weight in weights.items()}

    def get_entropy(self, guess, probabilities=None):
        """Calculates the expected information, in bits, from the feedback to a guess."""
        if probabilities is None:
            probabilities = self.answer_probabilities()

        pattern_probs = defaultdict(float)
        for word, p in probabilities.items():
            pattern_probs[''.join(self.get_feedback(guess, word))] += p

        return -sum(p * math.log2(p) for p in pattern_probs.values() if p > 0)

    def get_optimal_guess(self, use_opening_guess=True):
        """Picks the guess that maximises expected information plus the chance of winning now."""
        if not self.possible_words:
            return None

        if use_opening_guess and self.opening_guess and len(self.possible_words) == len(self.words):
            return self.opening_guess

        probabilities = self.answer_probabilities()
        if len(self.possible_words) <= 2:
            return max(probabilities, key=probabilities.get)

        max_score = -1
        best_guess = None
        for word in self.words:
            score = self.get_entropy(word, probabilities) + probabilities.get(word, 0)
            if score > max_score:
                max_score = score
                best_guess = word

        return best_guess

    def get_feedback(self, guess, actual):
        """Generates feedback for a guess compared to the actual word."""
        feedback = [self.BLACK] * len(guess)
        unmatched = []
        for i, (g_char, a_char) in enumerate(zip(guess, actual)):
            if g_char == a_char:
                feedback[i] = self.GREEN
            else:
                unmatched.append(a_char)

        for i, g_char in enumerate(guess):
            if feedback[i] != self.GREEN and g_char in unmatched:
                feedback[i] = self.YELLOW
                unmatched.remove(g_char)

        return feedback

    def reset(self):
        """Resets the possible words to the original list."""
        self.possible_words = self.words.copy()
