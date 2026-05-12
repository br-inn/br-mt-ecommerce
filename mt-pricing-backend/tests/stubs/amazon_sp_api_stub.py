"""Stub del Amazon Selling Partner API para tests — US-1B-04-04."""

from __future__ import annotations


class AmazonSPAPIStub:
    """Simula el comportamiento del Amazon Selling Partner API para tests."""

    submitted: list[dict]

    def __init__(self) -> None:
        self.submitted = []

    def submit_price_feed(self, rows: list[dict]) -> str:
        """Retorna un feed_id simulado."""
        self.submitted.extend(rows)
        return f"FEED-{len(self.submitted):04d}"

    def get_feed_status(self, feed_id: str) -> dict:
        return {"feed_id": feed_id, "status": "DONE", "errors": 0}
