import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List
from picows import WSFrame, WSListener, WSMsgType, WSTransport, ws_connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


class WooXOrderBookListener(WSListener):
    def __init__(self, symbol: str = "PERP_ETH_USDT"):
        self.symbol = symbol
        self.bids: Dict[float, float] = {}
        self.asks: Dict[float, float] = {}
        self.last_update = None

    def on_ws_connected(self, transport: WSTransport):
        #Called automatically when WebSocket connects

        logging.info("Connected to Woo X. Subscribing to orderbook...")

        sub_msg = {
            "id": "sub_ob",
            "event": "subscribe",
            "topic": f"{self.symbol}@orderbook",
        }
        transport.send(WSMsgType.TEXT, json.dumps(sub_msg).encode("utf-8"))

    def on_ws_frame(self, transport: WSTransport, frame: WSFrame):
        #Processes incoming data frames from Woo X

        payload = frame.get_payload_as_ascii_text()
        if not payload:
            return

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        if not isinstance(data, dict):
            return

        # Server Heartbeat Ping
        if data.get("event") == "ping":
            transport.send(
                WSMsgType.TEXT, json.dumps({"event": "pong"}).encode("utf-8")
            )
            return

        # Subscription Confirmation
        if data.get("event") == "subscribe":
            logging.info(f"Subscription confirmation: {data}")
            return

        # Process Market Order Book Data
        if "data" in data and isinstance(data["data"], dict):
            ob_data = data["data"]
            self._update_book(ob_data.get("bids", []), ob_data.get("asks", []))
            self.last_update = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._display_book()

    def _update_book(self, bids: List[List[float]], asks: List[List[float]]):
        for price, size in bids:
            price, size = float(price), float(size)
            if size == 0:
                self.bids.pop(price, None)
            else:
                self.bids[price] = size

        for price, size in asks:
            price, size = float(price), float(size)
            if size == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = size

    def _display_book(self):
        sorted_bids = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)[:5]
        sorted_asks = sorted(self.asks.items(), key=lambda x: x[0])[:5]

        lines = [
            "\033[2J\033[3J\033[H" + "=" * 56,
            f" Woo X Level 2 Book | {self.symbol} | Last: {self.last_update}",
            "=" * 56,
            f"{'ASKS':^26} | {'BIDS':^26}",
            f"{'Price':>11}  {'Size':>10}    | {'Price':>10}  {'Size':>10}",
            "-" * 56
        ]

        max_rows = max(len(sorted_bids), len(sorted_asks))
        for i in range(max_rows):
            ask_str = f"{sorted_asks[i][0]:>11.2f}  {sorted_asks[i][1]:>10.4f}" if i < len(sorted_asks) else " " * 23
            bid_str = f"{sorted_bids[i][0]:>10.2f}  {sorted_bids[i][1]:>10.4f}" if i < len(sorted_bids) else " " * 23
            lines.append(f"{ask_str}    | {bid_str}")
        
        lines.append("=" * 56)

        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()


async def send_ping_loop(transport: WSTransport):
    #Sends client-side heartbeat pings every 5 seconds to keep WS active

    try:
        while True:
            await asyncio.sleep(5)
            transport.send(
                WSMsgType.TEXT, json.dumps({"event": "ping"}).encode("utf-8")
            )
    except asyncio.CancelledError:
        # Expected exit signal when task is canceled
        pass
    except Exception as e:
        logging.error(f"Error in ping loop: {e}")


async def main():
    url = "wss://wss.woox.io/ws/stream"
    logging.info(f"Connecting to {url}...")

    transport, listener = await ws_connect(WooXOrderBookListener, url)

    ping_task = asyncio.create_task(send_ping_loop(transport))

    try:
        await ping_task
    except asyncio.CancelledError:
        pass
    finally:
        ping_task.cancel()
        transport.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down ingester gracefully...")
        sys.exit(0)