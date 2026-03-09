# Long Ducker Lion Auction — App Documentation

## Overview
This Flask app powers the Long Ducker Lion Auction experience with a public catalogue, bidding flow, and an admin console for managing lions and bids.

## Public Experience
### Pages
- Home: highlights top lions, totals, and key auction info.
- Lions catalogue: grid of all lions with bidding status.
- Lion detail: story, countdown, and bid form.

### Bidding Rules
- Bids are accepted only within the lion’s bidding window.
- A bid must exceed the current bid.
- Successful bids update `current_bid` and appear immediately in admin views.

## Admin System
### Access
- Admin login protects all `/admin` routes. Credentials are read from environment variables.

### Dashboard Tabs
- Manage lions: card view with image, status, and quick edit links.
- All bids: table view with filters (by lion and bidder search) and sorting by bid amount.

### Editing Lions
- Admins can create or edit lions, update current bid, and manage bidding windows.
- Bidding times are input in HKT and stored in UTC.

## Images
- Uploads are validated for JPG/PNG/GIF/WEBP.
- Client-side compression reduces upload size before submit.
- Server-side compression converts images to WebP and resizes to a maximum dimension.
- Image responses include long-lived cache headers.

## Environment Variables
- `SECRET_KEY`: Flask session secret.
- `MONGODB_URI`: MongoDB connection string.
- `MONGODB_DB`: Database name.
- `ADMIN_USERNAME`: Admin username.
- `ADMIN_PASSWORD`: Admin password.
- `MAX_LION_IMAGE_DIM`: Max image size (default 1600).
- `LION_IMAGE_QUALITY`: WebP quality (default 80).

## Development
- Python dependencies: `requirements.txt`
- Tailwind build: `npm run build:css` or `npm run watch:css`

## Data Seeding
- Use `load_temp_demo_data()` from `db.py` to seed demo lions and bids.
