# src/solver/__init__.py

from .patterns import decode, encode, feedback
from .solver import MODES, Suggestion, WordleSolver

__all__ = ['WordleSolver', 'Suggestion', 'MODES', 'feedback', 'encode', 'decode']
