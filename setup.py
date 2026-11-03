from setuptools import setup, find_packages

# The solver reads frequencyMaps/ from the repository root, so install in editable mode:
#   pip install -e .
setup(
    name='wordle-lab',
    version='2.0.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    package_data={'webapp': ['static/*']},
    install_requires=[
        'numpy>=1.24',
        'fastapi>=0.110',
        'uvicorn>=0.27',
    ],
    extras_require={
        'test': ['pytest>=7', 'httpx'],
    },
    entry_points={
        'console_scripts': [
            'wordle-lab=webapp.__main__:main',
            'wordle-benchmark=solver.benchmark:main',
        ],
    },
    python_requires='>=3.10',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
