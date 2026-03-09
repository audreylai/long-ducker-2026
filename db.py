import os
from datetime import datetime, timezone
from typing import List, Optional

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from bson import ObjectId
from gridfs import GridFS

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB", "lion-auction")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

lions_collection = db["lions"]
bids_collection = db["bids"]
lion_images_fs = GridFS(db, collection="lion_images")


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


def insert_bid(bid_data: dict) -> str:
    result = bids_collection.insert_one(bid_data)
    return str(result.inserted_id)


def update_lion_current_bid(lion_id: str, amount: int) -> None:
    try:
        lion_oid = ObjectId(lion_id)
    except Exception:
        return
    lions_collection.update_one({"_id": lion_oid}, {"$set": {"current_bid": amount}})


def load_temp_demo_data() -> None:

    lions_payload = [
        {
            "name": "Solstice Ember",
            "house": "Gellhorn",
            "current_bid": 15200,
            "summary": "Iridescent glass tessellation tracks the sun from dawn to dusk across its mane.",
            "image_url": "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1400&q=80",
            "image_ids": [],
            "bidding_starts_at": datetime(2026, 2, 10, 9, 0, tzinfo=timezone.utc),
            "bidding_ends_at": datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc),
            "created_at": datetime(2026, 1, 15, 6, 30, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 25, 6, 30, tzinfo=timezone.utc),
        },
        {
            "name": "Prism Runner",
            "house": "Green",
            "current_bid": 13400,
            "summary": "Layered acrylic fins bend the light spectrum as you circle the sculpture.",
            "image_url": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1400&q=80",
            "image_ids": [],
            "bidding_starts_at": datetime(2026, 2, 11, 9, 0, tzinfo=timezone.utc),
            "bidding_ends_at": datetime(2026, 3, 3, 17, 0, tzinfo=timezone.utc),
            "created_at": datetime(2026, 1, 16, 6, 30, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 26, 6, 30, tzinfo=timezone.utc),
        },
        {
            "name": "Harbor Pulse",
            "house": "Red",
            "current_bid": 11900,
            "summary": "Reclaimed sailcloth wraps the torso with hand-stitched skyline light trails.",
            "image_url": "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=1400&q=80",
            "image_ids": [],
            "bidding_starts_at": datetime(2026, 2, 12, 9, 0, tzinfo=timezone.utc),
            "bidding_ends_at": datetime(2026, 3, 4, 19, 0, tzinfo=timezone.utc),
            "created_at": datetime(2026, 1, 17, 6, 30, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 27, 6, 30, tzinfo=timezone.utc),
        },
        {
            "name": "Atlas Bloom",
            "house": "Blue",
            "current_bid": 9800,
            "summary": "Pressed botanicals chart the migration of pollinators across Asia.",
            "image_url": "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=1400&q=80",
            "image_ids": [],
            "bidding_starts_at": datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc),
            "bidding_ends_at": datetime(2026, 3, 5, 21, 0, tzinfo=timezone.utc),
            "created_at": datetime(2026, 1, 18, 6, 30, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 28, 6, 30, tzinfo=timezone.utc),
        },
        {
            "name": "Midnight Voyager",
            "house": "Gellhorn",
            "current_bid": 8700,
            "summary": "Matte indigo gradients hide constellations that glow under UV lighting.",
            "image_url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1400&q=80",
            "image_ids": [],
            "bidding_starts_at": datetime(2026, 2, 14, 9, 0, tzinfo=timezone.utc),
            "bidding_ends_at": datetime(2026, 3, 6, 23, 0, tzinfo=timezone.utc),
            "created_at": datetime(2026, 1, 19, 6, 30, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 29, 6, 30, tzinfo=timezone.utc),
        },
        {
            "name": "Lumina Trace",
            "house": "Green",
            "current_bid": 7600,
            "summary": "Programmable e-ink tiles animate choreographed patterns down the spine.",
            "image_url": "https://images.unsplash.com/photo-1451471016731-e963a8588be8?auto=format&fit=crop&w=1400&q=80",
            "image_ids": [],
            "bidding_starts_at": datetime(2026, 2, 15, 9, 0, tzinfo=timezone.utc),
            "bidding_ends_at": datetime(2026, 3, 7, 23, 0, tzinfo=timezone.utc),
            "created_at": datetime(2026, 1, 20, 6, 30, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 30, 6, 30, tzinfo=timezone.utc),
        },
    ]

    bids_payload = [
        {
            "lion": "Solstice Ember",
            "lion_name": "Solstice Ember",
            "amount": 15200,
            "bidder": "Jamie Lee",
            "contact": {"email": "jamie.lee@example.com", "phone": "+852 5566 7788"},
            "timestamp": datetime(2026, 2, 16, 15, 45, tzinfo=timezone.utc),
        },
        {
            "lion": "Prism Runner",
            "lion_name": "Prism Runner",
            "amount": 13400,
            "bidder": "Priya Desai",
            "contact": {"email": "priya.desai@example.com", "phone": "+852 6677 8899"},
            "timestamp": datetime(2026, 2, 15, 11, 15, tzinfo=timezone.utc),
        },
        {
            "lion": "Harbor Pulse",
            "lion_name": "Harbor Pulse",
            "amount": 11900,
            "bidder": "Alex Wong",
            "contact": {"email": "alex.wong@example.com", "phone": "+852 9988 7766"},
            "timestamp": datetime(2026, 2, 14, 9, 5, tzinfo=timezone.utc),
        },
        {
            "lion": "Atlas Bloom",
            "lion_name": "Atlas Bloom",
            "amount": 9800,
            "bidder": "Noah Reyes",
            "contact": {"email": "noah.reyes@example.com", "phone": "+852 4455 9911"},
            "timestamp": datetime(2026, 2, 13, 10, 20, tzinfo=timezone.utc),
        },
        {
            "lion": "Midnight Voyager",
            "lion_name": "Midnight Voyager",
            "amount": 8700,
            "bidder": "Maya Patel",
            "contact": {"email": "maya.patel@example.com", "phone": "+852 7788 2211"},
            "timestamp": datetime(2026, 2, 12, 13, 55, tzinfo=timezone.utc),
        },
        {
            "lion": "Lumina Trace",
            "lion_name": "Lumina Trace",
            "amount": 7600,
            "bidder": "Ethan Clarke",
            "contact": {"email": "ethan.clarke@example.com", "phone": "+852 8844 6622"},
            "timestamp": datetime(2026, 2, 11, 14, 5, tzinfo=timezone.utc),
        },
        {
            "lion": "Solstice Ember",
            "lion_name": "Solstice Ember",
            "amount": 14600,
            "bidder": "Morgan Tse",
            "contact": {"email": "morgan.tse@example.com", "phone": "+852 3322 1144"},
            "timestamp": datetime(2026, 2, 15, 16, 40, tzinfo=timezone.utc),
        },
    ]

    lions_collection.delete_many({})
    lion_name_to_id: dict[str, str] = {}
    if lions_payload:
        result = lions_collection.insert_many(lions_payload)
        for payload, inserted_id in zip(lions_payload, result.inserted_ids):
            lion_name_to_id[payload.get("name")] = str(inserted_id)

    bids_collection.delete_many({})
    if bids_payload:
        for bid in bids_payload:
            lion_name = bid.get("lion_name") or bid.get("lion")
            if lion_name:
                bid["lion"] = lion_name
                if lion_name in lion_name_to_id:
                    bid["lion_id"] = lion_name_to_id[lion_name]
                    bid["lion_name"] = lion_name
        bids_collection.insert_many(bids_payload)


