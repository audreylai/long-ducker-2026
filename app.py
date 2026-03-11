import base64
import csv
import io
import os
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import List, Optional

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
from PIL import Image
import qrcode
from qrcode.constants import ERROR_CORRECT_Q
from weasyprint import HTML
from werkzeug.utils import secure_filename
from flask_wtf.csrf import generate_csrf

from db import (
    add_lion_images,
    clear_database,
    delete_bid,
    delete_lion,
    delete_lion_image,
    get_bid_by_id,
    get_bids,
    get_lion_by_id,
    get_lion_image_file,
    get_lion_images,
    get_lions,
    get_lions_by_bid,
    get_max_bid_for_lion,
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
TRAIL_RESET_PIN = os.environ.get("TRAIL_RESET_PIN", "harrow2026")
ALLOWED_LION_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_LION_IMAGE_DIM = int(os.environ.get("MAX_LION_IMAGE_DIM", "1600"))
LION_IMAGE_QUALITY = int(os.environ.get("LION_IMAGE_QUALITY", "80"))


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


def lion_payload_from_form(form: AdminLionForm, existing_lion: Optional[dict] = None) -> dict:
    payload = {
        "name": (form.name.data or "").strip(),
        "summary": (form.summary.data or "").strip(),
    }
    if form.current_bid.data is not None:
        payload["current_bid"] = int(form.current_bid.data)
    else:
        payload["current_bid"] = 0
    if form.bidding_starts_at.data:
        local_start = form.bidding_starts_at.data.replace(tzinfo=HKT_TZ)
        payload["bidding_starts_at"] = local_start.astimezone(timezone.utc)
    elif existing_lion:
        payload["bidding_starts_at"] = ensure_utc_datetime(existing_lion.get("bidding_starts_at")) or datetime.now(timezone.utc)
    else:
        payload["bidding_starts_at"] = datetime.now(timezone.utc)
    if form.bidding_ends_at.data:
        local_end = form.bidding_ends_at.data.replace(tzinfo=HKT_TZ)
        payload["bidding_ends_at"] = local_end.astimezone(timezone.utc)
    else:
        payload["bidding_ends_at"] = None
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
        compressed_content, content_type, extension = compress_lion_image(content)
        base_name = os.path.splitext(filename)[0] or "lion-image"
        compressed_filename = f"{base_name}.{extension}"
        uploads.append(
            {
                "filename": compressed_filename,
                "content": compressed_content,
                "content_type": content_type,
            }
        )

    if form.images.errors:
        uploads.clear()
    return uploads


def compress_lion_image(content: bytes) -> tuple[bytes, str, str]:
    """Compress uploaded images and return (content, content_type, extension)."""
    with Image.open(io.BytesIO(content)) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_LION_IMAGE_DIM, MAX_LION_IMAGE_DIM))
        buffer = io.BytesIO()
        img.save(buffer, format="WEBP", quality=LION_IMAGE_QUALITY, optimize=True, method=6)
    return buffer.getvalue(), "image/webp", "webp"


