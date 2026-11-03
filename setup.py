from setuptools import setup, find_packages

# tkinter ships with Python and cannot be installed from PyPI, so there are no runtime dependencies.
# The solver reads frequencyMaps/ from the repository root, so install in editable mode:
#   pip install -e .
setup(
    name='wordle-quordle-solver',
    version='1.0.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    extras_require={
        'test': ['pytest>=7'],
    },
    entry_points={
        'console_scripts': [
            'wordle_solver_gui=gui.wordle_gui:main',
            'quordle_solver_gui=gui.quordle_gui:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
