import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for

from db import get_bids, get_lion_by_slug, get_lions, get_lions_by_bid, insert_bid, update_lion_current_bid
from forms import LionBidForm

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

HKT_TZ = timezone(timedelta(hours=8))


def ensure_utc_datetime(value: Optional[datetime]) -> Optional[datetime]:
    """Return a timezone-aware UTC datetime for comparisons."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def convert_to_hkt(value: Optional[datetime]) -> Optional[datetime]:
    utc_value = ensure_utc_datetime(value)
    if utc_value is None:
        return None
    return utc_value.astimezone(HKT_TZ)


def normalize_lion_time_fields(lion: Optional[dict]) -> Optional[dict]:
    if not lion:
        return lion

    starts_utc = ensure_utc_datetime(lion.get("bidding_starts_at"))
    ends_utc = ensure_utc_datetime(lion.get("bidding_ends_at"))

    lion["bidding_starts_at"] = starts_utc
    lion["bidding_ends_at"] = ends_utc
    lion["bidding_starts_at_hkt"] = convert_to_hkt(starts_utc)
    lion["bidding_ends_at_hkt"] = convert_to_hkt(ends_utc)
    return lion


def is_bidding_window_open(lion: dict, reference_time: Optional[datetime] = None) -> bool:
    """Return True when the current time falls within the lion's bidding window."""

    reference_time = reference_time or datetime.now(timezone.utc)
    starts_at = ensure_utc_datetime(lion.get("bidding_starts_at"))
    ends_at = ensure_utc_datetime(lion.get("bidding_ends_at"))

    if starts_at and reference_time < starts_at:
        return False
    if ends_at and reference_time > ends_at:
        return False
    return True


@app.route("/")
def home():
    highlight_lions = [normalize_lion_time_fields(lion) for lion in get_lions_by_bid()]
    bids = get_bids()
    total_raised = sum(bid.get("amount", 0) for bid in bids)
    top_bid = max(bids, key=lambda bid: bid.get("amount", 0)) if bids else None
    return render_template(
        "index.html",
        highlight_lions=highlight_lions,
        total_raised=total_raised,
        top_bid=top_bid,
        long_ducker_date="14 March 2026",
    )


@app.route("/lions")
def lions_catalog():
    raw_lions = get_lions()
    now = datetime.now(timezone.utc)
    lions = []
    for lion in raw_lions:
        normalized = normalize_lion_time_fields(lion)
        normalized["bidding_open"] = is_bidding_window_open(normalized, now)
        lions.append(normalized)
    return render_template("lions.html", lions=lions)


@app.route("/admin")
def admin_dashboard():
    lions = [normalize_lion_time_fields(lion) for lion in get_lions()]
    bids = get_bids()
    unique_bidders = {bid.get("bidder") for bid in bids if bid.get("bidder")}
    metrics = {
        "total_lions": len(lions),
        "total_bids": len(bids),
        "unique_bidders": len(unique_bidders),
        "highest_bid": max((bid.get("amount", 0) for bid in bids), default=0),
    }
    return render_template("admin_dashboard.html", lions=lions, bids=bids, metrics=metrics)


@app.route("/lions/<slug>", methods=["GET", "POST"])
def lion_detail(slug):
    lion = get_lion_by_slug(slug)
    if not lion:
        abort(404)

    lion = normalize_lion_time_fields(lion)
    now = datetime.now(timezone.utc)
    bidding_open = is_bidding_window_open(lion, now)
    lion["bidding_open"] = bidding_open

    form = LionBidForm()
    if not form.is_submitted():
        form.lion_slug.data = slug

    if form.validate_on_submit():
        amount_value = int(form.amount.data)
        current = int(lion.get("current_bid") or 0)

        if form.lion_slug.data != slug:
            form.lion_slug.errors.append("Invalid lion reference.")
        elif not bidding_open:
            form.amount.errors.append("Bidding is closed for this lion.")
        elif amount_value <= current:
            form.amount.errors.append("Bid must exceed the current amount.")
        else:
            bid_document = {
                "lion": lion.get("slug") or lion.get("name"),
                "amount": amount_value,
                "bidder": form.name.data,
                "contact": {"email": form.email.data, "phone": form.phone.data},
                "timestamp": datetime.now(timezone.utc),
                "status": "pending",
            }
            insert_bid(bid_document)
            update_lion_current_bid(slug, amount_value)
            flash("Bid submitted successfully. We'll be in touch soon!", "success")
            return redirect(url_for("lion_detail", slug=slug))

    related_bids = [
        bid for bid in get_bids() if bid.get("lion") in {lion.get("slug"), lion.get("name")}
    ]
    return render_template(
        "lion_detail.html",
        lion=lion,
        bids=related_bids,
        form=form,
        bidding_open=bidding_open,
        current_time=now,
    )

@app.context_processor
def inject_global_context():
    now = datetime.now(timezone.utc)
    return {"current_year": now.year, "current_time": now}


if __name__ == "__main__":
    app.run(debug=True)