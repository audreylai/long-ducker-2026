# Lion Auction MongoDB Schema

The application uses a single MongoDB database (default name `lion-auction`) with two primary collections. The schema is lightweight and document-oriented so it can evolve with additional auction metadata such as media URLs or live socket state.

## Collections

### `lions`
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `_id` | ObjectId | Yes | Auto-generated unique identifier. |
| `name` | String | Yes | Display name of the sculpture. |
| `house` | String | Yes | Harrow house colour associated with the lion. |
| `summary` | String | Yes | Short marketing description shown on cards and detail pages. |
| `current_bid` | Number (int) | Yes | Latest confirmed bid in HKD; updated when bids are submitted. |
| `bidding_starts_at` | Date | No | Opening timestamp for online bidding (stored in UTC; admin UI uses HKT). |
| `bidding_ends_at` | Date | No | Closing timestamp for online bidding (stored in UTC; admin UI uses HKT). |
| `image_ids` | Array[ObjectId] | No | References to GridFS files uploaded through the admin console. The first ID becomes the public hero image. |
| `image_url` | String | No | Optional fallback/seed hero image URL used when no uploads exist. |
| `created_at` | Date | No | When the record was first created. |
| `updated_at` | Date | No | Last admin update timestamp. |

### `bids`
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `_id` | ObjectId | Yes | Auto-generated unique identifier. |
| `lion_id` | String | Yes | Stringified ObjectId of the lion; used for routing and grouping. |
| `lion_name` | String | Yes | Cached friendly name of the sculpture for denormalized reporting. |
| `lion` | String | No | Legacy text reference (older exports). New writes duplicate `lion_name` here for compatibility. |
| `amount` | Number (int) | Yes | Bid amount in HKD. |
| `bidder` | String | Yes | Primary contact name. |
| `contact.email` | String | Yes | Email for confirmations. |
| `contact.phone` | String | No | SMS number for rapid approvals. |
| `timestamp` | Date | Yes | When the bid was captured. |

## Relationships
- `bids.lion_id` references `lions._id`. Legacy `bids.lion` strings (formerly slugs) still resolve, but new code relies on the ObjectId string + cached name.
- Aggregate metrics (highest bid, totals) are computed dynamically in Flask so no extra rollup collection is needed.

## Image Storage (GridFS)
Uploads are stored in a GridFS bucket named `lion_images`. Images are compressed to WebP on upload and cached aggressively when served. The first `image_ids` entry is used as the primary image when available.

## Seed Data
Use the helper below whenever you need placeholder content in development:

```bash
python -c "from db import load_temp_demo_data; load_temp_demo_data()"
```

The script now clears both collections and seeds six fully populated lions (Solstice Ember, Prism Runner, Harbor Pulse, Atlas Bloom, Midnight Voyager, Lumina Trace) with hero image URLs, bidding windows, and representative bids so the spotlight, catalogue, and detail pages all display real artwork thumbnails.
