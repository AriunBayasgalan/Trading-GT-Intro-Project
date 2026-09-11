# Interactive Price Simulation Research Notebook

This project is a small marimo notebook for exploring synthetic market-price behavior using a random-walk model.

## What it does

- Generates a simulated price series from a Gaussian random walk
- Lets you adjust the number of observations, volatility, seed, and moving-average window
- Computes summary statistics like min, max, mean, and standard deviation
- Plots the simulated price path against a simple moving average using Altair
- Displays a reactive experiment summary in the notebook UI

## Tech stack

- `marimo`
- `numpy`
- `polars`
- `altair`
- `pandas`
- `pyarrow`

## Prerequisites

- Python 3.10+
- `uv` installed

## Setup

1. Create a virtual environment:
   `uv venv --python 3.11`
2. Install dependencies:
   `uv sync`

## Run

From the project directory:

```bash
uv run marimo edit notebook.py
```

This opens the notebook in a local marimo editor where you can interact with the sliders and see the data update in real time.

## Notes

- The model is synthetic and not a real market-data feed.
- The price process is a basic random walk:
  $\Delta P_t \sim \mathcal{N}(0, \sigma)$