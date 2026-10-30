import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, time, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Tự động nạp file .env nếu có để bảo đảm biến môi trường luôn sẵn sàng
def load_env_file(env_path=".env"):
    p = Path(env_path)
    if p.is_file():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("\"'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

load_env_file()

ROLES = ("ADMIN", "DOCTOR", "CASHIER", "CUSTOMER")
STATUSES = ("Chờ duyệt", "Đã xác nhận", "Đang khám", "Đã hoàn thành", "Đã hủy")
LEGACY_STATUSES = ("Chờ xác nhận",) + STATUSES
SLOTS = ("08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
DEFAULT_SERVICES = (
    ("Khám sức khỏe", 150000),
    ("Tiêm phòng", 200000),
    ("Tắm và vệ sinh", 120000),
    ("Điều trị thú cưng", 300000),
    ("Phẫu thuật ngoại khoa", 850000),
    ("Chẩn đoán hình ảnh (Siêu âm/X-quang)", 250000)
)

DEFAULT_DOCTORS_DATA = [
    {
        "username": "doctor_minh_anh",
        "full_name": "BS.CKI Nguyễn Minh Anh",
        "degree": "Bác sĩ Chuyên khoa I",
        "specialty": "Nội khoa Thú y & Dinh dưỡng",
        "bio": "Hơn 8 năm kinh nghiệm thăm khám và điều trị các bệnh lý nội khoa, tiêu hóa, hô hấp và tư vấn dinh dưỡng toàn diện cho thú cưng.",
        "experience_years": 8,
        "avatar": "images/doctors/doctor_minh_anh.jpg",
        "phone": "0901 234 501"
    },
    {
        "username": "doctor_quoc_bao",
        "full_name": "ThS.BS Trần Quốc Bảo",
        "degree": "Thạc sĩ Thú y",
        "specialty": "Ngoại khoa & Phẫu thuật Chấn thương",
        "bio": "Hơn 10 năm kinh nghiệm phẫu thuật mô mềm, chỉnh hình xương khớp và cấp cứu chấn thương phức tạp cho thú nhỏ.",
        "experience_years": 10,
        "avatar": "images/doctors/doctor_quoc_bao.jpg",
        "phone": "0901 234 502"
    },
    {
        "username": "doctor_ngoc_ha",
        "full_name": "BS. Lê Ngọc Hà",
        "degree": "Bác sĩ Thú y",
        "specialty": "Da liễu, Tiêm chủng & Nhi khoa Thú cưng",
        "bio": "Chuyên gia về điều trị viêm da, nấm ký sinh trùng, phác đồ vắc-xin bảo vệ trọn đời và chăm sóc chó mèo con mới sinh.",
        "experience_years": 6,
        "avatar": "images/doctors/doctor_ngoc_ha.jpg",
        "phone": "0901 234 503"
    },
    {
        "username": "doctor_hoang_long",
        "full_name": "BS. Phạm Hoàng Long",
        "degree": "Bác sĩ Thú y",
        "specialty": "Chẩn đoán hình ảnh (Siêu âm / X-Quang) & Hồi sức",
        "bio": "Chuyên gia siêu âm tim mạch, ổ bụng tổng quát, chụp và đọc X-quang kỹ thuật số giúp phát hiện sớm các bệnh lý tiềm ẩn.",
        "experience_years": 7,
        "avatar": "images/doctors/doctor_hoang_long.jpg",
        "phone": "0901 234 504"
    },
    {
        "username": "doctor_thu_thao",
        "full_name": "BS. Đặng Thu Thảo",
        "degree": "Bác sĩ Thú y",
        "specialty": "Nha khoa & Phục hồi chức năng Thú cưng",
        "bio": "Tận tâm chăm sóc sức khỏe răng miệng, cạo vôi răng an toàn, điều trị viêm nướu và phục hồi vận động hậu phẫu cho thú cưng.",
        "experience_years": 5,
        "avatar": "images/doctors/doctor_thu_thao.jpg",
        "phone": "0901 234 505"
    }
]

# Tương thích ngược với DEFAULT_DOCTORS cũ
DEFAULT_DOCTORS = tuple(
    (d["username"], d["full_name"], d["specialty"], d["specialty"]) for d in DEFAULT_DOCTORS_DATA
)


def slots_for_shift(shift):
    if shift == "Sáng":
        return tuple(slot for slot in SLOTS if slot < "12:00")
    if shift == "Chiều":
        return tuple(slot for slot in SLOTS if slot >= "12:00")
    return SLOTS


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("PETCARE_SECRET_KEY") or secrets.token_urlsafe(32),
        DATABASE=os.path.join(app.instance_path, "petcare.db"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        UPLOAD_FOLDER=os.path.join(app.static_folder, "uploads"),
        ADMIN_USERNAME=os.environ.get("PETCARE_ADMIN_USER", "admin"),
        ADMIN_PASSWORD=os.environ.get("PETCARE_ADMIN_PASSWORD", "admin@123"),
        DOCTOR_DEFAULT_PASSWORD=os.environ.get("PETCARE_DOCTOR_PASSWORD", "Doctor@123"),
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    for folder in ("pets", "medical", "avatars"):
        Path(app.config["UPLOAD_FOLDER"], folder).mkdir(parents=True, exist_ok=True)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        database = g.pop("db", None)
        if database:
            database.close()

    def add_column(table, column, definition):
        columns = {row[1] for row in get_db().execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            get_db().execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def init_db():
        database = get_db()
        database.executescript("""
            CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, phone TEXT NOT NULL, pet_name TEXT NOT NULL, appointment_date TEXT NOT NULL, service TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Chờ duyệt', created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, email TEXT NOT NULL, message TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, email TEXT UNIQUE, password_hash TEXT NOT NULL, full_name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('ADMIN','DOCTOR','CASHIER','CUSTOMER')), is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE, phone TEXT NOT NULL, address TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, price INTEGER NOT NULL CHECK(price >= 0), is_active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS pets (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE, name TEXT NOT NULL, species TEXT NOT NULL, breed TEXT NOT NULL DEFAULT '', birth_date TEXT, gender TEXT NOT NULL DEFAULT '', weight REAL, medical_history TEXT NOT NULL DEFAULT '', allergies TEXT NOT NULL DEFAULT '', image_path TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS vaccinations (id INTEGER PRIMARY KEY AUTOINCREMENT, pet_id INTEGER NOT NULL REFERENCES pets(id) ON DELETE CASCADE, vaccine_name TEXT NOT NULL, vaccinated_on TEXT NOT NULL, due_on TEXT, note TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS doctor_schedules (id INTEGER PRIMARY KEY AUTOINCREMENT, doctor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, schedule_date TEXT NOT NULL, shift TEXT NOT NULL DEFAULT 'Cả ngày', UNIQUE(doctor_id, schedule_date));
            CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, content TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS medical_records (id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER NOT NULL UNIQUE REFERENCES appointments(id) ON DELETE CASCADE, pet_id INTEGER NOT NULL REFERENCES pets(id), doctor_id INTEGER NOT NULL REFERENCES users(id), weight REAL, temperature REAL, heart_rate INTEGER, symptoms TEXT NOT NULL DEFAULT '', diagnosis TEXT NOT NULL DEFAULT '', prescription TEXT NOT NULL DEFAULT '', attachment_path TEXT, examined_at TEXT NOT NULL DEFAULT (datetime('now','localtime')), follow_up_date TEXT);
            CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER NOT NULL UNIQUE REFERENCES appointments(id), customer_id INTEGER REFERENCES customers(id), examination_fee INTEGER NOT NULL DEFAULT 0, medicine_fee INTEGER NOT NULL DEFAULT 0, surcharge_fee INTEGER NOT NULL DEFAULT 0, total_amount INTEGER NOT NULL DEFAULT 0, payment_method TEXT NOT NULL CHECK(payment_method IN ('Tiền mặt','Chuyển khoản')), status TEXT NOT NULL DEFAULT 'Đã thanh toán', paid_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
            CREATE TABLE IF NOT EXISTS invoice_items (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE, description TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount >= 0));
        """)

        # Nâng cấp các trường cho appointments
        for column, definition in (
            ("customer_id", "INTEGER REFERENCES customers(id)"),
            ("pet_id", "INTEGER REFERENCES pets(id)"),
            ("doctor_id", "INTEGER REFERENCES users(id)"),
            ("service_id", "INTEGER REFERENCES services(id)"),
            ("time_slot", "TEXT"),
            ("reschedule_note", "TEXT NOT NULL DEFAULT ''"),
            ("doctor_note", "TEXT NOT NULL DEFAULT ''"),
        ):
            add_column("appointments", column, definition)

        # Nâng cấp các trường hồ sơ chuyên sâu cho users (Bác sĩ, nhân sự)
        for column, definition in (
            ("avatar", "TEXT NOT NULL DEFAULT ''"),
            ("specialty", "TEXT NOT NULL DEFAULT ''"),
            ("experience_years", "INTEGER NOT NULL DEFAULT 0"),
            ("bio", "TEXT NOT NULL DEFAULT ''"),
            ("phone", "TEXT NOT NULL DEFAULT ''"),
            ("degree", "TEXT NOT NULL DEFAULT ''"),
        ):
            add_column("users", column, definition)

        database.executescript("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_doctor_slot ON appointments(doctor_id, appointment_date, time_slot) WHERE doctor_id IS NOT NULL AND time_slot IS NOT NULL AND status <> 'Đã hủy';
            CREATE INDEX IF NOT EXISTS idx_pet_customer ON pets(customer_id);
            CREATE INDEX IF NOT EXISTS idx_appointment_customer ON appointments(customer_id);
            CREATE INDEX IF NOT EXISTS idx_notification_user ON notifications(user_id,is_read);
        """)

        # Khởi tạo dịch vụ
        for name, price in DEFAULT_SERVICES:
            database.execute("INSERT OR IGNORE INTO services(name,price) VALUES (?,?)", (name, price))

        # Khởi tạo và cập nhật bác sĩ với thông tin chuyên môn, ảnh đại diện và mật khẩu an toàn
        doctor_default_pw = app.config.get("DOCTOR_DEFAULT_PASSWORD", "Doctor@123")
        for doc in DEFAULT_DOCTORS_DATA:
            existing = database.execute("SELECT id, password_hash FROM users WHERE username=?", (doc["username"],)).fetchone()
            if not existing:
                database.execute("""
                    INSERT INTO users(username, password_hash, full_name, role, specialty, experience_years, bio, avatar, phone, degree)
                    VALUES (?, ?, ?, 'DOCTOR', ?, ?, ?, ?, ?, ?)
                """, (
                    doc["username"],
                    generate_password_hash(doctor_default_pw),
                    doc["full_name"],
                    doc["specialty"],
                    doc["experience_years"],
                    doc["bio"],
                    doc["avatar"],
                    doc["phone"],
                    doc["degree"]
                ))
            else:
                # Cập nhật thông tin chuyên môn, học vị và ảnh đại diện nếu chưa có
                database.execute("""
                    UPDATE users
                    SET full_name=?, specialty=?, experience_years=?, bio=?, avatar=?, phone=?, degree=?
                    WHERE id=?
                """, (
                    doc["full_name"],
                    doc["specialty"],
                    doc["experience_years"],
                    doc["bio"],
                    doc["avatar"],
                    doc["phone"],
                    doc["degree"],
                    existing["id"]
                ))
                # Khôi phục mật khẩu nếu mật khẩu cũ không thể đăng nhập
                try:
                    if not check_password_hash(existing["password_hash"], doctor_default_pw):
                        database.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(doctor_default_pw), existing["id"]))
                except Exception:
                    database.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(doctor_default_pw), existing["id"]))

        # Khởi tạo Quản trị viên
        admin_user = app.config.get("ADMIN_USERNAME", "admin")
        admin_pass = app.config.get("ADMIN_PASSWORD", "admin@123")
        if admin_user and admin_pass:
            existing_admin = database.execute("SELECT id, password_hash FROM users WHERE username=?", (admin_user,)).fetchone()
            if not existing_admin:
                database.execute("""
                    INSERT INTO users(username, password_hash, full_name, role, specialty, degree)
                    VALUES (?, ?, ?, 'ADMIN', 'Quản trị hệ thống', 'Quản trị viên')
                """, (admin_user, generate_password_hash(admin_pass), "Quản trị viên PetCare"))
            else:
                # Đảm bảo mật khẩu admin từ cấu hình luôn hoạt động
                try:
                    if not check_password_hash(existing_admin["password_hash"], admin_pass):
                        database.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(admin_pass), existing_admin["id"]))
                except Exception:
                    database.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(admin_pass), existing_admin["id"]))

        # Khởi tạo Thu ngân demo (CASHIER)
        if not database.execute("SELECT 1 FROM users WHERE role='CASHIER'").fetchone():
            database.execute("""
                INSERT INTO users(username, password_hash, full_name, role, specialty, phone)
                VALUES (?, ?, ?, 'CASHIER', 'Kế toán & Thu ngân', '0901 234 999')
            """, ("cashier", generate_password_hash("Cashier@123"), "Trần Thị Thu Ngân"))

        # Đảm bảo khách hàng son (nếu có trong DB) có mật khẩu tiện đăng nhập thử nghiệm
        customer_son = database.execute("SELECT id, password_hash FROM users WHERE username='son'").fetchone()
        if customer_son:
            try:
                if not check_password_hash(customer_son["password_hash"], "Customer@123"):
                    database.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash("Customer@123"), customer_son["id"]))
            except Exception:
                pass

        # Tự động tạo lịch trực mẫu cho các bác sĩ trong 30 ngày nếu bảng doctor_schedules đang trống
        schedule_count = database.execute("SELECT COUNT(*) FROM doctor_schedules").fetchone()[0]
        if schedule_count == 0:
            doctors = database.execute("SELECT id FROM users WHERE role='DOCTOR' AND is_active=1").fetchall()
            today_d = date.today()
            shifts = ("Cả ngày", "Sáng", "Chiều")
            for doc_idx, doc_row in enumerate(doctors):
                for day_offset in range(30):
                    sched_date = (today_d + timedelta(days=day_offset)).isoformat()
                    # Phân ca luân phiên
                    shift_val = shifts[(doc_idx + day_offset) % len(shifts)]
                    database.execute("""
                        INSERT OR IGNORE INTO doctor_schedules(doctor_id, schedule_date, shift)
                        VALUES (?, ?, ?)
                    """, (doc_row["id"], sched_date, shift_val))

        database.commit()

    def user():
        user_id = session.get("user_id")
        return get_db().execute("SELECT * FROM users WHERE id=? AND is_active=1", (user_id,)).fetchone() if user_id else None

    def customer():
        current = user()
        return get_db().execute("SELECT * FROM customers WHERE user_id=?", (current["id"],)).fetchone() if current else None

    def role_required(*roles):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                current = user()
                if not current:
                    flash("Vui lòng đăng nhập để tiếp tục.", "error")
                    return redirect(url_for("login", next=request.path))
                if current["role"] not in roles:
                    abort(403, description="Bạn không có quyền truy cập chức năng này.")
                return view(*args, **kwargs)
            return wrapped
        return decorator

    def login_required(view): return role_required(*ROLES)(view)
    def admin_required(view): return role_required("ADMIN")(view)
    def doctor_required(view): return role_required("DOCTOR")(view)

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    @app.context_processor
    def context():
        current = user()
        count = get_db().execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (current["id"],)).fetchone()[0] if current else 0
        return {
            "current_user": current,
            "csrf_token": csrf_token(),
            "unread_notifications": count,
            "current_year": date.today().year,
            "statuses": STATUSES,
            "today_date": date.today().isoformat()
        }

    @app.before_request
    def csrf_protect():
        if request.method == "POST" and (not session.get("csrf_token") or not secrets.compare_digest(session["csrf_token"], request.form.get("csrf_token", ""))):
            abort(400, description="Phiên làm việc không hợp lệ. Vui lòng tải lại trang và thử lại.")

    def valid_phone(value):
        return bool(re.fullmatch(r"[0-9+ .()\-]{9,30}", value) and len(re.sub(r"\D", "", value)) >= 9)

    def pet_or_404(pet_id):
        result = get_db().execute("SELECT * FROM pets WHERE id=? AND customer_id=?", (pet_id, customer()["id"])).fetchone()
        if not result:
            abort(404)
        return result

    def appointment_or_404(appointment_id):
        result = get_db().execute("""
            SELECT a.*, u.full_name doctor_name, u.avatar doctor_avatar, u.specialty doctor_specialty, s.price service_price
            FROM appointments a
            LEFT JOIN users u ON u.id=a.doctor_id
            LEFT JOIN services s ON s.id=a.service_id
            WHERE a.id=?
        """, (appointment_id,)).fetchone()
        if not result:
            abort(404)
        return result

    def save_image(field, folder):
        upload = request.files.get(field)
        if not upload or not upload.filename:
            return None
        extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
        if extension not in ALLOWED_EXTENSIONS:
            raise ValueError("Chỉ chấp nhận ảnh định dạng PNG, JPG, JPEG hoặc WEBP.")
        filename = f"{secrets.token_hex(12)}.{extension}"
        upload.save(Path(app.config["UPLOAD_FOLDER"], folder, secure_filename(filename)))
        return f"uploads/{folder}/{filename}"

    def notify(user_id, text):
        get_db().execute("INSERT INTO notifications(user_id,content) VALUES (?,?)", (user_id, text))

    def doctor_profiles():
        records = get_db().execute("""
            SELECT id, username, full_name, role, specialty, experience_years, bio, avatar, phone, degree
            FROM users
            WHERE role='DOCTOR' AND is_active=1
            ORDER BY experience_years DESC, full_name ASC
        """).fetchall()
        result = []
        for r in records:
            result.append({
                "id": r["id"],
                "username": r["username"],
                "name": r["full_name"],
                "role": r["degree"] or "Bác sĩ thú y",
                "specialty": r["specialty"] or "Khám và điều trị thú cưng",
                "experience_years": r["experience_years"] or 5,
                "bio": r["bio"] or "Bác sĩ tận tâm, nhiều năm kinh nghiệm chăm sóc sức khỏe thú cưng.",
                "avatar": r["avatar"] or "images/default-doctor.svg",
                "phone": r["phone"] or "0900 123 456",
                "degree": r["degree"] or "Bác sĩ Thú y"
            })
        return result

    # ── TRANG CÔNG KHAI ──────────────────────────────────────────────────
    @app.get("/")
    def index():
        doctors = doctor_profiles()
        service_list = get_db().execute("SELECT * FROM services WHERE is_active=1 LIMIT 6").fetchall()
        return render_template("index.html", doctors=doctors, services=service_list)

    @app.get("/gioi-thieu")
    def about():
        doctors = doctor_profiles()
        return render_template("about.html", doctors=doctors)

    @app.get("/dich-vu")
    def services():
        return render_template("services.html", service_list=get_db().execute("SELECT * FROM services WHERE is_active=1").fetchall())

    @app.get("/bac-si")
    def doctors():
        return render_template("doctors.html", doctors=doctor_profiles())

    @app.get("/bac-si/<int:doctor_id>")
    def doctor_detail(doctor_id):
        database = get_db()
        doctor = database.execute("""
            SELECT id, username, full_name, role, specialty, experience_years, bio, avatar, phone, degree
            FROM users
            WHERE id=? AND role='DOCTOR' AND is_active=1
        """, (doctor_id,)).fetchone()
        if not doctor:
            abort(404, description="Không tìm thấy thông tin bác sĩ yêu cầu.")

        # Lấy lịch trực 7 ngày tới của bác sĩ
        today_str = date.today().isoformat()
        next_week = (date.today() + timedelta(days=7)).isoformat()
        schedules = database.execute("""
            SELECT schedule_date, shift
            FROM doctor_schedules
            WHERE doctor_id=? AND schedule_date >= ? AND schedule_date <= ?
            ORDER BY schedule_date ASC
        """, (doctor_id, today_str, next_week)).fetchall()

        # Danh sách bác sĩ khác để giới thiệu thêm
        other_doctors = database.execute("""
            SELECT id, full_name, specialty, avatar, degree, experience_years
            FROM users
            WHERE role='DOCTOR' AND is_active=1 AND id <> ?
            LIMIT 3
        """, (doctor_id,)).fetchall()

        return render_template("doctor_detail.html", doctor=doctor, schedules=schedules, other_doctors=other_doctors)

    @app.get("/chinh-sach")
    def policy():
        return render_template("policy.html")

    # ── XÁC THỰC & TÀI KHOẢN ─────────────────────────────────────────────
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if user():
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            full_name, username, email, phone, password = (request.form.get(key, "").strip() for key in ("full_name", "username", "email", "phone", "password"))
            if not all((full_name, username, email, phone, password)) or len(password) < 8 or not valid_phone(phone) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                flash("Thông tin chưa hợp lệ; mật khẩu cần ít nhất 8 ký tự, email và số điện thoại đúng định dạng.", "error")
            else:
                try:
                    database = get_db()
                    cursor = database.execute("INSERT INTO users(username,email,password_hash,full_name,role) VALUES (?,?,?,?,?)", (username, email, generate_password_hash(password), full_name, "CUSTOMER"))
                    database.execute("INSERT INTO customers(user_id,phone,address) VALUES (?,?,?)", (cursor.lastrowid, phone, request.form.get("address", "").strip()[:250]))
                    database.commit()
                    flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
                    return redirect(url_for("login"))
                except sqlite3.IntegrityError:
                    flash("Tên đăng nhập hoặc email đã được sử dụng.", "error")
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    @app.route("/admin/login", methods=["GET", "POST"])
    @app.route("/doctor/login", methods=["GET", "POST"])
    def login():
        current = user()
        if current:
            return redirect(url_for("dashboard"))

        # Xác định ngữ cảnh đăng nhập nếu vào từ url bác sĩ hoặc admin
        login_type = "general"
        if request.path.startswith("/admin"):
            login_type = "admin"
        elif request.path.startswith("/doctor"):
            login_type = "doctor"

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            account = get_db().execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
            if account and check_password_hash(account["password_hash"], password):
                session.clear()
                session["user_id"] = account["id"]
                csrf_token()
                destination = request.args.get("next", "")
                if destination and destination.startswith("/") and not destination.startswith("//"):
                    return redirect(destination)
                return redirect(url_for("dashboard"))
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")

        # Nếu vào /admin/login thì render template admin_login.html cho tương thích bài test
        if login_type == "admin":
            return render_template("admin_login.html")
        return render_template("login.html", login_type=login_type)

    @app.post("/logout")
    @app.post("/admin/logout")
    @login_required
    def logout():
        session.clear()
        flash("Bạn đã đăng xuất thành công.", "success")
        return redirect(url_for("login"))

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST":
            username_or_email = request.form.get("identity", "").strip()
            if username_or_email:
                flash("Yêu cầu đã được ghi nhận. Vui lòng liên hệ ban quản trị để xác minh và đặt lại mật khẩu an toàn.", "success")
            else:
                flash("Vui lòng nhập tên đăng nhập hoặc email.", "error")
            return redirect(url_for("login"))
        return render_template("forgot_password.html")

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        account, client = user(), customer()
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            password = request.form.get("new_password", "")
            phone = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()[:250]

            if not full_name:
                flash("Họ và tên không được để trống.", "error")
            elif client and phone and not valid_phone(phone):
                flash("Số điện thoại không đúng định dạng.", "error")
            elif password and len(password) < 8:
                flash("Mật khẩu mới phải có ít nhất 8 ký tự.", "error")
            else:
                database = get_db()
                database.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, account["id"]))
                if client:
                    database.execute("UPDATE customers SET phone=?, address=? WHERE id=?", (phone, address, client["id"]))
                if password:
                    database.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), account["id"]))
                database.commit()
                flash("Đã cập nhật hồ sơ cá nhân thành công.", "success")
                return redirect(url_for("profile"))
        return render_template("profile.html", customer=client)

    @app.get("/dashboard")
    @login_required
    def dashboard():
        current = user()
        if current["role"] == "ADMIN":
            return redirect(url_for("admin_dashboard"))
        if current["role"] == "DOCTOR":
            return redirect(url_for("doctor_dashboard"))
        if current["role"] == "CASHIER":
            return redirect(url_for("cashier_dashboard"))

        # Dashboard khách hàng
        client = customer()
        database = get_db()
        pets = database.execute("SELECT * FROM pets WHERE customer_id=? ORDER BY id DESC", (client["id"],)).fetchall() if client else []
        appointments = database.execute("""
            SELECT a.*, u.full_name doctor_name, s.name service_title
            FROM appointments a
            LEFT JOIN users u ON u.id=a.doctor_id
            LEFT JOIN services s ON s.id=a.service_id
            WHERE a.customer_id=?
            ORDER BY a.appointment_date DESC, a.time_slot DESC
            LIMIT 5
        """, (client["id"],)).fetchall() if client else []
        return render_template("customer_dashboard.html", pets=pets, appointments=appointments)

    # ── QUẢN LÝ THÚ CƯNG (KHÁCH HÀNG) ───────────────────────────────────
    @app.get("/pets")
    @role_required("CUSTOMER")
    def pets():
        pets_list = get_db().execute("SELECT * FROM pets WHERE customer_id=? ORDER BY id DESC", (customer()["id"],)).fetchall()
        return render_template("pets.html", pets=pets_list)

    @app.route("/pets/new", methods=["GET", "POST"])
    @app.route("/pets/<int:pet_id>/edit", methods=["GET", "POST"])
    @role_required("CUSTOMER")
    def pet_form(pet_id=None):
        pet = pet_or_404(pet_id) if pet_id else None
        if request.method == "POST":
            name, species = request.form.get("name", "").strip(), request.form.get("species", "").strip()
            if not name or not species:
                flash("Tên và loài thú cưng là bắt buộc.", "error")
            else:
                try:
                    image_path = save_image("image", "pets")
                except ValueError as error:
                    flash(str(error), "error")
                    return render_template("pet_form.html", pet=pet)

                values = (
                    name[:100],
                    species[:80],
                    request.form.get("breed", "").strip()[:100],
                    request.form.get("birth_date") or None,
                    request.form.get("gender", "").strip()[:20],
                    request.form.get("weight") or None,
                    request.form.get("medical_history", "").strip()[:2000],
                    request.form.get("allergies", "").strip()[:1000]
                )
                database = get_db()
                if pet:
                    database.execute("""
                        UPDATE pets
                        SET name=?, species=?, breed=?, birth_date=?, gender=?, weight=?, medical_history=?, allergies=?, image_path=COALESCE(?, image_path)
                        WHERE id=?
                    """, values + (image_path, pet_id))
                else:
                    database.execute("""
                        INSERT INTO pets(customer_id, name, species, breed, birth_date, gender, weight, medical_history, allergies, image_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (customer()["id"],) + values + (image_path,))
                database.commit()
                flash("Đã lưu hồ sơ thú cưng thành công.", "success")
                return redirect(url_for("pets"))
        return render_template("pet_form.html", pet=pet)

    @app.post("/pets/<int:pet_id>/delete")
    @role_required("CUSTOMER")
    def delete_pet(pet_id):
        pet_or_404(pet_id)
        get_db().execute("DELETE FROM pets WHERE id=?", (pet_id,))
        get_db().commit()
        flash("Đã xóa hồ sơ thú cưng thành công.", "success")
        return redirect(url_for("pets"))

    @app.route("/pets/<int:pet_id>/vaccinations", methods=["GET", "POST"])
    @role_required("CUSTOMER")
    def vaccinations(pet_id):
        pet = pet_or_404(pet_id)
        if request.method == "POST":
            vaccine_name = request.form.get("vaccine_name", "").strip()
            vaccinated_on = request.form.get("vaccinated_on")
            if not vaccine_name or not vaccinated_on:
                flash("Vui lòng nhập tên vắc-xin và ngày tiêm.", "error")
            else:
                get_db().execute("""
                    INSERT INTO vaccinations(pet_id, vaccine_name, vaccinated_on, due_on, note)
                    VALUES (?, ?, ?, ?, ?)
                """, (pet_id, vaccine_name[:120], vaccinated_on, request.form.get("due_on") or None, request.form.get("note", "").strip()[:1000]))
                get_db().commit()
                flash("Đã thêm thông tin mũi tiêm phòng.", "success")
                return redirect(url_for("vaccinations", pet_id=pet_id))
        vacc_list = get_db().execute("SELECT * FROM vaccinations WHERE pet_id=? ORDER BY vaccinated_on DESC", (pet_id,)).fetchall()
        return render_template("vaccinations.html", pet=pet, vaccinations=vacc_list)

    # ── ĐẶT LỊCH & LỊCH HẸN ──────────────────────────────────────────────
    @app.get("/api/slots")
    def slots():
        doctor_id = request.args.get("doctor_id", type=int)
        scheduled_date = request.args.get("date", "")
        if not doctor_id or not scheduled_date:
            return jsonify({"slots": []})

        scheduled = get_db().execute("SELECT shift FROM doctor_schedules WHERE doctor_id=? AND schedule_date=?", (doctor_id, scheduled_date)).fetchone()
        if not scheduled:
            # Fallback nếu bác sĩ chưa đăng ký ca trực cụ thể ngày này nhưng vẫn làm việc
            return jsonify({"slots": []})

        busy = {record[0] for record in get_db().execute("SELECT time_slot FROM appointments WHERE doctor_id=? AND appointment_date=? AND status <> 'Đã hủy'", (doctor_id, scheduled_date))}
        available_slots = [slot for slot in slots_for_shift(scheduled["shift"]) if slot not in busy]
        return jsonify({"slots": available_slots})

    @app.route("/dat-lich", methods=["GET", "POST"])
    def book_appointment():
        account = user()
        client = customer() if account and account["role"] == "CUSTOMER" else None
        database = get_db()
        doctors = database.execute("SELECT id, full_name, specialty, avatar FROM users WHERE role='DOCTOR' AND is_active=1 ORDER BY full_name").fetchall()
        service_list = database.execute("SELECT * FROM services WHERE is_active=1").fetchall()

        if request.method == "GET":
            pets_list = database.execute("SELECT * FROM pets WHERE customer_id=?", (client["id"],)).fetchall() if client else []
            return render_template("booking.html", doctors=doctors, service_list=service_list, pets=pets_list)

        scheduled_date = request.form.get("appointment_date", "")
        service_id = request.form.get("service_id", type=int)
        doctor_id = request.form.get("doctor_id", type=int)
        slot = request.form.get("time_slot", "")

        try:
            valid_date = date.fromisoformat(scheduled_date)
        except ValueError:
            valid_date = None

        service = database.execute("SELECT * FROM services WHERE id=? AND is_active=1", (service_id,)).fetchone()
        if not service:
            service = database.execute("SELECT * FROM services WHERE name=? AND is_active=1", (request.form.get("service", ""),)).fetchone()

        if not valid_date or valid_date < date.today():
            flash("Ngày khám phải từ hôm nay trở đi.", "error")
            return redirect(url_for("book_appointment"))

        if not service:
            flash("Dịch vụ không hợp lệ.", "error")
            return redirect(url_for("book_appointment"))

        if client:
            pet_id_input = request.form.get("pet_id", type=int)
            pet = pet_or_404(pet_id_input) if pet_id_input else None
            if not pet:
                flash("Vui lòng chọn thú cưng cần khám.", "error")
                return redirect(url_for("book_appointment"))
            full_name, phone, pet_name = account["full_name"], client["phone"], pet["name"]
        else:
            full_name, phone, pet_name = (request.form.get(key, "").strip() for key in ("full_name", "phone", "pet_name"))
            pet = None
            if not full_name or not pet_name:
                flash("Vui lòng điền đầy đủ các trường bắt buộc.", "error")
                return redirect(url_for("book_appointment"))
            if not valid_phone(phone):
                flash("Số điện thoại chưa đúng định dạng.", "error")
                return redirect(url_for("book_appointment"))

        schedule = database.execute("SELECT shift FROM doctor_schedules WHERE doctor_id=? AND schedule_date=?", (doctor_id, scheduled_date)).fetchone() if doctor_id else None
        if doctor_id and (slot not in SLOTS or not schedule or slot not in slots_for_shift(schedule["shift"])):
            flash("Bác sĩ hoặc khung giờ không khả dụng.", "error")
            return redirect(url_for("book_appointment"))

        try:
            cursor = database.execute("""
                INSERT INTO appointments(full_name, phone, pet_name, appointment_date, service, note, status, customer_id, pet_id, doctor_id, service_id, time_slot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                full_name, phone, pet_name, scheduled_date, service["name"],
                request.form.get("note", "").strip()[:1000], "Chờ duyệt",
                client["id"] if client else None, pet["id"] if pet else None,
                doctor_id, service_id, slot or None
            ))
            # Thông báo cho Bác sĩ nếu có chỉ định bác sĩ
            if doctor_id:
                notify(doctor_id, f"Bạn có lịch hẹn mới #{cursor.lastrowid} cho thú cưng {pet_name} vào ngày {scheduled_date} ({slot or 'Chưa chọn giờ'}).")
            database.commit()
        except sqlite3.IntegrityError:
            database.rollback()
            flash("Khung giờ này vừa được đặt. Vui lòng chọn giờ khác.", "error")
            return redirect(url_for("book_appointment"))

        flash("Đặt lịch thành công! Đội ngũ PetCare sẽ xác nhận lịch hẹn của bạn sớm nhất.", "success")
        return redirect(url_for("appointments") if client else url_for("book_appointment"))

    @app.get("/appointments")
    @role_required("CUSTOMER")
    def appointments():
        appts = get_db().execute("""
            SELECT a.*, u.full_name doctor_name, u.avatar doctor_avatar, i.id invoice_id, i.total_amount, mr.id record_id
            FROM appointments a
            LEFT JOIN users u ON u.id=a.doctor_id
            LEFT JOIN invoices i ON i.appointment_id=a.id
            LEFT JOIN medical_records mr ON mr.appointment_id=a.id
            WHERE a.customer_id=?
            ORDER BY a.appointment_date DESC, a.time_slot DESC
        """, (customer()["id"],)).fetchall()
        return render_template("appointments.html", appointments=appts)

    @app.get("/medical-records/<int:appointment_id>")
    @login_required
    def medical_record_detail(appointment_id):
        appointment = appointment_or_404(appointment_id)
        account = user()
        if account["role"] == "CUSTOMER" and appointment["customer_id"] != customer()["id"]:
            abort(403)
        if account["role"] == "DOCTOR" and appointment["doctor_id"] != account["id"]:
            abort(403)
        if account["role"] not in ("CUSTOMER", "DOCTOR", "ADMIN"):
            abort(403)

        record = get_db().execute("""
            SELECT mr.*, u.full_name doctor_name, u.degree doctor_degree, u.avatar doctor_avatar
            FROM medical_records mr
            JOIN users u ON u.id=mr.doctor_id
            WHERE mr.appointment_id=?
        """, (appointment_id,)).fetchone()
        if not record:
            abort(404, description="Hồ sơ bệnh án chưa được lập.")
        return render_template("medical_record_detail.html", appointment=appointment, record=record)

    @app.post("/appointments/<int:appointment_id>/cancel")
    @role_required("CUSTOMER")
    def cancel_appointment(appointment_id):
        appointment = appointment_or_404(appointment_id)
        if appointment["customer_id"] != customer()["id"]:
            abort(403)
        start = datetime.combine(date.fromisoformat(appointment["appointment_date"]), time.fromisoformat(appointment["time_slot"] or "00:00"))
        if start - datetime.now() < timedelta(hours=4):
            flash("Chỉ được hủy lịch trước giờ khám tối thiểu 4 tiếng theo quy định của phòng khám.", "error")
        elif appointment["status"] not in ("Chờ duyệt", "Đã xác nhận"):
            flash("Lịch hẹn này không thể hủy vì đã hoặc đang trong quá trình thực hiện.", "error")
        else:
            get_db().execute("UPDATE appointments SET status='Đã hủy' WHERE id=?", (appointment_id,))
            get_db().commit()
            flash("Đã hủy lịch hẹn thành công.", "success")
        return redirect(url_for("appointments"))

    @app.get("/notifications")
    @login_required
    def notifications():
        rows = get_db().execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (user()["id"],)).fetchall()
        get_db().execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user()["id"],))
        get_db().commit()
        return render_template("notifications.html", notifications=rows)

    # ── CỔNG BÁC SĨ (DOCTOR PORTAL) ──────────────────────────────────────
    @app.get("/doctor")
    @role_required("DOCTOR")
    def doctor_dashboard():
        database = get_db()
        current_doctor = user()
        doctor_id = current_doctor["id"]
        today_iso = date.today().isoformat()

        # Thống kê nhanh cho bác sĩ
        today_count = database.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id=? AND appointment_date=?", (doctor_id, today_iso)).fetchone()[0]
        pending_count = database.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id=? AND appointment_date=? AND status IN ('Đã xác nhận', 'Đang khám')", (doctor_id, today_iso)).fetchone()[0]
        completed_count = database.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id=? AND status='Đã hoàn thành'", (doctor_id,)).fetchone()[0]
        total_assigned = database.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id=?", (doctor_id,)).fetchone()[0]

        # Bộ lọc ca khám
        date_filter = request.args.get("date_filter", "today")
        status_filter = request.args.get("status_filter", "all")
        query_text = request.args.get("q", "").strip()

        sql = """
            SELECT a.*, p.species, p.breed, p.image_path pet_image, mr.id record_id
            FROM appointments a
            LEFT JOIN pets p ON p.id=a.pet_id
            LEFT JOIN medical_records mr ON mr.appointment_id=a.id
            WHERE a.doctor_id=?
        """
        params = [doctor_id]

        if date_filter == "today":
            sql += " AND a.appointment_date = ?"
            params.append(today_iso)
        elif date_filter == "tomorrow":
            tomorrow_iso = (date.today() + timedelta(days=1)).isoformat()
            sql += " AND a.appointment_date = ?"
            params.append(tomorrow_iso)
        elif date_filter == "week":
            week_later_iso = (date.today() + timedelta(days=7)).isoformat()
            sql += " AND a.appointment_date >= ? AND a.appointment_date <= ?"
            params.extend([today_iso, week_later_iso])

        if status_filter != "all" and status_filter in STATUSES:
            sql += " AND a.status = ?"
            params.append(status_filter)

        if query_text:
            sql += " AND (a.full_name LIKE ? OR a.pet_name LIKE ? OR a.phone LIKE ?)"
            wildcard = f"%{query_text}%"
            params.extend([wildcard, wildcard, wildcard])

        sql += " ORDER BY a.appointment_date ASC, a.time_slot ASC"
        appointments = database.execute(sql, tuple(params)).fetchall()

        # Lịch trực sắp tới của bác sĩ
        schedules = database.execute("""
            SELECT schedule_date, shift
            FROM doctor_schedules
            WHERE doctor_id=? AND schedule_date >= ?
            ORDER BY schedule_date ASC
            LIMIT 7
        """, (doctor_id, today_iso)).fetchall()

        return render_template(
            "doctor_dashboard.html",
            appointments=appointments,
            today_count=today_count,
            pending_count=pending_count,
            completed_count=completed_count,
            total_assigned=total_assigned,
            date_filter=date_filter,
            status_filter=status_filter,
            query_text=query_text,
            schedules=schedules
        )

    @app.get("/doctor/schedules")
    @role_required("DOCTOR")
    def doctor_schedules():
        current_doctor = user()
        today_iso = date.today().isoformat()
        schedules = get_db().execute("""
            SELECT * FROM doctor_schedules
            WHERE doctor_id=? AND schedule_date >= ?
            ORDER BY schedule_date ASC
        """, (current_doctor["id"], today_iso)).fetchall()
        return render_template("doctor_schedules.html", schedules=schedules)

    @app.route("/doctor/profile", methods=["GET", "POST"])
    @role_required("DOCTOR")
    def doctor_profile():
        doctor = user()
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            specialty = request.form.get("specialty", "").strip()
            phone = request.form.get("phone", "").strip()
            bio = request.form.get("bio", "").strip()
            degree = request.form.get("degree", "").strip()
            experience = request.form.get("experience_years", type=int) or 0
            new_password = request.form.get("new_password", "")

            if not full_name:
                flash("Họ và tên bác sĩ không được để trống.", "error")
            elif new_password and len(new_password) < 8:
                flash("Mật khẩu mới phải có ít nhất 8 ký tự.", "error")
            else:
                avatar_path = None
                try:
                    avatar_path = save_image("avatar", "avatars")
                except ValueError as err:
                    flash(str(err), "error")
                    return render_template("doctor_profile.html", doctor=doctor)

                database = get_db()
                database.execute("""
                    UPDATE users
                    SET full_name=?, specialty=?, phone=?, bio=?, degree=?, experience_years=?, avatar=COALESCE(?, avatar)
                    WHERE id=?
                """, (full_name, specialty, phone, bio, degree, experience, avatar_path, doctor["id"]))

                if new_password:
                    database.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), doctor["id"]))

                database.commit()
                flash("Đã cập nhật hồ sơ chuyên môn bác sĩ thành công.", "success")
                return redirect(url_for("doctor_profile"))
        return render_template("doctor_profile.html", doctor=doctor)

    @app.get("/doctor/pets/<int:pet_id>/history")
    @role_required("DOCTOR", "ADMIN")
    def doctor_pet_history(pet_id):
        database = get_db()
        pet = database.execute("""
            SELECT p.*, c.phone customer_phone, c.address customer_address, u.full_name owner_name
            FROM pets p
            JOIN customers c ON c.id=p.customer_id
            JOIN users u ON u.id=c.user_id
            WHERE p.id=?
        """, (pet_id,)).fetchone()
        if not pet:
            abort(404, description="Không tìm thấy hồ sơ thú cưng.")

        records = database.execute("""
            SELECT mr.*, a.appointment_date, a.service, u.full_name doctor_name
            FROM medical_records mr
            JOIN appointments a ON a.id=mr.appointment_id
            JOIN users u ON u.id=mr.doctor_id
            WHERE mr.pet_id=?
            ORDER BY a.appointment_date DESC
        """, (pet_id,)).fetchall()

        vaccinations_list = database.execute("""
            SELECT * FROM vaccinations WHERE pet_id=? ORDER BY vaccinated_on DESC
        """, (pet_id,)).fetchall()

        return render_template("doctor_pet_history.html", pet=pet, records=records, vaccinations=vaccinations_list)

    @app.route("/doctor/exams/<int:appointment_id>", methods=["GET", "POST"])
    @role_required("DOCTOR")
    def doctor_exam(appointment_id):
        appointment = appointment_or_404(appointment_id)
        if appointment["doctor_id"] != user()["id"]:
            abort(403, description="Ca khám này được chỉ định cho bác sĩ khác.")
        if not appointment["pet_id"]:
            abort(400, description="Lịch hẹn này chưa liên kết hồ sơ thú cưng.")

        database = get_db()
        record = database.execute("SELECT * FROM medical_records WHERE appointment_id=?", (appointment_id,)).fetchone()
        pet = database.execute("SELECT * FROM pets WHERE id=?", (appointment["pet_id"],)).fetchone()

        if request.method == "POST":
            try:
                attachment = save_image("attachment", "medical")
            except ValueError as error:
                flash(str(error), "error")
                return render_template("exam_form.html", appointment=appointment, record=record, pet=pet)

            values = (
                request.form.get("weight") or None,
                request.form.get("temperature") or None,
                request.form.get("heart_rate") or None,
                request.form.get("symptoms", "").strip()[:3000],
                request.form.get("diagnosis", "").strip()[:3000],
                request.form.get("prescription", "").strip()[:4000],
                request.form.get("follow_up_date") or None
            )
            if record:
                database.execute("""
                    UPDATE medical_records
                    SET weight=?, temperature=?, heart_rate=?, symptoms=?, diagnosis=?, prescription=?, follow_up_date=?, attachment_path=COALESCE(?, attachment_path)
                    WHERE id=?
                """, values + (attachment, record["id"]))
            else:
                database.execute("""
                    INSERT INTO medical_records(appointment_id, pet_id, doctor_id, weight, temperature, heart_rate, symptoms, diagnosis, prescription, follow_up_date, attachment_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (appointment_id, appointment["pet_id"], user()["id"]) + values + (attachment,))

            # Cập nhật cân nặng mới nhất cho hồ sơ thú cưng nếu có
            if request.form.get("weight"):
                try:
                    database.execute("UPDATE pets SET weight=? WHERE id=?", (float(request.form.get("weight")), appointment["pet_id"]))
                except ValueError:
                    pass

            database.execute("UPDATE appointments SET status='Đã hoàn thành' WHERE id=?", (appointment_id,))
            if appointment["customer_id"]:
                customer_user = database.execute("SELECT user_id FROM customers WHERE id=?", (appointment["customer_id"],)).fetchone()
                if customer_user:
                    notify(customer_user["user_id"], f"Bệnh án của bé {appointment['pet_name']} đã được hoàn tất bởi {user()['full_name']}.")
                    if request.form.get("follow_up_date"):
                        notify(customer_user["user_id"], f"Bé {appointment['pet_name']} có lịch hẹn tái khám vào ngày {request.form['follow_up_date']}.")

            database.commit()
            flash("Đã lưu kết quả khám và cập nhật trạng thái ca khám thành 'Đã hoàn thành'.", "success")
            return redirect(url_for("doctor_dashboard"))

        if appointment["status"] == "Đã xác nhận":
            database.execute("UPDATE appointments SET status='Đang khám' WHERE id=?", (appointment_id,))
            database.commit()

        return render_template("exam_form.html", appointment=appointment, record=record, pet=pet)

    # ── CỔNG THU NGÂN (CASHIER) ──────────────────────────────────────────
    @app.get("/cashier")
    @role_required("CASHIER")
    def cashier_dashboard():
        database = get_db()
        pending_invoices = database.execute("""
            SELECT a.*, s.price service_price
            FROM appointments a
            LEFT JOIN invoices i ON i.appointment_id=a.id
            LEFT JOIN services s ON s.id=a.service_id
            WHERE a.status='Đã hoàn thành' AND i.id IS NULL
            ORDER BY a.appointment_date DESC
        """).fetchall()
        pending_approval = database.execute("SELECT * FROM appointments WHERE status='Chờ duyệt' ORDER BY appointment_date ASC").fetchall()
        recent_invoices = database.execute("""
            SELECT i.*, a.pet_name, a.full_name
            FROM invoices i
            JOIN appointments a ON a.id=i.appointment_id
            ORDER BY i.id DESC LIMIT 10
        """).fetchall()
        return render_template("cashier_dashboard.html", pending=pending_invoices, pending_approval=pending_approval, recent_invoices=recent_invoices)

    @app.post("/cashier/appointments/<int:appointment_id>/approve")
    @role_required("CASHIER", "ADMIN")
    def approve_appointment(appointment_id):
        appointment = appointment_or_404(appointment_id)
        if appointment["status"] != "Chờ duyệt":
            abort(400)
        database = get_db()
        database.execute("UPDATE appointments SET status='Đã xác nhận' WHERE id=?", (appointment_id,))
        if appointment["customer_id"]:
            cust = database.execute("SELECT user_id FROM customers WHERE id=?", (appointment["customer_id"],)).fetchone()
            if cust:
                notify(cust["user_id"], f"Lịch hẹn khám #{appointment_id} của {appointment['pet_name']} đã được xác nhận.")
        database.commit()
        flash("Đã duyệt và xác nhận lịch hẹn.", "success")
        return redirect(url_for("cashier_dashboard") if user()["role"] == "CASHIER" else url_for("admin_dashboard"))

    @app.route("/cashier/invoices/new/<int:appointment_id>", methods=["GET", "POST"])
    @role_required("CASHIER", "ADMIN")
    def create_invoice(appointment_id):
        appointment = appointment_or_404(appointment_id)
        database = get_db()
        exists = database.execute("SELECT 1 FROM invoices WHERE appointment_id=?", (appointment_id,)).fetchone()
        base_fee = appointment["service_price"] or 0
        if appointment["status"] != "Đã hoàn thành" or exists:
            abort(400, description="Không thể tạo hóa đơn cho lịch hẹn này.")

        if request.method == "POST":
            try:
                medicine = max(0, int(request.form.get("medicine_fee", "0") or 0))
                items = [(name.strip()[:150], max(0, int(amount or 0))) for name, amount in zip(request.form.getlist("item_name"), request.form.getlist("item_amount")) if name.strip()]
            except ValueError:
                flash("Chi phí phải là số nguyên không âm.", "error")
                return render_template("invoice_form.html", appointment=appointment, base_fee=base_fee)

            surcharge = sum(item[1] for item in items)
            total = base_fee + medicine + surcharge
            payment_method = request.form.get("payment_method") if request.form.get("payment_method") in ("Tiền mặt", "Chuyển khoản") else "Tiền mặt"
            cursor = database.execute("""
                INSERT INTO invoices(appointment_id, customer_id, examination_fee, medicine_fee, surcharge_fee, total_amount, payment_method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (appointment_id, appointment["customer_id"], base_fee, medicine, surcharge, total, payment_method))
            invoice_id = cursor.lastrowid
            database.executemany("INSERT INTO invoice_items(invoice_id, description, amount) VALUES (?, ?, ?)", [(invoice_id,) + item for item in items])
            database.commit()
            flash("Đã thanh toán và lập hóa đơn thành công.", "success")
            return redirect(url_for("print_invoice", invoice_id=invoice_id))

        return render_template("invoice_form.html", appointment=appointment, base_fee=base_fee)

    @app.get("/invoices/<int:invoice_id>/print")
    @login_required
    def print_invoice(invoice_id):
        invoice = get_db().execute("""
            SELECT i.*, a.pet_name, a.full_name, a.phone, a.appointment_date, a.service, u.full_name doctor_name
            FROM invoices i
            JOIN appointments a ON a.id=i.appointment_id
            LEFT JOIN users u ON u.id=a.doctor_id
            WHERE i.id=?
        """, (invoice_id,)).fetchone()
        if not invoice:
            abort(404)
        if user()["role"] == "CUSTOMER" and invoice["customer_id"] != customer()["id"]:
            abort(403)
        if user()["role"] not in ("CUSTOMER", "CASHIER", "ADMIN"):
            abort(403)
        items = get_db().execute("SELECT * FROM invoice_items WHERE invoice_id=?", (invoice_id,)).fetchall()
        return render_template("invoice_print.html", invoice=invoice, items=items)

    # ── CỔNG QUẢN TRỊ VIÊN (ADMIN) ───────────────────────────────────────
    @app.get("/admin")
    @admin_required
    def admin_dashboard():
        database = get_db()
        metrics = {
            "customers": database.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            "pets": database.execute("SELECT COUNT(*) FROM pets").fetchone()[0],
            "appointments": database.execute("SELECT COUNT(*) FROM appointments").fetchone()[0],
            "revenue": database.execute("SELECT COALESCE(SUM(total_amount), 0) FROM invoices").fetchone()[0]
        }
        chart = database.execute("""
            SELECT substr(paid_at, 1, 10) label, SUM(total_amount) value
            FROM invoices
            GROUP BY substr(paid_at, 1, 10)
            ORDER BY label DESC LIMIT 7
        """).fetchall()
        chart_data = [dict(row) for row in reversed(chart)]

        # Tìm kiếm và lọc lịch hẹn cho Admin
        status_filter = request.args.get("status", "")
        q = request.args.get("q", "").strip()
        appt_sql = """
            SELECT a.*, u.full_name doctor_name
            FROM appointments a
            LEFT JOIN users u ON u.id=a.doctor_id
            WHERE 1=1
        """
        appt_params = []
        if status_filter in STATUSES:
            appt_sql += " AND a.status = ?"
            appt_params.append(status_filter)
        if q:
            appt_sql += " AND (a.full_name LIKE ? OR a.pet_name LIKE ? OR a.phone LIKE ?)"
            wildcard = f"%{q}%"
            appt_params.extend([wildcard, wildcard, wildcard])
        appt_sql += " ORDER BY a.id DESC LIMIT 15"

        appointments = database.execute(appt_sql, tuple(appt_params)).fetchall()
        messages = database.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 5").fetchall()
        return render_template(
            "admin_dashboard.html",
            metrics=metrics,
            chart=json.dumps(chart_data),
            appointments=appointments,
            messages=messages,
            status_filter=status_filter,
            q=q
        )

    @app.route("/admin/staff", methods=["GET", "POST"])
    @admin_required
    def admin_staff():
        database = get_db()
        if request.method == "POST":
            action = request.form.get("action", "create")
            if action == "create":
                username, full_name, password, role = (request.form.get(key, "").strip() for key in ("username", "full_name", "password", "role"))
                specialty = request.form.get("specialty", "").strip()
                degree = request.form.get("degree", "").strip()
                if role not in ("DOCTOR", "CASHIER") or not username or not full_name or len(password) < 8:
                    flash("Thông tin nhân sự chưa hợp lệ (mật khẩu cần tối thiểu 8 ký tự).", "error")
                else:
                    try:
                        database.execute("""
                            INSERT INTO users(username, password_hash, full_name, role, specialty, degree)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (username, generate_password_hash(password), full_name, role, specialty, degree))
                        database.commit()
                        flash("Đã thêm nhân sự thành công.", "success")
                    except sqlite3.IntegrityError:
                        flash("Tên đăng nhập đã tồn tại trong hệ thống.", "error")
            elif action == "toggle_active":
                target_id = request.form.get("user_id", type=int)
                if target_id:
                    user_row = database.execute("SELECT is_active FROM users WHERE id=?", (target_id,)).fetchone()
                    if user_row:
                        new_state = 0 if user_row["is_active"] else 1
                        database.execute("UPDATE users SET is_active=? WHERE id=?", (new_state, target_id))
                        database.commit()
                        flash("Đã thay đổi trạng thái kích hoạt của nhân sự.", "success")
            elif action == "reset_password":
                target_id = request.form.get("user_id", type=int)
                new_pw = request.form.get("new_password", "").strip()
                if target_id and len(new_pw) >= 8:
                    database.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_pw), target_id))
                    database.commit()
                    flash("Đã đặt lại mật khẩu nhân sự thành công.", "success")
                else:
                    flash("Mật khẩu mới cần ít nhất 8 ký tự.", "error")

        staff_list = database.execute("SELECT * FROM users WHERE role IN ('DOCTOR','CASHIER') ORDER BY role ASC, full_name ASC").fetchall()
        return render_template("staff.html", staff=staff_list)

    @app.route("/admin/services", methods=["GET", "POST"])
    @admin_required
    def admin_services():
        database = get_db()
        if request.method == "POST":
            action = request.form.get("action", "create")
            if action == "create":
                try:
                    price = int(request.form.get("price", ""))
                except ValueError:
                    price = -1
                name = request.form.get("name", "").strip()
                if not name or price < 0:
                    flash("Tên dịch vụ và giá chưa hợp lệ.", "error")
                else:
                    try:
                        database.execute("INSERT INTO services(name, price) VALUES (?, ?)", (name[:120], price))
                        database.commit()
                        flash("Đã thêm dịch vụ mới thành công.", "success")
                    except sqlite3.IntegrityError:
                        flash("Tên dịch vụ đã tồn tại.", "error")
            elif action == "toggle_active":
                service_id = request.form.get("service_id", type=int)
                svc = database.execute("SELECT is_active FROM services WHERE id=?", (service_id,)).fetchone()
                if svc:
                    new_val = 0 if svc["is_active"] else 1
                    database.execute("UPDATE services SET is_active=? WHERE id=?", (new_val, service_id))
                    database.commit()
                    flash("Đã cập nhật trạng thái hiển thị của dịch vụ.", "success")

        return render_template("services_admin.html", service_list=database.execute("SELECT * FROM services ORDER BY id ASC").fetchall())

    @app.route("/admin/schedules", methods=["GET", "POST"])
    @admin_required
    def admin_schedules():
        database = get_db()
        doctors = database.execute("SELECT id, full_name FROM users WHERE role='DOCTOR' AND is_active=1 ORDER BY full_name").fetchall()
        if request.method == "POST":
            doctor_id = request.form.get("doctor_id", type=int)
            schedule_date = request.form.get("schedule_date", "")
            shift = request.form.get("shift", "Cả ngày")
            try:
                date.fromisoformat(schedule_date)
            except ValueError:
                schedule_date = ""

            if not doctor_id or not schedule_date or shift not in ("Sáng", "Chiều", "Cả ngày") or not database.execute("SELECT 1 FROM users WHERE id=? AND role='DOCTOR'", (doctor_id,)).fetchone():
                flash("Thông tin lịch trực chưa hợp lệ.", "error")
            else:
                database.execute("""
                    INSERT INTO doctor_schedules(doctor_id, schedule_date, shift)
                    VALUES (?, ?, ?)
                    ON CONFLICT(doctor_id, schedule_date) DO UPDATE SET shift=excluded.shift
                """, (doctor_id, schedule_date, shift))
                database.commit()
                flash("Đã lưu lịch trực bác sĩ thành công.", "success")
                return redirect(url_for("admin_schedules"))

        schedules = database.execute("""
            SELECT ds.*, u.full_name
            FROM doctor_schedules ds
            JOIN users u ON u.id=ds.doctor_id
            ORDER BY ds.schedule_date DESC, u.full_name ASC
            LIMIT 40
        """).fetchall()
        return render_template("schedules.html", doctors=doctors, schedules=schedules)

    @app.route("/admin/appointments/new", methods=["GET", "POST"])
    @app.route("/admin/appointments/<int:appointment_id>/edit", methods=["GET", "POST"])
    @admin_required
    def admin_appointment_form(appointment_id=None):
        appointment = appointment_or_404(appointment_id) if appointment_id else None
        database = get_db()
        doctors = database.execute("SELECT id, full_name FROM users WHERE role='DOCTOR' AND is_active=1 ORDER BY full_name").fetchall()
        service_list = database.execute("SELECT * FROM services WHERE is_active=1").fetchall()

        if request.method == "POST":
            fields = {key: request.form.get(key, "").strip() for key in ("full_name", "phone", "pet_name", "appointment_date", "service", "note")}
            doctor_id = request.form.get("doctor_id", type=int) or None
            time_slot = request.form.get("time_slot", "").strip() or None

            if not all(fields[key] for key in ("full_name", "phone", "pet_name", "appointment_date", "service")) or not valid_phone(fields["phone"]):
                flash("Thông tin lịch hẹn chưa hợp lệ.", "error")
            else:
                status = request.form.get("status") if request.form.get("status") in LEGACY_STATUSES else "Chờ duyệt"
                if appointment:
                    database.execute("""
                        UPDATE appointments
                        SET full_name=?, phone=?, pet_name=?, appointment_date=?, service=?, note=?, status=?, doctor_id=?, time_slot=?
                        WHERE id=?
                    """, tuple(fields.values()) + (status, doctor_id, time_slot, appointment_id))
                else:
                    database.execute("""
                        INSERT INTO appointments(full_name, phone, pet_name, appointment_date, service, note, status, doctor_id, time_slot)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, tuple(fields.values()) + (status, doctor_id, time_slot))
                database.commit()
                flash("Đã lưu lịch hẹn.", "success")
                return redirect(url_for("admin_dashboard"))

        return render_template("admin_appointment_form.html", appointment=appointment, statuses=LEGACY_STATUSES, doctors=doctors, services=service_list)

    @app.post("/admin/appointments/<int:appointment_id>/status")
    @admin_required
    def update_appointment_status(appointment_id):
        status = request.form.get("status", "")
        if status not in LEGACY_STATUSES:
            abort(400)
        result = get_db().execute("UPDATE appointments SET status=? WHERE id=?", (status, appointment_id))
        get_db().commit()
        if not result.rowcount:
            abort(404)
        flash("Đã cập nhật trạng thái lịch hẹn.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.post("/admin/appointments/<int:appointment_id>/delete")
    @admin_required
    def delete_appointment(appointment_id):
        get_db().execute("DELETE FROM appointments WHERE id=?", (appointment_id,))
        get_db().commit()
        flash("Đã xóa lịch hẹn thành công.", "success")
        return redirect(url_for("admin_dashboard"))

    # ── LIÊN HỆ & TIN NHẮN ──────────────────────────────────────────────
    @app.route("/lien-he", methods=["GET", "POST"])
    def contact():
        if request.method == "POST":
            full_name, email, message = (request.form.get(key, "").strip() for key in ("full_name", "email", "message"))
            if not full_name or not message or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                flash("Thông tin liên hệ chưa hợp lệ; vui lòng nhập họ tên, email đúng định dạng và nội dung tin nhắn.", "error")
            else:
                get_db().execute("INSERT INTO messages(full_name, email, message) VALUES (?, ?, ?)", (full_name, email, message))
                get_db().commit()
                flash("Cảm ơn bạn! Tin nhắn đã được gửi đến hệ thống.", "success")
                return redirect(url_for("contact"))
        return render_template("contact.html")

    @app.post("/admin/messages/<int:message_id>/read")
    @admin_required
    def mark_message_read(message_id):
        get_db().execute("UPDATE messages SET is_read=1 WHERE id=?", (message_id,))
        get_db().commit()
        flash("Đã đánh dấu tin nhắn là đã đọc.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.post("/admin/messages/<int:message_id>/delete")
    @admin_required
    def delete_message(message_id):
        get_db().execute("DELETE FROM messages WHERE id=?", (message_id,))
        get_db().commit()
        flash("Đã xóa tin nhắn.", "success")
        return redirect(url_for("admin_dashboard"))

    # ── XỬ LÝ LỖI (ERROR HANDLERS) ───────────────────────────────────────
    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def client_error(error):
        return render_template("error.html", code=error.code, message=getattr(error, "description", "Yêu cầu không hợp lệ.")), error.code

    @app.errorhandler(413)
    def file_too_large(_error):
        return render_template("error.html", code=413, message="Tệp tải lên vượt quá dung lượng tối đa cho phép (5 MB)."), 413

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("error.html", code=500, message="Hệ thống đang gặp sự cố tạm thời. Vui lòng thử lại sau giây lát."), 500

    with app.app_context():
        init_db()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