def get_lion_by_id(lion_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(lion_id)
    except Exception:
        return None
    return lions_collection.find_one({"_id": oid})


def insert_lion(lion_data: dict) -> str:
    result = lions_collection.insert_one(lion_data)
    return str(result.inserted_id)


def update_lion(lion_id: str, lion_data: dict) -> bool:
    try:
        oid = ObjectId(lion_id)
    except Exception:
        return False
    update_result = lions_collection.update_one({"_id": oid}, {"$set": lion_data})
    return update_result.modified_count > 0


def add_lion_images(lion_id: str, files: List[dict]) -> List[str]:
    try:
        lion_oid = ObjectId(lion_id)
    except Exception:
        return []

    stored_ids: List[str] = []
    for file_payload in files:
        content = file_payload.get("content")
        if not content:
            continue
        file_id = lion_images_fs.put(
            content,
            filename=file_payload.get("filename"),
            lion_id=lion_oid,
            content_type=file_payload.get("content_type"),
            uploaded_at=datetime.now(timezone.utc),
        )
        stored_ids.append(str(file_id))
        lions_collection.update_one({"_id": lion_oid}, {"$addToSet": {"image_ids": file_id}})
    return stored_ids


def get_lion_images(lion_id: str) -> List[dict]:
    try:
        lion_oid = ObjectId(lion_id)
    except Exception:
        return []

    images = []
    for file_obj in lion_images_fs.find({"lion_id": lion_oid}).sort("uploadDate", ASCENDING):
        images.append(
            {
                "id": str(file_obj._id),
                "filename": file_obj.filename,
                "content_type": getattr(file_obj, "content_type", None),
                "length": getattr(file_obj, "length", 0),
                "uploaded_at": getattr(file_obj, "uploaded_at", getattr(file_obj, "upload_date", None)),
            }
        )
    return images


def get_lion_image_file(lion_id: str, image_id: str):
    try:
        lion_oid = ObjectId(lion_id)
        image_oid = ObjectId(image_id)
    except Exception:
        return None

    try:
        file_obj = lion_images_fs.get(image_oid)
    except Exception:
        return None

    if getattr(file_obj, "lion_id", None) != lion_oid:
        return None
    return file_obj


def delete_lion_image(lion_id: str, image_id: str) -> bool:
    file_obj = get_lion_image_file(lion_id, image_id)
    if not file_obj:
        return False

    lion_oid = ObjectId(lion_id)
    lion_images_fs.delete(file_obj._id)
    lions_collection.update_one({"_id": lion_oid}, {"$pull": {"image_ids": file_obj._id}})
    return True


def delete_bid(bid_id: str) -> bool:
    try:
        bid_oid = ObjectId(bid_id)
    except Exception:
        return False
    result = bids_collection.delete_one({"_id": bid_oid})
    return result.deleted_count > 0


def clear_database() -> dict:
    """Delete all lions, bids, and associated images. Returns counts of deleted documents."""
    # Remove all GridFS image files
    deleted_images = 0
    for grid_out in lion_images_fs.find():
        lion_images_fs.delete(grid_out._id)
        deleted_images += 1

    deleted_lions = lions_collection.delete_many({}).deleted_count
    deleted_bids = bids_collection.delete_many({}).deleted_count
    return {"lions": deleted_lions, "bids": deleted_bids, "images": deleted_images}