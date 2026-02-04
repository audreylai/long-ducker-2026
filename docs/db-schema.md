# Lion Auction MongoDB Schema

The application uses a single MongoDB database (default name `lion-auction`) with two primary collections. The schema is lightweight and document-oriented so it can evolve with additional auction metadata such as media URLs or live socket state.

## Collections

### `lions`
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `_id` | ObjectId | Yes | Auto-generated unique identifier. |
| `slug` | String | Yes | URL-safe identifier for routing and lookups (unique index recommended). |
| `name` | String | Yes | Display name of the sculpture. |
| `house` | String | Yes | Harrow house color associated with the lion. |
| `artist` | String | Yes | Student group or collaborator who created the piece. |
| `summary` | String | Yes | Short marketing description shown on cards. |
| `current_bid` | Number (int) | Yes | Latest confirmed bid in HKD; updated when bids settle. |
| `media` | Array[String] | No | Optional list of CDN image/video URLs. |

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

This script clears both collections and inserts the three demo lions (`aurora`, `verve`, `legacy`) with matching bids.
