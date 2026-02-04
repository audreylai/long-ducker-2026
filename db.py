import os
from datetime import datetime, timezone
from typing import List, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB", "lion-auction")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

lions_collection = db["lions"]
bids_collection = db["bids"]


def get_lions(limit: Optional[int] = None, sort_field: str = "name", direction: int = ASCENDING) -> List[dict]:
    cursor = lions_collection.find().sort(sort_field, direction)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def get_lions_by_bid(limit: int = 2) -> List[dict]:
    return get_lions(limit=limit, sort_field="current_bid", direction=DESCENDING)


def get_bids(limit: Optional[int] = None, sort_field: str = "timestamp", direction: int = DESCENDING) -> List[dict]:
    cursor = bids_collection.find().sort(sort_field, direction)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def get_lion_by_slug(slug: str) -> Optional[dict]:
    return lions_collection.find_one({"slug": slug})


def insert_bid(bid_data: dict) -> str:
    result = bids_collection.insert_one(bid_data)
    return str(result.inserted_id)


def update_lion_current_bid(slug: str, amount: int) -> None:
    lions_collection.update_one({"slug": slug}, {"$set": {"current_bid": amount}})


def load_temp_demo_data() -> None:
    """One-off helper to push sample documents into MongoDB when needed."""

    lions_payload = [
        {
            "slug": "aurora",
            "name": "Aurora",
            "house": "Gellhorn",
            "current_bid": 12800,
            "summary": "Hand-painted night sky gradients with fiber-optic accents for live sparkle.",
            "bidding_starts_at": datetime(2026, 2, 1, 9, 0, tzinfo=timezone.utc),
            "bidding_ends_at": datetime(2026, 2, 8, 21, 0, tzinfo=timezone.utc),
        },
        {
            "slug": "verve",
            "name": "Verve",
            "house": "Green",
            "current_bid": 9400,
            "summary": "Translucent armor plates melt reclaimed plastics into a flowing mane.",
            "bidding_starts_at": datetime(2026, 2, 2, 9, 0, tzinfo=timezone.utc),
            "bidding_ends_at": datetime(2026, 2, 9, 20, 0, tzinfo=timezone.utc),
        },
        {
            "slug": "legacy",
            "name": "Legacy",
            "house": "Red",
            "current_bid": 7600,
            "summary": "Panels illustrate milestone moments since the founding of the campus.",
            "bidding_starts_at": datetime(2026, 2, 3, 9, 0, tzinfo=timezone.utc),
            "bidding_ends_at": datetime(2026, 2, 10, 19, 0, tzinfo=timezone.utc),
        },
    ]

    bids_payload = [
        {
            "lion": "Aurora",
            "amount": 12800,
            "bidder": "Jamie Lee",
            "contact": {"email": "jamie.lee@example.com", "phone": "+852 5566 7788"},
            "timestamp": datetime(2026, 2, 3, 15, 45, tzinfo=timezone.utc),
            "status": "pending",
        },
        {
            "lion": "Verve",
            "amount": 9400,
            "bidder": "Priya Desai",
            "contact": {"email": "priya.desai@example.com", "phone": "+852 6677 8899"},
            "timestamp": datetime(2026, 2, 2, 11, 15, tzinfo=timezone.utc),
            "status": "confirmed",
        },
        {
            "lion": "Legacy",
            "amount": 7600,
            "bidder": "Alex Wong",
            "contact": {"email": "alex.wong@example.com", "phone": "+852 9988 7766"},
            "timestamp": datetime(2026, 2, 1, 9, 5, tzinfo=timezone.utc),
            "status": "pending",
        },
    ]

    lions_collection.delete_many({})
    if lions_payload:
        lions_collection.insert_many(lions_payload)

    bids_collection.delete_many({})
    if bids_payload:
        bids_collection.insert_many(bids_payload)

# load_temp_demo_data()