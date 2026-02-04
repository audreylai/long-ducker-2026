import csv
import io
import os
import re
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import List, Optional
from uuid import uuid4

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from db import (
    add_lion_images,
    delete_lion_image,
    get_bids,
    get_lion_by_id,
    get_lion_image_file,
    get_lion_images,
    get_lion_by_slug,
    get_lions,
    get_lions_by_bid,
    insert_bid,
    insert_lion,
    update_lion,
    update_lion_current_bid,
)
from forms import AdminLionForm, AdminLoginForm, LionBidForm

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

HKT_TZ = timezone(timedelta(hours=8))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "harrow-lion-2026")
ALLOWED_LION_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}


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
    reference_time = reference_time or datetime.now(timezone.utc)
    starts_at = ensure_utc_datetime(lion.get("bidding_starts_at"))
    ends_at = ensure_utc_datetime(lion.get("bidding_ends_at"))

    if starts_at and reference_time < starts_at:
        return False
    if ends_at and reference_time > ends_at:
        return False
    return True


def admin_is_authenticated() -> bool:
    return bool(session.get("admin_logged_in"))


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not admin_is_authenticated():
            flash("Please log in to access the admin console.", "warning")
            return redirect(url_for("admin_login"))
        return view_func(*args, **kwargs)

    return wrapper


def serialize_lion_record(record: Optional[dict]) -> Optional[dict]:
    if not record:
        return None
    payload = dict(record)
    payload["id"] = str(record.get("_id"))
    image_ids = payload.get("image_ids") or []
    payload["image_ids"] = [str(image_id) for image_id in image_ids]
    payload["image_count"] = len(image_ids)
    return payload


def attach_primary_image_url(lion: Optional[dict]) -> Optional[dict]:
    if not lion:
        return lion

    lion_identifier = lion.get("_id") or lion.get("id")
    image_ids = lion.get("image_ids") or []

    if lion.get("image_url") and not image_ids:
        return lion

    if not lion_identifier or not image_ids:
        return lion

    first_image_id = image_ids[0]
    if isinstance(first_image_id, dict):
        first_image_id = first_image_id.get("id") or first_image_id.get("_id")
    if first_image_id is None:
        return lion

    lion["image_url"] = url_for(
        "lion_image",
        lion_id=str(lion_identifier),
        image_id=str(first_image_id),
    )
    return lion


