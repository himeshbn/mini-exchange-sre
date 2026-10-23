import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def place_order(client, side, price, quantity):
    return client.post(
        "/order",
        json={"side": side, "price": price, "quantity": quantity},
    )


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_non_crossing_orders_remain_open(client):
    buy = place_order(client, "buy", 99, 5)
    sell = place_order(client, "sell", 101, 3)

    assert buy.status_code == 201
    assert sell.status_code == 201
    assert buy.json()["status"] == "open"
    assert sell.json()["status"] == "open"

    book = client.get("/orderbook").json()
    assert len(book["bids"]) == 1
    assert len(book["asks"]) == 1


def test_crossing_orders_match(client):
    place_order(client, "sell", 100, 5)
    response = place_order(client, "buy", 105, 3)

    result = response.json()
    assert result["status"] == "filled"
    assert result["remaining"] == 0
    assert result["fills"][0]["price"] == 100
    assert result["fills"][0]["quantity"] == 3

    book = client.get("/orderbook").json()
    assert book["asks"][0]["remaining"] == 2
    assert book["bids"] == []


def test_partial_fill_and_remaining_quantity(client):
    place_order(client, "sell", 100, 2)
    response = place_order(client, "buy", 100, 5)

    result = response.json()
    assert result["status"] == "partially_filled"
    assert result["remaining"] == 3
    assert result["fills"][0]["quantity"] == 2

    book = client.get("/orderbook").json()
    assert book["bids"][0]["remaining"] == 3
    assert book["asks"] == []


def test_best_price_has_priority(client):
    place_order(client, "sell", 102, 1)
    place_order(client, "sell", 100, 1)

    response = place_order(client, "buy", 110, 1)
    result = response.json()

    assert result["fills"][0]["price"] == 100


def test_invalid_orders_are_rejected(client):
    response = client.post(
        "/order",
        json={"side": "buy", "price": -1, "quantity": 1},
    )
    assert response.status_code == 422

    response = client.post(
        "/order",
        json={"side": "hold", "price": 100, "quantity": 1},
    )
    assert response.status_code == 422


def test_equal_price_orders_keep_time_priority(client):
    first = place_order(client, "sell", 100, 1).json()
    second = place_order(client, "sell", 100, 1).json()

    result = place_order(client, "buy", 100, 1).json()

    assert result["fills"][0]["sell_order_id"] == first["order_id"]
    book = client.get("/orderbook").json()
    assert book["asks"][0]["order_id"] == second["order_id"]
