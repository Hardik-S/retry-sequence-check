# Launch notes

## Quick start

Create a fresh Python 3.10+ virtual environment, activate it, and run `python -m pip install .`. Then check the included fixture with `retry-sequence-check examples/valid.jsonl`.

## Output and limits

Exit codes are 0 for valid input, 1 for sequence issues, and 2 for invalid input or command usage. Output is machine-readable JSON. The tool validates normalized attempt numbers only; it neither executes retries nor makes claims about retry safety or outcomes.
