PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('ADMIN','DOCTOR','CASHIER','CUSTOMER')),
    specialty TEXT NOT NULL DEFAULT '',
    degree TEXT NOT NULL DEFAULT '',
    experience_years INTEGER NOT NULL DEFAULT 0,
    bio TEXT NOT NULL DEFAULT '',
    avatar TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    price INTEGER NOT NULL CHECK(price >= 0),
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    breed TEXT NOT NULL DEFAULT '',
    birth_date TEXT,
    gender TEXT NOT NULL DEFAULT '',
    weight REAL,
    medical_history TEXT NOT NULL DEFAULT '',
    allergies TEXT NOT NULL DEFAULT '',
    image_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS vaccinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    vaccine_name TEXT NOT NULL,
    vaccinated_on TEXT NOT NULL,
    due_on TEXT,
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS doctor_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    schedule_date TEXT NOT NULL,
    shift TEXT NOT NULL DEFAULT 'Cả ngày',
    UNIQUE(doctor_id, schedule_date)
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    pet_name TEXT NOT NULL,
    appointment_date TEXT NOT NULL,
    service TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Chờ duyệt',
    customer_id INTEGER REFERENCES customers(id),
    pet_id INTEGER REFERENCES pets(id),
    doctor_id INTEGER REFERENCES users(id),
    service_id INTEGER REFERENCES services(id),
    time_slot TEXT,
    reschedule_note TEXT NOT NULL DEFAULT '',
    doctor_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS medical_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL UNIQUE REFERENCES appointments(id) ON DELETE CASCADE,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    doctor_id INTEGER NOT NULL REFERENCES users(id),
    weight REAL,
    temperature REAL,
    heart_rate INTEGER,
    symptoms TEXT NOT NULL DEFAULT '',
    diagnosis TEXT NOT NULL DEFAULT '',
    prescription TEXT NOT NULL DEFAULT '',
    attachment_path TEXT,
    examined_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    follow_up_date TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL UNIQUE REFERENCES appointments(id),
    customer_id INTEGER REFERENCES customers(id),
    examination_fee INTEGER NOT NULL DEFAULT 0,
    medicine_fee INTEGER NOT NULL DEFAULT 0,
    surcharge_fee INTEGER NOT NULL DEFAULT 0,
    total_amount INTEGER NOT NULL DEFAULT 0,
    payment_method TEXT NOT NULL CHECK(payment_method IN ('Tiền mặt','Chuyển khoản')),
    status TEXT NOT NULL DEFAULT 'Đã thanh toán',
    paid_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK(amount >= 0)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_doctor_slot 
ON appointments(doctor_id, appointment_date, time_slot) 
WHERE doctor_id IS NOT NULL AND time_slot IS NOT NULL AND status <> 'Đã hủy';
