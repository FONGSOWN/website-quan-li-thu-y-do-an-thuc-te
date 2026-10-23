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

ROLES = ("ADMIN", "DOCTOR", "CASHIER", "CUSTOMER")
STATUSES = ("Chờ duyệt", "Đã xác nhận", "Đang khám", "Đã hoàn thành", "Đã hủy")
LEGACY_STATUSES = ("Chờ xác nhận",) + STATUSES
SLOTS = ("08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
DEFAULT_SERVICES = (("Khám sức khỏe", 150000), ("Tiêm phòng", 200000), ("Tắm và vệ sinh", 120000), ("Điều trị thú cưng", 300000))
DEFAULT_DOCTORS = (
    ("doctor_minh_anh", "BS. Nguyễn Minh Anh", "Bác sĩ thú y tổng quát", "Khám sức khỏe · Tư vấn dinh dưỡng"),
    ("doctor_quoc_bao", "BS. Trần Quốc Bảo", "Bác sĩ điều trị và phẫu thuật", "Chẩn đoán · Phẫu thuật · Theo dõi"),
    ("doctor_ngoc_ha", "BS. Lê Ngọc Hà", "Bác sĩ chăm sóc và tiêm phòng", "Tiêm phòng · Da liễu · Nhi khoa"),
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
        ADMIN_USERNAME=os.environ.get("PETCARE_ADMIN_USER"),
        ADMIN_PASSWORD=os.environ.get("PETCARE_ADMIN_PASSWORD"),
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    for folder in ("pets", "medical"):
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
        for column, definition in (("customer_id", "INTEGER REFERENCES customers(id)"), ("pet_id", "INTEGER REFERENCES pets(id)"), ("doctor_id", "INTEGER REFERENCES users(id)"), ("service_id", "INTEGER REFERENCES services(id)"), ("time_slot", "TEXT"), ("reschedule_note", "TEXT NOT NULL DEFAULT ''")):
            add_column("appointments", column, definition)
        database.executescript("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_doctor_slot ON appointments(doctor_id, appointment_date, time_slot) WHERE doctor_id IS NOT NULL AND time_slot IS NOT NULL AND status <> 'Đã hủy';
            CREATE INDEX IF NOT EXISTS idx_pet_customer ON pets(customer_id); CREATE INDEX IF NOT EXISTS idx_appointment_customer ON appointments(customer_id); CREATE INDEX IF NOT EXISTS idx_notification_user ON notifications(user_id,is_read);
        """)
        for name, price in DEFAULT_SERVICES:
            database.execute("INSERT OR IGNORE INTO services(name,price) VALUES (?,?)", (name, price))
        if not database.execute("SELECT 1 FROM users WHERE role='DOCTOR'").fetchone():
            for username, full_name, _role, _specialty in DEFAULT_DOCTORS:
                database.execute("INSERT INTO users(username,password_hash,full_name,role) VALUES (?,?,?,?)", (username, generate_password_hash(secrets.token_urlsafe(32)), full_name, "DOCTOR"))
        if app.config.get("ADMIN_USERNAME") and app.config.get("ADMIN_PASSWORD") and not database.execute("SELECT 1 FROM users WHERE username=?", (app.config["ADMIN_USERNAME"],)).fetchone():
            database.execute("INSERT INTO users(username,password_hash,full_name,role) VALUES (?,?,?,?)", (app.config["ADMIN_USERNAME"], generate_password_hash(app.config["ADMIN_PASSWORD"]), "Quản trị viên", "ADMIN"))
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

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    @app.context_processor
    def context():
        current = user()
        count = get_db().execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (current["id"],)).fetchone()[0] if current else 0
        return {"current_user": current, "csrf_token": csrf_token(), "unread_notifications": count, "current_year": date.today().year, "statuses": STATUSES}

    @app.before_request
    def csrf_protect():
        if request.method == "POST" and (not session.get("csrf_token") or not secrets.compare_digest(session["csrf_token"], request.form.get("csrf_token", ""))):
            abort(400, description="Phiên làm việc không hợp lệ. Vui lòng tải lại trang và thử lại.")

    def valid_phone(value): return bool(re.fullmatch(r"[0-9+ .()\-]{9,30}", value) and len(re.sub(r"\D", "", value)) >= 9)

    def pet_or_404(pet_id):
        result = get_db().execute("SELECT * FROM pets WHERE id=? AND customer_id=?", (pet_id, customer()["id"])).fetchone()
        if not result: abort(404)
        return result

    def appointment_or_404(appointment_id):
        result = get_db().execute("SELECT a.*, u.full_name doctor_name, s.price service_price FROM appointments a LEFT JOIN users u ON u.id=a.doctor_id LEFT JOIN services s ON s.id=a.service_id WHERE a.id=?", (appointment_id,)).fetchone()
        if not result: abort(404)
        return result

    def save_image(field, folder):
        upload = request.files.get(field)
        if not upload or not upload.filename: return None
        extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
        if extension not in ALLOWED_EXTENSIONS: raise ValueError("Chỉ chấp nhận ảnh PNG, JPG, JPEG hoặc WEBP.")
        filename = f"{secrets.token_hex(12)}.{extension}"
        upload.save(Path(app.config["UPLOAD_FOLDER"], folder, secure_filename(filename)))
        return f"uploads/{folder}/{filename}"

    def notify(user_id, text): get_db().execute("INSERT INTO notifications(user_id,content) VALUES (?,?)", (user_id, text))

    def doctor_profiles():
        records = get_db().execute("SELECT id,full_name FROM users WHERE role='DOCTOR' AND is_active=1 ORDER BY full_name").fetchall()
        catalog = {name: (role, specialty) for _username, name, role, specialty in DEFAULT_DOCTORS}
        return [{"id": record["id"], "name": record["full_name"], "role": catalog.get(record["full_name"], ("Bác sĩ thú y", "Khám và điều trị thú cưng"))[0], "specialty": catalog.get(record["full_name"], ("Bác sĩ thú y", "Khám và điều trị thú cưng"))[1]} for record in records]

    @app.get("/")
    def index(): return render_template("index.html", doctors=doctor_profiles())
    @app.get("/gioi-thieu")
    def about(): return render_template("about.html")
    @app.get("/dich-vu")
    def services(): return render_template("services.html", service_list=get_db().execute("SELECT * FROM services WHERE is_active=1").fetchall())
    @app.get("/bac-si")
    def doctors(): return render_template("doctors.html", doctors=doctor_profiles())

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            full_name, username, email, phone, password = (request.form.get(key, "").strip() for key in ("full_name", "username", "email", "phone", "password"))
            if not all((full_name, username, email, phone, password)) or len(password) < 8 or not valid_phone(phone) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email): flash("Thông tin chưa hợp lệ; mật khẩu cần ít nhất 8 ký tự.", "error")
            else:
                try:
                    database = get_db(); cursor = database.execute("INSERT INTO users(username,email,password_hash,full_name,role) VALUES (?,?,?,?,?)", (username, email, generate_password_hash(password), full_name, "CUSTOMER")); database.execute("INSERT INTO customers(user_id,phone,address) VALUES (?,?,?)", (cursor.lastrowid, phone, request.form.get("address", "").strip()[:250])); database.commit(); flash("Đăng ký thành công. Vui lòng đăng nhập.", "success"); return redirect(url_for("login"))
                except sqlite3.IntegrityError: flash("Tên đăng nhập hoặc email đã được sử dụng.", "error")
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        if user(): return redirect(url_for("dashboard"))
        if request.method == "POST":
            account = get_db().execute("SELECT * FROM users WHERE username=? AND is_active=1", (request.form.get("username", ""),)).fetchone()
            if account and check_password_hash(account["password_hash"], request.form.get("password", "")):
                session.clear(); session["user_id"] = account["id"]; csrf_token(); destination = request.args.get("next", ""); return redirect(destination if destination.startswith("/") and not destination.startswith("//") else url_for("dashboard"))
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")
        return render_template("login.html")

    @app.post("/logout")
    @app.post("/admin/logout")
    @login_required
    def logout(): session.clear(); flash("Bạn đã đăng xuất.", "success"); return redirect(url_for("login"))

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST": flash("Yêu cầu đã được ghi nhận. Hãy liên hệ quản trị viên để xác minh tài khoản.", "success"); return redirect(url_for("login"))
        return render_template("forgot_password.html")

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        account, client = user(), customer()
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip(); password = request.form.get("new_password", "")
            if not full_name or (client and not valid_phone(request.form.get("phone", "").strip())) or (password and len(password) < 8): flash("Thông tin hồ sơ hoặc mật khẩu mới chưa hợp lệ.", "error")
            else:
                database=get_db(); database.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, account["id"]));
                if client: database.execute("UPDATE customers SET phone=?,address=? WHERE id=?", (request.form.get("phone").strip(), request.form.get("address", "").strip()[:250], client["id"]))
                if password: database.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), account["id"]))
                database.commit(); flash("Đã cập nhật hồ sơ.", "success"); return redirect(url_for("profile"))
        return render_template("profile.html", customer=client)

    @app.get("/dashboard")
    @login_required
    def dashboard():
        if user()["role"] == "ADMIN": return redirect(url_for("admin_dashboard"))
        if user()["role"] == "DOCTOR": return redirect(url_for("doctor_dashboard"))
        if user()["role"] == "CASHIER": return redirect(url_for("cashier_dashboard"))
        client=customer(); database=get_db(); return render_template("customer_dashboard.html", pets=database.execute("SELECT * FROM pets WHERE customer_id=?", (client["id"],)).fetchall(), appointments=database.execute("SELECT * FROM appointments WHERE customer_id=? ORDER BY appointment_date DESC LIMIT 5", (client["id"],)).fetchall())

    @app.get("/pets")
    @role_required("CUSTOMER")
    def pets(): return render_template("pets.html", pets=get_db().execute("SELECT * FROM pets WHERE customer_id=?", (customer()["id"],)).fetchall())

    @app.route("/pets/new", methods=["GET", "POST"])
    @app.route("/pets/<int:pet_id>/edit", methods=["GET", "POST"])
    @role_required("CUSTOMER")
    def pet_form(pet_id=None):
        pet = pet_or_404(pet_id) if pet_id else None
        if request.method == "POST":
            name, species = request.form.get("name", "").strip(), request.form.get("species", "").strip()
            if not name or not species: flash("Tên và loài thú cưng là bắt buộc.", "error")
            else:
                try: image_path = save_image("image", "pets")
                except ValueError as error: flash(str(error), "error"); return render_template("pet_form.html", pet=pet)
                values=(name[:100],species[:80],request.form.get("breed", "").strip()[:100],request.form.get("birth_date") or None,request.form.get("gender", "").strip()[:20],request.form.get("weight") or None,request.form.get("medical_history", "").strip()[:2000],request.form.get("allergies", "").strip()[:1000])
                database=get_db()
                if pet: database.execute("UPDATE pets SET name=?,species=?,breed=?,birth_date=?,gender=?,weight=?,medical_history=?,allergies=?,image_path=COALESCE(?,image_path) WHERE id=?", values+(image_path,pet_id))
                else: database.execute("INSERT INTO pets(customer_id,name,species,breed,birth_date,gender,weight,medical_history,allergies,image_path) VALUES (?,?,?,?,?,?,?,?,?,?)", (customer()["id"],)+values+(image_path,))
                database.commit(); flash("Đã lưu hồ sơ thú cưng.", "success"); return redirect(url_for("pets"))
        return render_template("pet_form.html", pet=pet)

    @app.post("/pets/<int:pet_id>/delete")
    @role_required("CUSTOMER")
    def delete_pet(pet_id): pet_or_404(pet_id); get_db().execute("DELETE FROM pets WHERE id=?",(pet_id,));get_db().commit();flash("Đã xóa hồ sơ thú cưng.","success");return redirect(url_for("pets"))

    @app.route("/pets/<int:pet_id>/vaccinations", methods=["GET", "POST"])
    @role_required("CUSTOMER")
    def vaccinations(pet_id):
        pet=pet_or_404(pet_id)
        if request.method == "POST":
            if not request.form.get("vaccine_name", "").strip() or not request.form.get("vaccinated_on"): flash("Vui lòng nhập tên vắc-xin và ngày tiêm.", "error")
            else: get_db().execute("INSERT INTO vaccinations(pet_id,vaccine_name,vaccinated_on,due_on,note) VALUES (?,?,?,?,?)",(pet_id,request.form["vaccine_name"].strip()[:120],request.form["vaccinated_on"],request.form.get("due_on") or None,request.form.get("note", "").strip()[:1000]));get_db().commit();flash("Đã thêm mũi tiêm.","success");return redirect(url_for("vaccinations",pet_id=pet_id))
        return render_template("vaccinations.html",pet=pet,vaccinations=get_db().execute("SELECT * FROM vaccinations WHERE pet_id=? ORDER BY vaccinated_on DESC",(pet_id,)).fetchall())

    @app.get("/api/slots")
    @role_required("CUSTOMER")
    def slots():
        doctor_id, scheduled_date=request.args.get("doctor_id",type=int),request.args.get("date","")
        if not doctor_id or not scheduled_date: return jsonify({"slots":[]})
        scheduled=get_db().execute("SELECT shift FROM doctor_schedules WHERE doctor_id=? AND schedule_date=?",(doctor_id,scheduled_date)).fetchone()
        if not scheduled:
            return jsonify({"slots": []})
        busy={record[0] for record in get_db().execute("SELECT time_slot FROM appointments WHERE doctor_id=? AND appointment_date=? AND status <> 'Đã hủy'",(doctor_id,scheduled_date))}
        return jsonify({"slots":[slot for slot in slots_for_shift(scheduled["shift"]) if slot not in busy]})

    @app.route("/dat-lich", methods=["GET", "POST"])
    def book_appointment():
        account=user(); client=customer() if account and account["role"]=="CUSTOMER" else None; database=get_db(); doctors=database.execute("SELECT id,full_name FROM users WHERE role='DOCTOR' AND is_active=1").fetchall(); service_list=database.execute("SELECT * FROM services WHERE is_active=1").fetchall()
        if request.method == "GET": return render_template("booking.html",doctors=doctors,service_list=service_list,pets=database.execute("SELECT * FROM pets WHERE customer_id=?",(client["id"],)).fetchall() if client else [])
        scheduled_date=request.form.get("appointment_date",""); service_id=request.form.get("service_id",type=int); doctor_id=request.form.get("doctor_id",type=int); slot=request.form.get("time_slot","")
        try: valid_date=date.fromisoformat(scheduled_date)
        except ValueError: valid_date=None
        service=database.execute("SELECT * FROM services WHERE id=? AND is_active=1",(service_id,)).fetchone()
        if not service:
            service=database.execute("SELECT * FROM services WHERE name=? AND is_active=1",(request.form.get("service", ""),)).fetchone()
        if not valid_date or valid_date < date.today(): flash("Ngày khám phải từ hôm nay trở đi.","error");return redirect(url_for("book_appointment"))
        if not service: flash("Dịch vụ không hợp lệ.","error");return redirect(url_for("book_appointment"))
        if client:
            pet=pet_or_404(request.form.get("pet_id",type=int)); full_name,phone,pet_name=account["full_name"],client["phone"],pet["name"]
        else:
            full_name,phone,pet_name=(request.form.get(key,"").strip() for key in ("full_name","phone","pet_name"));pet=None
            if not full_name or not pet_name: flash("Vui lòng điền đầy đủ các trường bắt buộc.","error");return redirect(url_for("book_appointment"))
            if not valid_phone(phone): flash("Số điện thoại chưa đúng định dạng.","error");return redirect(url_for("book_appointment"))
        schedule = database.execute("SELECT shift FROM doctor_schedules WHERE doctor_id=? AND schedule_date=?",(doctor_id,scheduled_date)).fetchone() if doctor_id else None
        if doctor_id and (slot not in SLOTS or not schedule or slot not in slots_for_shift(schedule["shift"])): flash("Bác sĩ hoặc khung giờ không khả dụng.","error");return redirect(url_for("book_appointment"))
        try: database.execute("INSERT INTO appointments(full_name,phone,pet_name,appointment_date,service,note,status,customer_id,pet_id,doctor_id,service_id,time_slot) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(full_name,phone,pet_name,scheduled_date,service["name"],request.form.get("note","").strip()[:1000],"Chờ duyệt",client["id"] if client else None,pet["id"] if pet else None,doctor_id,service_id,slot or None));database.commit()
        except sqlite3.IntegrityError: database.rollback();flash("Khung giờ này vừa được đặt. Vui lòng chọn giờ khác.","error");return redirect(url_for("book_appointment"))
        flash("Đặt lịch thành công. Trung tâm sẽ duyệt lịch sớm nhất.","success");return redirect(url_for("appointments") if client else url_for("book_appointment"))

    @app.get("/appointments")
    @role_required("CUSTOMER")
    def appointments(): return render_template("appointments.html",appointments=get_db().execute("SELECT a.*,u.full_name doctor_name,i.id invoice_id,i.total_amount FROM appointments a LEFT JOIN users u ON u.id=a.doctor_id LEFT JOIN invoices i ON i.appointment_id=a.id WHERE a.customer_id=? ORDER BY a.appointment_date DESC",(customer()["id"],)).fetchall())

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
        record = get_db().execute("SELECT medical_records.*, users.full_name doctor_name FROM medical_records JOIN users ON users.id=medical_records.doctor_id WHERE appointment_id=?", (appointment_id,)).fetchone()
        if not record:
            abort(404, description="Bệnh án chưa được tạo.")
        return render_template("medical_record_detail.html", appointment=appointment, record=record)

    @app.post("/appointments/<int:appointment_id>/cancel")
    @role_required("CUSTOMER")
    def cancel_appointment(appointment_id):
        appointment=appointment_or_404(appointment_id)
        if appointment["customer_id"]!=customer()["id"]: abort(403)
        start=datetime.combine(date.fromisoformat(appointment["appointment_date"]),time.fromisoformat(appointment["time_slot"] or "00:00"))
        if start-datetime.now()<timedelta(hours=4): flash("Chỉ được hủy lịch trước giờ khám tối thiểu 4 tiếng.","error")
        elif appointment["status"] not in ("Chờ duyệt","Đã xác nhận"): flash("Lịch hẹn này không thể hủy.","error")
        else: get_db().execute("UPDATE appointments SET status='Đã hủy' WHERE id=?",(appointment_id,));get_db().commit();flash("Đã hủy lịch hẹn.","success")
        return redirect(url_for("appointments"))

    @app.get("/notifications")
    @login_required
    def notifications():
        rows=get_db().execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall();get_db().execute("UPDATE notifications SET is_read=1 WHERE user_id=?",(user()["id"],));get_db().commit();return render_template("notifications.html",notifications=rows)

    @app.get("/doctor")
    @role_required("DOCTOR")
    def doctor_dashboard(): return render_template("doctor_dashboard.html",appointments=get_db().execute("SELECT * FROM appointments WHERE doctor_id=? AND appointment_date=? AND status IN ('Đã xác nhận','Đang khám') ORDER BY time_slot",(user()["id"],date.today().isoformat())).fetchall())

    @app.route("/doctor/exams/<int:appointment_id>",methods=["GET","POST"])
    @role_required("DOCTOR")
    def doctor_exam(appointment_id):
        appointment=appointment_or_404(appointment_id)
        if appointment["doctor_id"]!=user()["id"]: abort(403)
        if not appointment["pet_id"]: abort(400,description="Lịch cũ chưa liên kết hồ sơ thú cưng.")
        database=get_db();record=database.execute("SELECT * FROM medical_records WHERE appointment_id=?",(appointment_id,)).fetchone()
        if request.method=="POST":
            try: attachment=save_image("attachment","medical")
            except ValueError as error: flash(str(error),"error");return render_template("exam_form.html",appointment=appointment,record=record)
            values=(request.form.get("weight") or None,request.form.get("temperature") or None,request.form.get("heart_rate") or None,request.form.get("symptoms","").strip()[:3000],request.form.get("diagnosis","").strip()[:3000],request.form.get("prescription","").strip()[:4000],request.form.get("follow_up_date") or None)
            if record: database.execute("UPDATE medical_records SET weight=?,temperature=?,heart_rate=?,symptoms=?,diagnosis=?,prescription=?,follow_up_date=?,attachment_path=COALESCE(?,attachment_path) WHERE id=?",values+(attachment,record["id"]))
            else: database.execute("INSERT INTO medical_records(appointment_id,pet_id,doctor_id,weight,temperature,heart_rate,symptoms,diagnosis,prescription,follow_up_date,attachment_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(appointment_id,appointment["pet_id"],user()["id"])+values+(attachment,))
            database.execute("UPDATE appointments SET status='Đã hoàn thành' WHERE id=?",(appointment_id,))
            if appointment["customer_id"]:
                customer_user = database.execute("SELECT user_id FROM customers WHERE id=?", (appointment["customer_id"],)).fetchone()
                notify(customer_user["user_id"], f"Bệnh án của {appointment['pet_name']} đã được cập nhật.")
                if request.form.get("follow_up_date"):
                    notify(customer_user["user_id"], f"{appointment['pet_name']} có lịch tái khám vào {request.form['follow_up_date']}.")
            database.commit();flash("Đã lưu bệnh án và chuyển ca khám sang hoàn thành.","success");return redirect(url_for("doctor_dashboard"))
        if appointment["status"]=="Đã xác nhận": database.execute("UPDATE appointments SET status='Đang khám' WHERE id=?",(appointment_id,));database.commit()
        return render_template("exam_form.html",appointment=appointment,record=record)

    @app.get("/cashier")
    @role_required("CASHIER")
    def cashier_dashboard():
        database=get_db();return render_template("cashier_dashboard.html",pending=database.execute("SELECT a.* FROM appointments a LEFT JOIN invoices i ON i.appointment_id=a.id WHERE a.status='Đã hoàn thành' AND i.id IS NULL").fetchall(),pending_approval=database.execute("SELECT * FROM appointments WHERE status='Chờ duyệt'").fetchall())

    @app.post("/cashier/appointments/<int:appointment_id>/approve")
    @role_required("CASHIER")
    def approve_appointment(appointment_id):
        appointment=appointment_or_404(appointment_id)
        if appointment["status"]!="Chờ duyệt": abort(400)
        database=get_db();database.execute("UPDATE appointments SET status='Đã xác nhận' WHERE id=?",(appointment_id,))
        if appointment["customer_id"]: notify(database.execute("SELECT user_id FROM customers WHERE id=?",(appointment["customer_id"],)).fetchone()[0],f"Lịch hẹn #{appointment_id} đã được xác nhận.")
        database.commit();flash("Đã xác nhận lịch hẹn.","success");return redirect(url_for("cashier_dashboard"))

    @app.route("/cashier/invoices/new/<int:appointment_id>",methods=["GET","POST"])
    @role_required("CASHIER")
    def create_invoice(appointment_id):
        appointment=appointment_or_404(appointment_id);database=get_db();exists=database.execute("SELECT 1 FROM invoices WHERE appointment_id=?",(appointment_id,)).fetchone();base_fee=appointment["service_price"] or 0
        if appointment["status"]!="Đã hoàn thành" or exists: abort(400,description="Không thể tạo hóa đơn cho lịch hẹn này.")
        if request.method=="POST":
            try: medicine=max(0,int(request.form.get("medicine_fee","0") or 0)); items=[(name.strip()[:150],max(0,int(amount or 0))) for name,amount in zip(request.form.getlist("item_name"),request.form.getlist("item_amount")) if name.strip()]
            except ValueError: flash("Chi phí phải là số nguyên không âm.","error");return render_template("invoice_form.html",appointment=appointment,base_fee=base_fee)
            surcharge=sum(item[1] for item in items);cursor=database.execute("INSERT INTO invoices(appointment_id,customer_id,examination_fee,medicine_fee,surcharge_fee,total_amount,payment_method) VALUES (?,?,?,?,?,?,?)",(appointment_id,appointment["customer_id"],base_fee,medicine,surcharge,base_fee+medicine+surcharge,request.form.get("payment_method") if request.form.get("payment_method") in ("Tiền mặt","Chuyển khoản") else "Tiền mặt"));database.executemany("INSERT INTO invoice_items(invoice_id,description,amount) VALUES (?,?,?)",[(cursor.lastrowid,)+item for item in items]);database.commit();flash("Đã thanh toán và tạo hóa đơn.","success");return redirect(url_for("print_invoice",invoice_id=cursor.lastrowid))
        return render_template("invoice_form.html",appointment=appointment,base_fee=base_fee)

    @app.get("/invoices/<int:invoice_id>/print")
    @login_required
    def print_invoice(invoice_id):
        invoice=get_db().execute("SELECT i.*,a.pet_name,a.full_name,a.appointment_date FROM invoices i JOIN appointments a ON a.id=i.appointment_id WHERE i.id=?",(invoice_id,)).fetchone()
        if not invoice: abort(404)
        if user()["role"]=="CUSTOMER" and invoice["customer_id"]!=customer()["id"]: abort(403)
        if user()["role"] not in ("CUSTOMER","CASHIER","ADMIN"): abort(403)
        return render_template("invoice_print.html",invoice=invoice,items=get_db().execute("SELECT * FROM invoice_items WHERE invoice_id=?",(invoice_id,)).fetchall())

    @app.get("/admin")
    @admin_required
    def admin_dashboard():
        database=get_db();metrics={"customers":database.execute("SELECT COUNT(*) FROM customers").fetchone()[0],"pets":database.execute("SELECT COUNT(*) FROM pets").fetchone()[0],"appointments":database.execute("SELECT COUNT(*) FROM appointments").fetchone()[0],"revenue":database.execute("SELECT COALESCE(SUM(total_amount),0) FROM invoices").fetchone()[0]};chart=database.execute("SELECT substr(paid_at,1,10) label,SUM(total_amount) value FROM invoices GROUP BY substr(paid_at,1,10) ORDER BY label DESC LIMIT 7").fetchall();return render_template("admin_dashboard.html",metrics=metrics,chart=json.dumps([dict(row) for row in chart]),appointments=database.execute("SELECT * FROM appointments ORDER BY id DESC LIMIT 10").fetchall(),messages=database.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 5").fetchall())

    @app.route("/admin/staff",methods=["GET","POST"])
    @admin_required
    def admin_staff():
        database=get_db()
        if request.method=="POST":
            username,full_name,password,role=(request.form.get(key,"").strip() for key in ("username","full_name","password","role"))
            if role not in ("DOCTOR","CASHIER") or not username or not full_name or len(password)<8: flash("Thông tin nhân sự chưa hợp lệ.","error")
            else:
                try: database.execute("INSERT INTO users(username,password_hash,full_name,role) VALUES (?,?,?,?)",(username,generate_password_hash(password),full_name,role));database.commit();flash("Đã thêm nhân sự.","success")
                except sqlite3.IntegrityError: flash("Tên đăng nhập đã tồn tại.","error")
        return render_template("staff.html",staff=database.execute("SELECT * FROM users WHERE role IN ('DOCTOR','CASHIER')").fetchall())

    @app.route("/admin/services",methods=["GET","POST"])
    @admin_required
    def admin_services():
        database=get_db()
        if request.method=="POST":
            try: price=int(request.form.get("price", ""))
            except ValueError: price=-1
            name=request.form.get("name","").strip()
            if not name or price<0: flash("Tên dịch vụ và giá chưa hợp lệ.","error")
            else:
                try: database.execute("INSERT INTO services(name,price) VALUES (?,?)",(name[:120],price));database.commit();flash("Đã thêm dịch vụ.","success")
                except sqlite3.IntegrityError: flash("Tên dịch vụ đã tồn tại.","error")
        return render_template("services_admin.html",service_list=database.execute("SELECT * FROM services").fetchall())

    @app.route("/admin/schedules", methods=["GET", "POST"])
    @admin_required
    def admin_schedules():
        database = get_db()
        doctors = database.execute("SELECT id,full_name FROM users WHERE role='DOCTOR' AND is_active=1 ORDER BY full_name").fetchall()
        if request.method == "POST":
            doctor_id, schedule_date, shift = request.form.get("doctor_id", type=int), request.form.get("schedule_date", ""), request.form.get("shift", "Cả ngày")
            try:
                date.fromisoformat(schedule_date)
            except ValueError:
                schedule_date = ""
            if not doctor_id or not schedule_date or shift not in ("Sáng", "Chiều", "Cả ngày") or not database.execute("SELECT 1 FROM users WHERE id=? AND role='DOCTOR'", (doctor_id,)).fetchone():
                flash("Thông tin lịch trực chưa hợp lệ.", "error")
            else:
                database.execute("INSERT INTO doctor_schedules(doctor_id,schedule_date,shift) VALUES (?,?,?) ON CONFLICT(doctor_id,schedule_date) DO UPDATE SET shift=excluded.shift", (doctor_id, schedule_date, shift))
                database.commit(); flash("Đã lưu lịch trực.", "success")
                return redirect(url_for("admin_schedules"))
        schedules = database.execute("SELECT doctor_schedules.*,users.full_name FROM doctor_schedules JOIN users ON users.id=doctor_schedules.doctor_id ORDER BY schedule_date DESC,users.full_name").fetchall()
        return render_template("schedules.html", doctors=doctors, schedules=schedules)

    @app.route("/admin/appointments/new",methods=["GET","POST"])
    @app.route("/admin/appointments/<int:appointment_id>/edit",methods=["GET","POST"])
    @admin_required
    def admin_appointment_form(appointment_id=None):
        appointment=appointment_or_404(appointment_id) if appointment_id else None
        if request.method=="POST":
            fields={key:request.form.get(key,"").strip() for key in ("full_name","phone","pet_name","appointment_date","service","note")}
            if not all(fields[key] for key in ("full_name","phone","pet_name","appointment_date","service")) or not valid_phone(fields["phone"]): flash("Thông tin lịch hẹn chưa hợp lệ.","error")
            else:
                status=request.form.get("status") if request.form.get("status") in LEGACY_STATUSES else "Chờ duyệt";database=get_db()
                if appointment: database.execute("UPDATE appointments SET full_name=?,phone=?,pet_name=?,appointment_date=?,service=?,note=?,status=? WHERE id=?",tuple(fields.values())+(status,appointment_id))
                else: database.execute("INSERT INTO appointments(full_name,phone,pet_name,appointment_date,service,note,status) VALUES (?,?,?,?,?,?,?)",tuple(fields.values())+(status,))
                database.commit();flash("Đã lưu lịch hẹn.","success");return redirect(url_for("admin_dashboard"))
        return render_template("admin_appointment_form.html",appointment=appointment,statuses=LEGACY_STATUSES)

    @app.post("/admin/appointments/<int:appointment_id>/status")
    @admin_required
    def update_appointment_status(appointment_id):
        status=request.form.get("status","")
        if status not in LEGACY_STATUSES: abort(400)
        result=get_db().execute("UPDATE appointments SET status=? WHERE id=?",(status,appointment_id));get_db().commit()
        if not result.rowcount: abort(404)
        flash("Đã cập nhật trạng thái lịch hẹn.","success");return redirect(url_for("admin_dashboard"))

    @app.post("/admin/appointments/<int:appointment_id>/delete")
    @admin_required
    def delete_appointment(appointment_id): get_db().execute("DELETE FROM appointments WHERE id=?",(appointment_id,));get_db().commit();flash("Đã xóa lịch hẹn.","success");return redirect(url_for("admin_dashboard"))

    @app.route("/lien-he",methods=["GET","POST"])
    def contact():
        if request.method=="POST":
            full_name,email,message=(request.form.get(key,"").strip() for key in ("full_name","email","message"))
            if not full_name or not message or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email): flash("Thông tin liên hệ chưa hợp lệ.","error")
            else: get_db().execute("INSERT INTO messages(full_name,email,message) VALUES (?,?,?)",(full_name,email,message));get_db().commit();flash("Cảm ơn bạn! Tin nhắn đã được gửi đến hệ thống.","success");return redirect(url_for("contact"))
        return render_template("contact.html")

    @app.post("/admin/messages/<int:message_id>/read")
    @admin_required
    def mark_message_read(message_id): get_db().execute("UPDATE messages SET is_read=1 WHERE id=?",(message_id,));get_db().commit();flash("Đã đánh dấu tin nhắn là đã đọc.","success");return redirect(url_for("admin_dashboard"))
    @app.post("/admin/messages/<int:message_id>/delete")
    @admin_required
    def delete_message(message_id): get_db().execute("DELETE FROM messages WHERE id=?",(message_id,));get_db().commit();flash("Đã xóa tin nhắn.","success");return redirect(url_for("admin_dashboard"))

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def client_error(error): return render_template("error.html",code=error.code,message=getattr(error,"description","Yêu cầu không hợp lệ.")),error.code
    @app.errorhandler(413)
    def file_too_large(_error): return render_template("error.html",code=413,message="Tệp tải lên vượt quá 5 MB."),413
    @app.errorhandler(500)
    def server_error(_error): return render_template("error.html",code=500,message="Hệ thống đang gặp sự cố. Vui lòng thử lại sau."),500

    with app.app_context(): init_db()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1",port=5000,debug=os.environ.get("FLASK_DEBUG")=="1")
