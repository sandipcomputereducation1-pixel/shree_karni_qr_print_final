import os, uuid, sqlite3, qrcode, secrets, logging
from datetime import datetime
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageOps
import fitz
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE / "data")))
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB = DATA_DIR / "orders.db"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(48)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
UPI_ID = os.environ.get("UPI_ID", "")
SHOP_NAME = os.environ.get("SHOP_NAME", "Shree Karni Computer Dalot")
ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
PRINT_SIZES = {"A4", "4×6 Inch", "ID Card", "PVC Card 98×54 mm"}

logging.basicConfig(level=logging.INFO)
if not ADMIN_PASSWORD and not ADMIN_PASSWORD_HASH:
    logging.warning("ADMIN_PASSWORD or ADMIN_PASSWORD_HASH is not configured; admin login is disabled.")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, customer_name TEXT, mobile TEXT, print_size TEXT,
            copies INTEGER, payment_mode TEXT, amount REAL, payment_status TEXT,
            status TEXT, filename TEXT, original_name TEXT, created_at TEXT
        )""")
init_db()

def allowed_file(name):
    return Path(name).suffix.lower() in ALLOWED

def safe_int(value, default=1, low=1, high=100):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default

def safe_float(value, default=0):
    try:
        return max(0, min(100000, float(value)))
    except (TypeError, ValueError):
        return default

def admin_ok():
    if not ADMIN_PASSWORD and not ADMIN_PASSWORD_HASH:
        return False
    if request.form.get("username") != ADMIN_USER:
        return False
    supplied = request.form.get("password", "")
    if ADMIN_PASSWORD_HASH:
        return check_password_hash(ADMIN_PASSWORD_HASH, supplied)
    return secrets.compare_digest(supplied, ADMIN_PASSWORD)

def process_photo(source_path, output_path, rotate, zoom, make_sheet=False):
    with Image.open(source_path) as source:
        img = ImageOps.exif_transpose(source).convert("RGB")
    if rotate:
        img = img.rotate(-rotate, expand=True, resample=Image.Resampling.BICUBIC)
    target_ratio = 25 / 35
    w, h = img.size
    if w / h > target_ratio:
        nw = int(h * target_ratio)
        left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    else:
        nh = int(w / target_ratio)
        top = (h - nh) // 2
        img = img.crop((0, top, w, top + nh))
    zoom = max(1.0, min(2.0, zoom))
    if zoom > 1:
        w, h = img.size
        nw, nh = int(w / zoom), int(h / zoom)
        left, top = (w - nw)//2, (h - nh)//2
        img = img.crop((left, top, left+nw, top+nh))
    img = img.resize((295, 413), Image.Resampling.LANCZOS)
    if make_sheet:
        sheet = Image.new("RGB", (1200, 1800), "white")
        gap_x, gap_y = 5, 8
        total_w, total_h = 4 * 295 + 3 * gap_x, 2 * 413 + gap_y
        x0, y0 = (1200-total_w)//2, (1800-total_h)//2
        for row in range(2):
            for col in range(4):
                sheet.paste(img, (x0 + col*(295+gap_x), y0 + row*(413+gap_y)))
        sheet.save(output_path, "JPEG", quality=95, dpi=(300, 300))
    else:
        img.save(output_path, "JPEG", quality=94, dpi=(300, 300))

def process_pdf(source_path, output_path, page_start, page_end, rotate, margin):
    doc = fitz.open(source_path)
    if doc.is_encrypted:
        doc.close()
        raise ValueError("Encrypted PDF is not supported")
    total = len(doc)
    if total < 1:
        doc.close()
        raise ValueError("Empty PDF")
    start = max(1, min(total, page_start))
    end = max(start, min(total, page_end or total))
    out = fitz.open()
    for index in range(start - 1, end):
        page = doc[index]
        new_page = out.new_page(width=page.rect.width, height=page.rect.height)
        new_page.show_pdf_page(new_page.rect, doc, index, rotate=rotate % 360)
        if margin > 0:
            rect = new_page.rect
            inset_x = rect.width * min(margin, 20) / 100
            inset_y = rect.height * min(margin, 20) / 100
            new_page.set_cropbox(fitz.Rect(inset_x, inset_y, rect.width-inset_x, rect.height-inset_y))
    out.save(output_path, garbage=4, deflate=True)
    out.close()
    doc.close()

@app.route("/")
def home():
    return redirect(url_for("upload_page"))

@app.route("/upload", methods=["GET", "POST"])
def upload_page():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename:
            flash("कृपया फोटो या PDF चुनें।", "error")
            return redirect(url_for("upload_page"))
        if not allowed_file(f.filename):
            flash("केवल JPG, PNG, WEBP और PDF फाइल स्वीकार हैं।", "error")
            return redirect(url_for("upload_page"))
        original = secure_filename(f.filename) or "upload"
        ext = Path(original).suffix.lower()
        order_id = "SK" + datetime.now().strftime("%y%m%d") + uuid.uuid4().hex[:5].upper()
        raw_path = UPLOAD_DIR / (order_id + "_raw" + ext)
        output_name = order_id + (".pdf" if ext == ".pdf" else ".jpg")
        output_path = UPLOAD_DIR / output_name
        f.save(raw_path)
        try:
            if ext == ".pdf":
                with fitz.open(raw_path) as pdf:
                    pages = len(pdf)
                start = safe_int(request.form.get("page_start"), 1, 1, max(1, pages))
                end = safe_int(request.form.get("page_end"), pages, 1, max(1, pages))
                process_pdf(raw_path, output_path, start, end,
                            safe_int(request.form.get("pdf_rotate"), 0, 0, 270),
                            safe_float(request.form.get("pdf_margin"), 0))
            else:
                process_photo(raw_path, output_path,
                              safe_int(request.form.get("photo_rotate"), 0, 0, 270),
                              safe_float(request.form.get("photo_zoom"), 1),
                              request.form.get("make_sheet") == "yes")
        except Exception:
            raw_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)
            app.logger.exception("Upload processing failed")
            flash("फाइल प्रोसेस नहीं हो सकी। कृपया दूसरी फाइल चुनें।", "error")
            return redirect(url_for("upload_page"))
        finally:
            raw_path.unlink(missing_ok=True)

        name = request.form.get("customer_name", "").strip()[:100]
        mobile = request.form.get("mobile", "").strip()[:20]
        size = request.form.get("print_size", "A4")
        if size not in PRINT_SIZES:
            size = "A4"
        copies = safe_int(request.form.get("copies"), 1)
        payment = request.form.get("payment_mode", "Cash")
        if payment not in {"Cash", "UPI"}:
            payment = "Cash"
        amount = safe_float(request.form.get("amount", 0))
        with db() as con:
            con.execute("""INSERT INTO orders
                (id, customer_name, mobile, print_size, copies, payment_mode, amount,
                 payment_status, status, filename, original_name, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (order_id, name, mobile, size, copies, payment, amount,
                 "Unverified" if payment == "UPI" else "Cash at counter",
                 "Pending", output_name, original,
                 datetime.now().strftime("%d-%m-%Y %I:%M %p")))
        return redirect(url_for("order_page", order_id=order_id))
    return render_template("upload.html", upi_id=UPI_ID, shop_name=SHOP_NAME)

