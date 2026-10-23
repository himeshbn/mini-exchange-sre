from collections import deque
from datetime import datetime, timezone
from itertools import count
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    side: Literal["buy", "sell"]
    price: float = Field(gt=0, allow_inf_nan=False)
    quantity: int = Field(gt=0)


class Exchange:
    """In-memory limit order book with price-time priority."""

    def __init__(self):
        self.bids = []
        self.asks = []
        self.trades = []
        self.order_ids = count(1)
        self.lock = Lock()

    def submit(self, request: OrderRequest):
        with self.lock:
            order = {
                "order_id": next(self.order_ids),
                "side": request.side,
                "price": request.price,
                "quantity": request.quantity,
                "remaining": request.quantity,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            fills = []

            # Match against the opposite side at the best available price.
            opposite = self.asks if order["side"] == "buy" else self.bids

            while order["remaining"] > 0 and opposite:
                best = opposite[0]

                crosses = (
                    order["price"] >= best["price"]
                    if order["side"] == "buy"
                    else order["price"] <= best["price"]
                )

                if not crosses:
                    break

                traded = min(order["remaining"], best["remaining"])

                # The resting order's price determines the execution price.
                trade = {
                    "buy_order_id": (
                        order["order_id"]
                        if order["side"] == "buy"
                        else best["order_id"]
                    ),
                    "sell_order_id": (
                        best["order_id"]
                        if order["side"] == "buy"
                        else order["order_id"]
                    ),
                    "price": best["price"],
                    "quantity": traded,
                }

                order["remaining"] -= traded
                best["remaining"] -= traded
                fills.append(trade)
                self.trades.append(trade)

                if best["remaining"] == 0:
                    opposite.pop(0)

            if order["remaining"] > 0:
                book = self.bids if order["side"] == "buy" else self.asks
                book.append(order)

                # Stable sorting preserves insertion order at equal prices.
                if order["side"] == "buy":
                    book.sort(key=lambda item: -item["price"])
                else:
                    book.sort(key=lambda item: item["price"])

            status = (
                "filled"
                if order["remaining"] == 0
                else "partially_filled"
                if fills
                else "open"
            )

            return {
                **order,
                "status": status,
                "fills": fills,
            }

    def orderbook(self):
        with self.lock:
            return {
                "bids": [dict(order) for order in self.bids],
                "asks": [dict(order) for order in self.asks],
                "recent_trades": [dict(trade) for trade in self.trades[-20:]],
            }


def create_app(exchange=None):
    api = FastAPI(title="Mini Exchange", version="0.1.0")
    engine = exchange or Exchange()

    @api.get("/health")
    def health():
        return {"status": "ok"}

    @api.post("/order", status_code=201)
    def submit_order(request: OrderRequest):
        try:
            return engine.submit(request)
        except Exception:
            # Do not expose internal exception details to API clients.
            raise HTTPException(
                status_code=500,
                detail="Internal order processing error",
            )

    @api.get("/orderbook")
    def get_orderbook():
        return engine.orderbook()

    return api


app = create_app()
