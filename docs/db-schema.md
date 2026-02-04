# Lion Auction MongoDB Schema

The application uses a single MongoDB database (default name `lion-auction`) with two primary collections. The schema is lightweight and document-oriented so it can evolve with additional auction metadata such as media URLs or live socket state.

## Collections

### `lions`
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `_id` | ObjectId | Yes | Auto-generated unique identifier. |
| `slug` | String | Yes | URL-safe identifier for routing and lookups (unique index recommended). |
| `name` | String | Yes | Display name of the sculpture. |
| `house` | String | Yes | Harrow house colour associated with the lion. |
| `summary` | String | Yes | Short marketing description shown on cards and detail pages. |
| `current_bid` | Number (int) | Yes | Latest confirmed bid in HKD; updated when bids settle. |
| `bidding_starts_at` | Date | No | Opening timestamp for online bidding (UTC). |
| `bidding_ends_at` | Date | No | Closing timestamp for online bidding (UTC). |
| `image_ids` | Array[ObjectId] | No | References to GridFS files uploaded through the admin console. The first ID becomes the public hero image. |
| `image_url` | String | No | Optional fallback/seed hero image URL used when no uploads exist. |
| `created_at` | Date | No | When the record was first created. |
| `updated_at` | Date | No | Last admin update timestamp. |

### `bids`
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `_id` | ObjectId | Yes | Auto-generated unique identifier. |
| `lion` | String | Yes | Slug or display name of the associated lion (lightweight reference). |
| `amount` | Number (int) | Yes | Bid amount in HKD. |
| `bidder` | String | Yes | Primary contact name. |
| `contact.email` | String | Yes | Email for confirmations. |
| `contact.phone` | String | No | SMS number for rapid approvals. |
| `timestamp` | Date | Yes | When the bid was captured. |
| `status` | String | Yes | `pending`, `confirmed`, or `declined`. |
| `notes` | String | No | Internal remarks from the auction desk. |

## Relationships
- `bids.lion` references `lions.slug` (or name). A formal foreign key is not required, but an index on `bids.lion` speeds up per-lion queries.
- Aggregate metrics (highest bid, totals) are computed dynamically in Flask so no extra rollup collection is needed.

## Seed Data
Use the helper below whenever you need placeholder content in development:

```bash
python -c "from db import load_temp_demo_data; load_temp_demo_data()"
```

The script now clears both collections and seeds six fully populated lions (`solstice-ember`, `prism-runner`, `harbor-pulse`, `atlas-bloom`, `midnight-voyager`, `lumina-trace`) with hero image URLs, bidding windows, and representative bids so the spotlight, catalogue, and detail pages all display real artwork thumbnails.