def generate_lion_qr_png(lion_id: str) -> bytes:

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_Q,
        box_size=10,
        border=2,
    )
    lion_url = url_for("lion_detail", lion_id=lion_id, _external=True)
    qr.add_data(f"{lion_url}#lion={lion_id}")
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0F172A", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@app.route("/")
def home():
    highlight_lions = []
    for lion in get_lions():
        normalized = normalize_lion_time_fields(lion)
        attach_primary_image_url(normalized)
        highlight_lions.append(normalized)
    lion_name_lookup = {}
    for lion in get_lions():
        lion_id = lion.get("_id")
        lion_name = lion.get("name")
        if lion_id and lion_name:
            lion_name_lookup[str(lion_id)] = lion_name
        if lion_name:
            lion_name_lookup[lion_name] = lion_name
        if lion.get("slug") and lion_name:
            lion_name_lookup[lion.get("slug")] = lion_name
    bids = get_bids()
    total_raised = sum(bid.get("amount", 0) for bid in bids)
    top_bid = max(bids, key=lambda bid: bid.get("amount", 0)) if bids else None
    top_bid_lion_name = None
    if top_bid:
        lion_ref = top_bid.get("lion_id") or top_bid.get("lion_name") or top_bid.get("lion")
        top_bid_lion_name = lion_name_lookup.get(lion_ref) or top_bid.get("lion_name") or top_bid.get("lion")
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
        serialized = serialize_lion_record(normalized)
        serialized["bidding_open"] = is_bidding_window_open(serialized, now)
        attach_primary_image_url(serialized)
        lions.append(serialized)
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
        if serialized.get("id"):
            lion_lookup[serialized["id"]] = serialized
        if serialized.get("name"):
            lion_lookup[serialized["name"]] = serialized
        if serialized.get("slug"):
            lion_lookup[serialized["slug"]] = serialized

    bids = get_bids()
    enriched_bids = []
    bids_by_lion = {}
    for bid in bids:
        bid["id"] = str(bid["_id"])
        lion_ref = bid.get("lion_id") or bid.get("lion")
        lion_match = lion_lookup.get(lion_ref) if lion_ref else None
        if not lion_match and bid.get("lion_name"):
            lion_match = lion_lookup.get(bid.get("lion_name"))
        bid["lion_name"] = lion_match.get("name") if lion_match else (bid.get("lion_name") or bid.get("lion"))
        bid["lion_id"] = bid.get("lion_id") or (lion_match.get("id") if lion_match else None)
        enriched_bids.append(bid)

        group_key = bid.get("lion_id") or (lion_match.get("id") if lion_match else None) or (bid.get("lion_name") or bid.get("lion") or "unknown")
        if group_key not in bids_by_lion:
            bids_by_lion[group_key] = {
                "lion": lion_match,
                "lion_name": bid.get("lion_name") or "Unknown lion",
                "lion_id": bid.get("lion_id") or (lion_match.get("id") if lion_match else None),
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
    source_lion = normalize_lion_time_fields(get_lion_by_id(lion_id))
    lion = serialize_lion_record(source_lion)
    if not lion:
        abort(404)
    lion["images"] = get_lion_images(lion_id)
    return render_template("admin_lion_detail.html", lion=lion)


@app.route("/admin/lions/<lion_id>/qr.png")
@admin_required
def admin_lion_qr(lion_id):
    lion = get_lion_by_id(lion_id)
    if not lion:
        abort(404)

    buffer = io.BytesIO(generate_lion_qr_png(lion_id))
    buffer.seek(0)

    response = send_file(
        buffer,
        mimetype="image/png",
        download_name=f"lion-{lion_id}-qr.png",
    )
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/admin/lions/<lion_id>/qr.pdf")
@admin_required
def admin_lion_qr_pdf(lion_id):
    source_lion = normalize_lion_time_fields(get_lion_by_id(lion_id))
    lion = serialize_lion_record(source_lion)
    if not lion:
        abort(404)

    qr_png = generate_lion_qr_png(lion_id)
    qr_base64 = base64.b64encode(qr_png).decode("ascii")

    html = render_template(
        "admin_lion_qr_pdf.html",
        lions=[{"lion": lion, "qr_base64": qr_base64}],
        generated_at=datetime.now(HKT_TZ),
    )
    pdf_bytes = HTML(string=html, base_url=None).write_pdf()

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename="lion-{lion_id}-qr.pdf"'
    response.headers["Cache-Control"] = "private, max-age=300"
    return response


@app.route("/admin/qr-codes.pdf")
@admin_required
def admin_all_qr_pdf():
    all_lions = get_lions()
    entries = []
    for lion in all_lions:
        lion = serialize_lion_record(normalize_lion_time_fields(lion))
        if not lion:
            continue
        lion_id = lion["id"]
        qr_png = generate_lion_qr_png(lion_id)
        entries.append({"lion": lion, "qr_base64": base64.b64encode(qr_png).decode("ascii")})

    html = render_template(
        "admin_lion_qr_pdf.html",
        lions=entries,
        generated_at=datetime.now(HKT_TZ),
    )
    pdf_bytes = HTML(string=html, base_url=None).write_pdf()

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = 'inline; filename="all-qr-codes.pdf"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


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
        form.summary.data = lion.get("summary")
        form.current_bid.data = lion.get("current_bid")
        starts = lion.get("bidding_starts_at")
        ends = lion.get("bidding_ends_at")
        if starts:
            form.bidding_starts_at.data = starts.astimezone(HKT_TZ).replace(tzinfo=None)
        if ends:
            form.bidding_ends_at.data = ends.astimezone(HKT_TZ).replace(tzinfo=None)

    if form.validate_on_submit():
        uploads = extract_lion_uploads(form)
        if form.images.errors:
            return render_template("admin_lion_form.html", form=form, lion=lion, mode="edit")
        lion_document = lion_payload_from_form(form, existing_lion=source_lion)
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
    response = send_file(
        io.BytesIO(file_obj.read()),
        mimetype=getattr(file_obj, "content_type", "application/octet-stream"),
        download_name=file_obj.filename or f"lion-{image_id}",
    )
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


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


@app.route("/admin/lions/<lion_id>/delete", methods=["POST"])
@admin_required
def admin_delete_lion(lion_id):
    if delete_lion(lion_id):
        flash("Lion deleted.", "info")
    else:
        flash("Unable to delete the selected lion.", "warning")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/clear-database", methods=["POST"])
@admin_required
def admin_clear_database():
    counts = clear_database()
    flash(
        f"Database cleared — {counts['lions']} lion(s), {counts['bids']} bid(s), and {counts['images']} image(s) deleted.",
        "warning",
    )
    return redirect(url_for("admin_dashboard"))


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


@app.route("/admin/bids/<bid_id>/delete", methods=["POST"])
@admin_required
def admin_delete_bid(bid_id):
    bid = get_bid_by_id(bid_id)
    lion_id = bid.get("lion_id") if bid else None
    if delete_bid(bid_id):
        if lion_id:
            update_lion_current_bid(lion_id, get_max_bid_for_lion(lion_id))
        flash("Bid deleted.", "info")
    else:
        flash("Unable to delete the selected bid.", "warning")
    return redirect(url_for("admin_dashboard"))


@app.route("/trail/reset", methods=["GET", "POST"])
def trail_reset():
    success = False
    error = None
    if request.method == "POST":
        pin = request.form.get("pin", "")
        if pin == TRAIL_RESET_PIN:
            success = True
        else:
            error = "Incorrect PIN. Please try again."
    return render_template("trail_reset.html", success=success, error=error)


@app.route("/lions/<lion_id>", methods=["GET", "POST"])
def lion_detail(lion_id):
    lion = get_lion_by_id(lion_id)
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
        form.lion_id.data = lion_id

    if form.validate_on_submit():
        amount_value = int(form.amount.data)
        current = int(lion.get("current_bid") or 0)

        if form.lion_id.data != lion_id:
            form.lion_id.errors.append("Invalid lion reference.")
        elif not bidding_open:
            form.amount.errors.append("Bidding is closed for this lion.")
        elif amount_value <= current:
            form.amount.errors.append("Bid must exceed the current amount.")
        else:
            bid_document = {
                "lion": lion.get("name"),
                "lion_id": lion.get("id"),
                "lion_name": lion.get("name"),
                "amount": amount_value,
                "bidder": form.name.data,
                "contact": {"email": form.email.data, "phone": form.phone.data},
                "timestamp": datetime.now(timezone.utc),
            }
            insert_bid(bid_document)
            update_lion_current_bid(lion_id, amount_value)
            flash("Bid submitted successfully. We'll be in touch soon!", "success")
            return redirect(url_for("lion_detail", lion_id=lion_id))

    legacy_refs = {lion.get("name")}
    if lion.get("slug"):
        legacy_refs.add(lion.get("slug"))

    related_bids = [
        bid
        for bid in get_bids()
        if bid.get("lion_id") == lion_id
        or bid.get("lion_name") in legacy_refs
        or bid.get("lion") in legacy_refs
    ]
    return render_template(
        "lion_detail.html",
        lion=lion,
        bids=related_bids,
        form=form,
        bidding_open=bidding_open,
        current_time=now,
    )

@app.route("/map")
def map_view():
    trail_lions = []
    for record in get_lions():
        serialized = serialize_lion_record(record)
        if not serialized:
            continue
        attach_primary_image_url(serialized)
        trail_lions.append(serialized)

    trail_lions.sort(key=lambda lion: lion.get("name") or "")
    print(trail_lions)
    return render_template(
        "map.html",
        lions=trail_lions,
        total_stops=len(trail_lions),
    )

@app.context_processor
def inject_global_context():
    now = datetime.now(timezone.utc)
    return {
        "current_year": now.year,
        "current_time": now,
        "admin_logged_in": admin_is_authenticated(),
        "csrf_token": generate_csrf,
    }

# Use for development
# if __name__ == "__main__":
#     app.run(debug=True)