@app.route("/order/<order_id>")
def order_page(order_id):
    with db() as con:
        order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        return "Order not found", 404
    return render_template("order.html", order=order, upi_id=UPI_ID, shop_name=SHOP_NAME)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if admin_ok():
            session.clear()
            session["admin"] = True
            session.permanent = True
            return redirect(url_for("admin"))
        flash("गलत यूज़रनेम या पासवर्ड, या Admin credentials configured नहीं हैं।", "error")
    return render_template("login.html", shop_name=SHOP_NAME)

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    with db() as con:
        orders = con.execute("SELECT * FROM orders ORDER BY rowid DESC").fetchall()
        stats = con.execute("""SELECT COUNT(*) total,
            SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) pending,
            SUM(CASE WHEN status='Printing' THEN 1 ELSE 0 END) printing,
            SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) completed,
            COALESCE(SUM(CASE WHEN payment_status='Paid' OR payment_status='Cash at counter' THEN amount ELSE 0 END),0) collection
            FROM orders""").fetchone()
    return render_template("admin.html", orders=orders, stats=stats, shop_name=SHOP_NAME)

@app.route("/admin/status/<order_id>", methods=["POST"])
def update_status(order_id):
    if not session.get("admin"):
        return jsonify(ok=False), 401
    status = request.form.get("status")
    payment_status = request.form.get("payment_status", "Unverified")
    if status not in {"Pending", "Printing", "Completed"}:
        abort(400)
    if payment_status not in {"Unverified", "Paid", "Cash at counter"}:
        abort(400)
    with db() as con:
        con.execute("UPDATE orders SET status=?, payment_status=? WHERE id=?",
                    (status, payment_status, order_id))
    return redirect(url_for("admin"))

@app.route("/file/<filename>")
def get_file(filename):
    if not session.get("admin"):
        return "Unauthorized", 401
    # Only serve files whose basename is a known order output.
    with db() as con:
        exists = con.execute("SELECT 1 FROM orders WHERE filename=?", (filename,)).fetchone()
    if not exists:
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)

@app.route("/qr.png")
def qr_code():
    img = qrcode.make(request.url_root.rstrip("/") + url_for("upload_page"))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/health")
def health():
    return {"ok": True, "app": "Shree Karni QR Print System", "version": "3.0"}

@app.errorhandler(413)
def too_large(_):
    flash("फाइल का आकार 25 MB से अधिक है।", "error")
    return redirect(url_for("upload_page"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
