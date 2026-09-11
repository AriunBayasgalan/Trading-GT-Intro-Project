# Woo X L2 Order Book Ingester

A lightweight live WebSocket client that subscribes to the Woo X Level 2 order book for the `PERP_ETH_USDT` market and prints the top bids and asks in the terminal.

## What it does

- Connects to the Woo X WebSocket stream at `wss://wss.woox.io/ws/stream`
- Subscribes to the `PERP_ETH_USDT@orderbook` topic
- Maintains local bid/ask state from incoming book updates
- Clears and redraws a terminal table showing the best prices and sizes
- Sends periodic heartbeat pings to keep the connection alive

## Prerequisites

- Python 3.10+
- `uv` installed

## Setup

1. Create a virtual environment:
   `uv venv --python 3.11`
2. Install project dependencies:
   `uv sync`

## Run

From the project directory:

```bash
uv run ingest.py
```

The script will connect to Woo X and begin streaming order-book updates. It will keep running until you stop it with `Ctrl+C`.

## Notes

- The current symbol is hardcoded as `PERP_ETH_USDT` in the listener.