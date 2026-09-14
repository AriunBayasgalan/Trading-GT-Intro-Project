import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional
import httpx
from sortedcontainers import SortedDict
from picows import WSFrame, WSListener, WSMsgType, WSTransport, ws_connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


class WooXOrderBookListener(WSListener):
    """WebSocket listener maintaining a real-time Woo X L2 Order Book.

    Utilizes SortedDict for fast key lookups and continuous range slicing while
    verifying timestamp continuity against REST snapshots.
    """

    def __init__(self, symbol: str = "PERP_ETH_USDT"):
        self.symbol = symbol
        self.bids: SortedDict = SortedDict()
        self.asks: SortedDict = SortedDict()
        self.last_update: Optional[str] = None

        self._is_synced: bool = False
        self._buffer: List[dict] = []
        self._last_ts: int = 0
        self._http_client: Optional[httpx.AsyncClient] = None

    def on_ws_connected(self, transport: WSTransport):
        """Triggers subscription and initiates non-blocking snapshot fetch."""
        logging.info(f"Connected. Subscribing to {self.symbol}@orderbookupdate...")

        sub_msg = {
            "id": "sub_ob_fast",
            "event": "subscribe",
            "topic": f"{self.symbol}@orderbookupdate",
        }
        transport.send(WSMsgType.TEXT, json.dumps(sub_msg).encode("utf-8"))

        self._http_client = httpx.AsyncClient(timeout=5.0)
        asyncio.create_task(self._fetch_rest_snapshot())

    def on_ws_frame(self, transport: WSTransport, frame: WSFrame):
        """Processes WS control frames and market deltas."""
        payload = frame.get_payload_as_ascii_text()
        if not payload:
            return

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        if not isinstance(data, dict):
            return

        event = data.get("event")
        if event == "ping":
            transport.send(WSMsgType.TEXT, b'{"event":"pong"}')
            return
        if event == "subscribe":
            logging.info(f"Subscription confirmed: {data}")
            return

        if "data" in data and isinstance(data["data"], dict):
            self._handle_delta(data["data"])

    async def _fetch_rest_snapshot(self):
        """Fetches initial order book snapshot asynchronously via HTTPX."""
        url = f"https://api.woox.io/v1/public/orderbook/{self.symbol}?max_level=50"
        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
            snapshot_data = response.json()

            if snapshot_data.get("success"):
                self._apply_snapshot(snapshot_data)
            else:
                logging.error(f"REST Snapshot payload invalid: {snapshot_data}")
        except Exception as e:
            logging.error(f"HTTP error fetching REST snapshot: {e}")

    def _apply_snapshot(self, snapshot: dict):
        """Applies snapshot base levels and replays buffered deltas."""
        snapshot_ts = snapshot.get("timestamp", 0)

        self.bids.clear()
        self.asks.clear()

        for item in snapshot.get("bids", []):
            p, s = (float(item["price"]), float(item.get("quantity", 0))) if isinstance(item, dict) else (float(item[0]), float(item[1]))
            if s > 0:
                self.bids[p] = s

        for item in snapshot.get("asks", []):
            p, s = (float(item["price"]), float(item.get("quantity", 0))) if isinstance(item, dict) else (float(item[0]), float(item[1]))
            if s > 0:
                self.asks[p] = s

        self._last_ts = snapshot_ts

        # Sync buffered messages
        for delta in self._buffer:
            prev_ts = delta.get("prevTs", 0)
            ts = delta.get("ts", 0)

            if ts <= snapshot_ts:
                continue

            if prev_ts <= snapshot_ts <= ts or self._is_synced:
                self._apply_delta_data(delta)
                self._is_synced = True
                self._last_ts = ts

        self._buffer.clear()
        self._is_synced = True
        self.last_update = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._display_book()

    def _handle_delta(self, ob_data: dict):
        """Validates sequence continuity and applies market deltas."""
        if not self._is_synced:
            self._buffer.append(ob_data)
            return

        prev_ts = ob_data.get("prevTs", 0)
        ts = ob_data.get("ts", 0)

        if prev_ts != self._last_ts:
            logging.error(f"Sequence gap! Expected prevTs={self._last_ts}, got {prev_ts}. Resyncing...")
            self._is_synced = False
            self._buffer.append(ob_data)
            asyncio.create_task(self._fetch_rest_snapshot())
            return

        self._apply_delta_data(ob_data)
        self._last_ts = ts
        self.last_update = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._display_book()

    def _apply_delta_data(self, ob_data: dict):
        """Updates internal SortedDict instances with incremental updates."""
        for price, size in ob_data.get("bids", []):
            p, s = float(price), float(size)
            if s == 0:
                self.bids.pop(p, None)
            else:
                self.bids[p] = s

        for price, size in ob_data.get("asks", []):
            p, s = float(price), float(size)
            if s == 0:
                self.asks.pop(p, None)
            else:
                self.asks[p] = s

    def _display_book(self):
        """Renders the top 5 bid and ask levels to terminal."""
        # Top 5 bids (highest price first)
        bid_keys = self.bids.keys()[-5:][::-1]
        sorted_bids = [(k, self.bids[k]) for k in bid_keys]

        # Top 5 asks (lowest price first)
        ask_keys = self.asks.keys()[:5]
        sorted_asks = [(k, self.asks[k]) for k in ask_keys]

        lines = [
            "\033[2J\033[3J\033[H" + "=" * 56,
            f" Woo X Level 2 Book | {self.symbol} | Last: {self.last_update}",
            "=" * 56,
            f"{'ASKS':^26} | {'BIDS':^26}",
            f"{'Price':>11}  {'Size':>10}    | {'Price':>10}  {'Size':>10}",
            "-" * 56,
        ]

        max_rows = max(len(sorted_bids), len(sorted_asks))
        for i in range(max_rows):
            ask_str = f"{sorted_asks[i][0]:>11.2f}  {sorted_asks[i][1]:>10.4f}" if i < len(sorted_asks) else " " * 23
            bid_str = f"{sorted_bids[i][0]:>10.2f}  {sorted_bids[i][1]:>10.4f}" if i < len(sorted_bids) else " " * 23
            lines.append(f"{ask_str}    | {bid_str}")

        lines.append("=" * 56)
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()

    async def close(self):
        """Cleanup async resources."""
        if self._http_client:
            await self._http_client.aclose()


async def send_ping_loop(transport: WSTransport):
    """Sends WS client heartbeats."""
    try:
        while True:
            await asyncio.sleep(5)
            transport.send(WSMsgType.TEXT, b'{"event":"ping"}')
    except asyncio.CancelledError:
        pass


async def main():
    url = "wss://wss.woox.io/ws/stream"
    transport, listener = await ws_connect(WooXOrderBookListener, url)
    ping_task = asyncio.create_task(send_ping_loop(transport))

    try:
        await ping_task
    except asyncio.CancelledError:
        pass
    finally:
        ping_task.cancel()
        await listener.close()
        transport.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)