def slugify_name(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return base or f"lion-{uuid4().hex[:6]}"


def ensure_unique_lion_slug(base_slug: str, current_id: Optional[str] = None) -> str:
    base_slug = base_slug or f"lion-{uuid4().hex[:6]}"
    slug = base_slug
    counter = 1
    while True:
        existing = get_lion_by_slug(slug)
        if not existing:
            return slug
        if current_id and str(existing.get("_id")) == str(current_id):
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


def lion_payload_from_form(form: AdminLionForm, current_lion_id: Optional[str] = None) -> dict:
    payload = {
        "name": (form.name.data or "").strip(),
        "house": (form.house.data or "").strip() or None,
        "summary": (form.summary.data or "").strip(),
    }
    if form.current_bid.data is not None:
        payload["current_bid"] = int(form.current_bid.data)
    else:
        payload["current_bid"] = 0
    if form.bidding_starts_at.data:
        payload["bidding_starts_at"] = form.bidding_starts_at.data.replace(tzinfo=timezone.utc)
    else:
        payload["bidding_starts_at"] = None
    if form.bidding_ends_at.data:
        payload["bidding_ends_at"] = form.bidding_ends_at.data.replace(tzinfo=timezone.utc)
    else:
        payload["bidding_ends_at"] = None
    base_slug = slugify_name(payload["name"])
    payload["slug"] = ensure_unique_lion_slug(base_slug, current_id=current_lion_id)
    return payload


def is_allowed_lion_image(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_LION_IMAGE_EXTENSIONS


def extract_lion_uploads(form: AdminLionForm) -> List[dict]:
    uploads: List[dict] = []
    files = form.images.data or []
    if not isinstance(files, list):
        files = [files]

    for storage in files:
        if not storage or not getattr(storage, "filename", ""):
            continue
        filename = secure_filename(storage.filename)
        if not is_allowed_lion_image(filename):
            form.images.errors.append("Only JPG, PNG, GIF, or WEBP files are supported.")
            continue
        content = storage.read()
        if not content:
            continue
        uploads.append(
            {
                "filename": filename,
                "content": content,
                "content_type": storage.mimetype,
            }
        )

    if form.images.errors:
        uploads.clear()
    return uploads


@app.route("/")
def home():
    highlight_lions = []
    for lion in get_lions_by_bid():
        normalized = normalize_lion_time_fields(lion)
        attach_primary_image_url(normalized)
        highlight_lions.append(normalized)
    slug_to_name = {
        lion.get("slug"): lion.get("name")
        for lion in get_lions()
        if lion.get("slug") and lion.get("name")
    }
    bids = get_bids()
    total_raised = sum(bid.get("amount", 0) for bid in bids)
    top_bid = max(bids, key=lambda bid: bid.get("amount", 0)) if bids else None
    top_bid_lion_name = None
    if top_bid:
        lion_ref = top_bid.get("lion")
        top_bid_lion_name = slug_to_name.get(lion_ref) or lion_ref
    return render_template(
        "index.html",
        highlight_lions=highlight_lions,
        total_raised=total_raised,
        top_bid=top_bid,
        top_bid_lion_name=top_bid_lion_name,
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
        attach_primary_image_url(normalized)
        lions.append(normalized)
    return render_template("lions.html", lions=lions)


@app.route("/admin")
@admin_required
def admin_dashboard():
    lions = [normalize_lion_time_fields(lion) for lion in get_lions()]
    now = datetime.now(timezone.utc)
    admin_lions = []
    lion_lookup = {}
    for lion in lions:
        serialized = serialize_lion_record(lion)
        serialized["bidding_open"] = is_bidding_window_open(serialized, now)
        attach_primary_image_url(serialized)
        admin_lions.append(serialized)
        if serialized.get("slug"):
            lion_lookup[serialized["slug"]] = serialized
        if serialized.get("name"):
            lion_lookup[serialized["name"]] = serialized

    bids = get_bids()
    enriched_bids = []
    bids_by_lion = {}
    for bid in bids:
        lion_ref = bid.get("lion")
        lion_match = lion_lookup.get(lion_ref) if lion_ref else None
        bid["lion_name"] = lion_match.get("name") if lion_match else lion_ref
        bid["lion_slug"] = lion_match.get("slug") if lion_match else None
        bid["lion_id"] = lion_match.get("id") if lion_match else None
        enriched_bids.append(bid)

        group_key = bid.get("lion_id") or bid.get("lion_slug") or lion_ref or "unknown"
        if group_key not in bids_by_lion:
            bids_by_lion[group_key] = {
                "lion": lion_match,
                "lion_name": bid.get("lion_name") or "Unknown lion",
                "lion_slug": bid.get("lion_slug"),
                "lion_id": bid.get("lion_id"),
                "bids": [],
            }
        bids_by_lion[group_key]["bids"].append(bid)

    lion_bid_summaries = []
    for summary in bids_by_lion.values():
        summary_bids = summary.get("bids", [])
        highest_bid = max(summary_bids, key=lambda b: b.get("amount", 0), default=None)
        summary["highest_bid"] = highest_bid
        summary["total_bids"] = len(summary_bids)
        lion_bid_summaries.append(summary)

    lion_bid_summaries.sort(key=lambda item: item.get("lion_name") or "")
    unique_bidders = {bid.get("bidder") for bid in bids if bid.get("bidder")}
    metrics = {
        "total_lions": len(lions),
        "total_bids": len(bids),
        "unique_bidders": len(unique_bidders),
        "highest_bid": max((bid.get("amount", 0) for bid in bids), default=0),
    }
    return render_template(
        "admin_dashboard.html",
        lions=admin_lions,
        bids=enriched_bids,
        bid_summaries=lion_bid_summaries,
        metrics=metrics,
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if admin_is_authenticated():
        return redirect(url_for("admin_dashboard"))

    form = AdminLoginForm()

    if form.validate_on_submit():
        username = (form.username.data or "").strip()
        password = form.password.data or ""
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            session["admin_username"] = username
            flash("Signed in successfully.", "success")
            return redirect(url_for("admin_dashboard"))
        form.password.errors.append("Invalid username or password.")

    return render_template("admin_login.html", form=form)


@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_username", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("home"))


@app.route("/admin/lions/new", methods=["GET", "POST"])
@admin_required
def admin_create_lion():
    form = AdminLionForm()
    if form.validate_on_submit():
        uploads = extract_lion_uploads(form)
        if form.images.errors:
            return render_template("admin_lion_form.html", form=form, lion=None, mode="create")
        lion_document = lion_payload_from_form(form)
        timestamp = datetime.now(timezone.utc)
        lion_document["created_at"] = timestamp
        lion_document["updated_at"] = timestamp
        lion_document["image_ids"] = []
        lion_id = insert_lion(lion_document)
        if uploads:
            add_lion_images(lion_id, uploads)
        flash("Lion added to the catalogue.", "success")
        return redirect(url_for("admin_lion_detail", lion_id=lion_id))
    return render_template("admin_lion_form.html", form=form, lion=None, mode="create")


@app.route("/admin/lions/<lion_id>")
@admin_required
def admin_lion_detail(lion_id):
    lion = get_lion_by_id(lion_id)
    if not lion:
        abort(404)
    slug = lion.get("slug")
    if not slug:
        flash("This lion is missing a public slug. Edit and save it to regenerate one.", "warning")
        return redirect(url_for("admin_edit_lion", lion_id=lion_id))
    return redirect(url_for("lion_detail", slug=slug))


@app.route("/admin/lions/<lion_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_lion(lion_id):
    source_lion = normalize_lion_time_fields(get_lion_by_id(lion_id))
    lion = serialize_lion_record(source_lion)
    if not lion:
        abort(404)
    lion["images"] = get_lion_images(lion_id)

    form = AdminLionForm()
    if not form.is_submitted():
        form.name.data = lion.get("name")
        form.house.data = lion.get("house")
        form.summary.data = lion.get("summary")
        form.current_bid.data = lion.get("current_bid")
        starts = lion.get("bidding_starts_at")
        ends = lion.get("bidding_ends_at")
        if starts:
            form.bidding_starts_at.data = starts.astimezone(timezone.utc).replace(tzinfo=None)
        if ends:
            form.bidding_ends_at.data = ends.astimezone(timezone.utc).replace(tzinfo=None)

    if form.validate_on_submit():
        uploads = extract_lion_uploads(form)
        if form.images.errors:
            return render_template("admin_lion_form.html", form=form, lion=lion, mode="edit")
        lion_document = lion_payload_from_form(form)
        lion_document["updated_at"] = datetime.now(timezone.utc)
        updated = update_lion(lion_id, lion_document)
        if uploads:
            add_lion_images(lion_id, uploads)
        if updated or uploads:
            flash("Lion updated successfully.", "success")
        else:
            flash("No changes were applied.", "info")
        return redirect(url_for("admin_lion_detail", lion_id=lion_id))

    return render_template("admin_lion_form.html", form=form, lion=lion, mode="edit")



def stream_lion_image(lion_id: str, image_id: str):
    file_obj = get_lion_image_file(lion_id, image_id)
    if not file_obj:
        abort(404)
    return send_file(
        io.BytesIO(file_obj.read()),
        mimetype=getattr(file_obj, "content_type", "application/octet-stream"),
        download_name=file_obj.filename or f"lion-{image_id}",
    )


@app.route("/lions/<lion_id>/images/<image_id>")
def lion_image(lion_id, image_id):
    return stream_lion_image(lion_id, image_id)


@app.route("/admin/lions/<lion_id>/images/<image_id>")
@admin_required
def admin_lion_image(lion_id, image_id):
    return stream_lion_image(lion_id, image_id)


@app.route("/admin/lions/<lion_id>/images/<image_id>/delete", methods=["POST"])
@admin_required
def admin_delete_lion_image(lion_id, image_id):
    if delete_lion_image(lion_id, image_id):
        flash("Image removed from this lion.", "info")
    else:
        flash("Unable to remove the selected image.", "warning")
    return redirect(url_for("admin_edit_lion", lion_id=lion_id))


@app.route("/admin/export/bids.csv")
@admin_required
def admin_export_bids_csv():
    bids = get_bids()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Lion",
        "Amount",
        "Bidder",
        "Email",
        "Phone",
        "Timestamp (UTC)",
    ])
    for bid in bids:
        contact = bid.get("contact") or {}
        timestamp = ensure_utc_datetime(bid.get("timestamp"))
        timestamp_str = timestamp.isoformat() if timestamp else ""
        writer.writerow(
            [
                bid.get("lion", ""),
                bid.get("amount", ""),
                bid.get("bidder", ""),
                contact.get("email", ""),
                contact.get("phone", ""),
                timestamp_str,
            ]
        )

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=bids.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


@app.route("/lions/<slug>", methods=["GET", "POST"])
def lion_detail(slug):
    lion = get_lion_by_slug(slug)
    if not lion:
        abort(404)

    lion = normalize_lion_time_fields(lion)
    lion = serialize_lion_record(lion)
    attach_primary_image_url(lion)
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
    return {
        "current_year": now.year,
        "current_time": now,
        "admin_logged_in": admin_is_authenticated(),
    }