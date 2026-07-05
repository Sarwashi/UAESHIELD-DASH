from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
import json
import urllib.request
from dotenv import load_dotenv
from functools import wraps
from datetime import datetime, date

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "CHANGE_ME_UAE_SHIELD_SECRET")

def env_bool(name, default="false"):
    return os.getenv(name, default).lower() in ["1", "true", "yes", "on"]

def env_list(name, default=""):
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

CONFIG = {
    "DISCORD_WEBHOOK_URL": os.getenv("DISCORD_WEBHOOK_URL", ""),
    "DASHBOARD_CHANNEL_NAME": os.getenv("DASHBOARD_CHANNEL_NAME", "dashboard"),
    "REQUIRE_LOGIN": env_bool("REQUIRE_LOGIN", "false"),
    "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD", "admin123"),
    "OWNER_DISCORD_IDS": env_list("OWNER_DISCORD_IDS", ""),
    "APPROVER_POSITIONS": env_list("APPROVER_POSITIONS", "مسؤول الإدارة العليا,مسؤول الادارة العليا"),
    "PROMOTION_ALLOWED_POSITIONS": env_list("PROMOTION_ALLOWED_POSITIONS", "مسؤول الإدارة العليا,مسؤول الادارة العليا,مسؤول الاداريين"),
    "LEAVE_ALLOWED_POSITIONS": env_list("LEAVE_ALLOWED_POSITIONS", "مسؤول الإدارة العليا,مسؤول الادارة العليا,مسؤول الاداريين,نائب مسؤول الاداريين"),
    "AUTO_SEND_DASHBOARD_ON_CHANGE": env_bool("AUTO_SEND_DASHBOARD_ON_CHANGE", "false")
}

# Render-ready database path
# For persistent storage on Render, set DATABASE_PATH=/var/data/uae_shield.db
DB = os.getenv("DATABASE_PATH", "uae_shield.db")

RANKS = [
    'ᵁˢ | ⌥ 𝐎𝐖𝐍𝐄𝐑.',
    'ᵁˢ | ⌥ 𝐓𝐄𝐀𝐌.',
    'ᵁˢ | ⌥ 𝐂𝐨 𝐎𝐰𝐧𝐞𝐫.',
    'ᵁˢ | ⌥ 𝐏𝐫𝐞𝐬𝐢𝐝𝐞𝐧𝐭.',
    'ᵁˢ | ⌥ 𝐁𝐈𝐆 𝐁𝐎𝐒𝐒.',
    'ᵁˢ | ⌥ 𝐅𝐨𝐮𝐧𝐝𝐞𝐫.',
    'ᵁˢ | ⌥ 𝐂𝐨 𝐅𝐨𝐮𝐧𝐝𝐞𝐫.',
    'ᵁˢ | ⌥ 𝐋𝐨𝐫𝐝',
    'ᵁˢ | ⌥ 𝐂𝐞𝐨.',
    'ᵁˢ | ⌥ 𝐌𝐚𝐧𝐚𝐠𝐞𝐫.',
    'ᵁˢ | ⌥ 𝐀𝐝𝐦𝐢𝐧𝐢𝐬𝐭𝐫𝐚𝐭𝐢𝐨𝐧.',
    'ᵁˢ | ⌥ 𝐌𝐚𝐬𝐭𝐞𝐫.',
    'ᵁˢ | ⌥ 𝐀𝐜𝐞.',
    'ᵁˢ | ⌥ 𝐔𝐥𝐭𝐫𝐚.',
    'ᵁˢ | ⌥ 𝐀𝐥𝐩𝐡𝐚.',
    'ᵁˢ | ⌥ 𝐁𝐞𝐭𝐚.',
    'ᵁˢ | ⌥ 𝐇𝐀𝐍𝐃 𝐎𝐅 𝐇𝐈𝐆𝐇 𝐒𝐓𝐀𝐅𝐅'
]

POSITIONS = [
    '␟ | مــســؤول الإدارة الـعـلـيـا',
    '␟ | مــســؤول الإداريــيــن',
    '␟ | نــائــب مــســؤول الإداريــيــن',
    '␟ | مـســاعــد مــســؤول الإداريــيــن'
]

STATUSES = ['نشط', 'إجازة', 'غير متفاعل', 'باند', 'مفصول', 'تحت المراجعة']
PROMOTION_STATUSES = ['قيد المراجعة', 'اعتماد', 'رفض']
LEAVE_STATUSES = ['قيد المراجعة', 'مقبولة', 'مرفوضة', 'منتهية']

def db():
    db_dir = os.path.dirname(DB)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def rank_index(rank):
    return RANKS.index(rank) + 1 if rank in RANKS else 999

def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id TEXT UNIQUE NOT NULL,
        player_id TEXT,
        discord_user TEXT,
        name TEXT NOT NULL,
        rank TEXT NOT NULL,
        rank_order INTEGER NOT NULL,
        position TEXT,
        status TEXT DEFAULT 'نشط',
        join_date TEXT,
        last_promotion TEXT,
        updated_at TEXT,
        notes TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS promotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_no TEXT,
        discord_id TEXT NOT NULL,
        player_id TEXT,
        name TEXT,
        from_rank TEXT,
        to_rank TEXT,
        operation_type TEXT,
        reason TEXT,
        status TEXT DEFAULT 'قيد المراجعة',
        approved_by TEXT,
        request_date TEXT,
        decision_date TEXT,
        notes TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS leaves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        leave_no TEXT,
        discord_id TEXT NOT NULL,
        player_id TEXT,
        name TEXT,
        rank TEXT,
        start_date TEXT,
        end_date TEXT,
        days INTEGER,
        reason TEXT,
        status TEXT DEFAULT 'قيد المراجعة',
        approved_by TEXT,
        decision_date TEXT,
        notes TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS positions_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_no TEXT,
        discord_id TEXT NOT NULL,
        player_id TEXT,
        name TEXT,
        position TEXT,
        assigned_date TEXT,
        removed_date TEXT,
        status TEXT DEFAULT 'حالي',
        notes TEXT
    )
    """)

    conn.commit()
    conn.close()


def migrate_db():
    conn = db()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(staff)").fetchall()]
        if "inactive_reason" not in cols:
            conn.execute("ALTER TABLE staff ADD COLUMN inactive_reason TEXT")
        conn.execute("UPDATE staff SET status='باند' WHERE status='موقوف'")
        conn.commit()
    finally:
        conn.close()


@app.before_request
def before():
    init_db()
    migrate_db()
    update_expired_leaves()

@app.context_processor
def inject_lists():
    return dict(RANKS=RANKS, POSITIONS=POSITIONS, STATUSES=STATUSES,
                PROMOTION_STATUSES=PROMOTION_STATUSES, LEAVE_STATUSES=LEAVE_STATUSES, CONFIG=CONFIG)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not CONFIG["REQUIRE_LOGIN"]:
            return fn(*args, **kwargs)
        if session.get("logged_in"):
            return fn(*args, **kwargs)
        return redirect(url_for("login", next=request.path))
    return wrapper

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == CONFIG["ADMIN_PASSWORD"]:
            session["logged_in"] = True
            flash("تم تسجيل الدخول ✅")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("كلمة المرور غير صحيحة.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج.")
    return redirect(url_for("login"))

def position_filter_sql(position_list):
    if not position_list:
        return "1=0", []
    clauses = []
    params = []
    for p in position_list:
        clauses.append("position LIKE ?")
        params.append(f"%{p}%")
    return " OR ".join(clauses), params

def get_approvers(conn):
    where, params = position_filter_sql(CONFIG["APPROVER_POSITIONS"])
    return conn.execute(f"""
        SELECT discord_id, player_id, name, rank, position
        FROM staff
        WHERE {where}
        ORDER BY rank_order ASC, name ASC
    """, params).fetchall()


@app.route("/")
@login_required
def dashboard():
    conn = db()
    stats = {
        "total": conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0],
        "active": conn.execute("SELECT COUNT(*) FROM staff WHERE status='نشط'").fetchone()[0],
        "leave": conn.execute("SELECT COUNT(*) FROM staff WHERE status='إجازة'").fetchone()[0],
        "inactive": conn.execute("SELECT COUNT(*) FROM staff WHERE status='غير متفاعل'").fetchone()[0],
        "banned": conn.execute("SELECT COUNT(*) FROM staff WHERE status='باند'").fetchone()[0],
        "pending_promotions": conn.execute("SELECT COUNT(*) FROM promotions WHERE status='قيد المراجعة'").fetchone()[0],
        "pending_leaves": conn.execute("SELECT COUNT(*) FROM leaves WHERE status='قيد المراجعة'").fetchone()[0],
        "top_rank": conn.execute("SELECT rank FROM staff ORDER BY rank_order ASC LIMIT 1").fetchone(),
    }
    leaders = conn.execute("""
        SELECT * FROM staff
        WHERE position IN ({})
        ORDER BY CASE position
          WHEN ? THEN 1 WHEN ? THEN 2 WHEN ? THEN 3 WHEN ? THEN 4 ELSE 99 END
    """.format(",".join("?" for _ in POSITIONS)), POSITIONS + POSITIONS).fetchall()

    staff = conn.execute("SELECT * FROM staff ORDER BY rank_order ASC, name ASC").fetchall()
    latest = conn.execute("""
        SELECT request_no AS no, name, 'ترقية' AS type, status, decision_date AS d FROM promotions
        UNION ALL
        SELECT leave_no AS no, name, 'إجازة' AS type, status, decision_date AS d FROM leaves
        ORDER BY no DESC LIMIT 10
    """).fetchall()
    conn.close()
    return render_template("dashboard.html", stats=stats, leaders=leaders, staff=staff, latest=latest, discord_ready=bool(os.getenv("DISCORD_WEBHOOK_URL")))

@app.route("/staff")
@login_required
def staff_page():
    q = request.args.get("q", "").strip()
    conn = db()
    if q:
        like = f"%{q}%"
        rows = conn.execute("""
            SELECT * FROM staff
            WHERE discord_id LIKE ? OR player_id LIKE ? OR discord_user LIKE ? OR name LIKE ?
            ORDER BY rank_order ASC
        """, (like, like, like, like)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM staff ORDER BY rank_order ASC, name ASC").fetchall()
    conn.close()
    return render_template("staff.html", rows=rows, q=q)

@app.route("/staff/add", methods=["GET", "POST"])
@login_required
def staff_add():
    if request.method == "POST":
        rank = request.form["rank"]
        position = request.form.get("position", "")
        conn = db()
        try:
            conn.execute("""
                INSERT INTO staff
                (discord_id, player_id, discord_user, name, rank, rank_order, position, status, join_date, updated_at, notes, inactive_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.form["discord_id"].strip(),
                request.form.get("player_id", "").strip(),
                request.form.get("discord_user", "").strip(),
                request.form["name"].strip(),
                rank,
                rank_index(rank),
                position,
                request.form.get("status", "نشط"),
                request.form.get("join_date") or str(date.today()),
                now(),
                request.form.get("notes", ""),
                request.form.get("inactive_reason", "")
            ))
            conn.commit()
            if position:
                staff = conn.execute("SELECT * FROM staff WHERE discord_id=?", (request.form["discord_id"].strip(),)).fetchone()
                add_position_log(conn, staff, position, "حالي", "تعيين من إدارة البيانات")
                conn.commit()
            flash("تمت إضافة الإداري بنجاح ✅")
            return redirect(url_for("staff_page"))
        except sqlite3.IntegrityError:
            flash("Discord ID موجود مسبقاً.")
        finally:
            conn.close()
    return render_template("staff_form.html", row=None)

@app.route("/staff/edit/<int:id>", methods=["GET", "POST"])
@login_required
def staff_edit(id):
    conn = db()
    row = conn.execute("SELECT * FROM staff WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close()
        flash("الإداري غير موجود.")
        return redirect(url_for("staff_page"))

    if request.method == "POST":
        old_position = row["position"]
        rank = request.form["rank"]
        new_position = request.form.get("position", "")
        conn.execute("""
            UPDATE staff SET
            discord_id=?, player_id=?, discord_user=?, name=?, rank=?, rank_order=?,
            position=?, status=?, join_date=?, notes=?, inactive_reason=?, updated_at=?
            WHERE id=?
        """, (
            request.form["discord_id"].strip(),
            request.form.get("player_id", "").strip(),
            request.form.get("discord_user", "").strip(),
            request.form["name"].strip(),
            rank,
            rank_index(rank),
            new_position,
            request.form.get("status", "نشط"),
            request.form.get("join_date"),
            request.form.get("notes", ""),
            request.form.get("inactive_reason", ""),
            now(),
            id
        ))

        fresh = conn.execute("SELECT * FROM staff WHERE id=?", (id,)).fetchone()
        if new_position and new_position != old_position:
            add_position_log(conn, fresh, new_position, "حالي", "تحديث منصب من إدارة البيانات")

        conn.commit()
        conn.close()
        flash("تم تحديث البيانات ✅")
        return redirect(url_for("staff_page"))

    conn.close()
    return render_template("staff_form.html", row=row)

@app.route("/promotions", methods=["GET", "POST"])
@login_required
def promotions():
    conn = db()
    high_staff = get_approvers(conn)
    staff_options = conn.execute("SELECT discord_id, player_id, name, discord_user, rank, position FROM staff ORDER BY rank_order ASC, name ASC").fetchall()

    if request.method == "POST":
        discord_id = request.form["discord_id"].strip()
        approved_by = request.form.get("approved_by", "").strip()

        if not approved_by:
            flash("لازم تختار المعتمد من قائمة مسؤول الادارة العليا.")
            conn.close()
            return redirect(url_for("promotions"))

        staff = conn.execute("SELECT * FROM staff WHERE discord_id=?", (discord_id,)).fetchone()
        if not staff:
            flash("Discord ID غير موجود في إدارة البيانات.")
            conn.close()
            return redirect(url_for("promotions"))

        to_rank = request.form["to_rank"]
        from_rank = staff["rank"]
        op = detect_rank_operation(from_rank, to_rank)
        req_no = f"PR-{next_number(conn, 'promotions'):04d}"

        conn.execute("""
            INSERT INTO promotions
            (request_no, discord_id, player_id, name, from_rank, to_rank, operation_type, reason, status,
             approved_by, request_date, decision_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req_no, discord_id, staff["player_id"], staff["name"], from_rank, to_rank, op,
            request.form.get("reason", ""), request.form.get("status", "قيد المراجعة"),
            approved_by, str(date.today()), "", request.form.get("notes", "")
        ))
        conn.commit()
        flash("تم إنشاء طلب الترقية ✅")
        conn.close()
        return redirect(url_for("promotions"))

    rows = conn.execute("SELECT * FROM promotions ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("promotions.html", rows=rows, high_staff=high_staff, staff_options=staff_options)

@app.route("/promotions/approve/<int:id>")
@login_required
def promotion_approve(id):
    conn = db()
    p = conn.execute("SELECT * FROM promotions WHERE id=?", (id,)).fetchone()
    if not p:
        flash("الطلب غير موجود.")
        conn.close()
        return redirect(url_for("promotions"))

    conn.execute("UPDATE promotions SET status='اعتماد', decision_date=? WHERE id=?", (now(), id))
    conn.execute("""
        UPDATE staff SET rank=?, rank_order=?, last_promotion=?, updated_at=?
        WHERE discord_id=?
    """, (p["to_rank"], rank_index(p["to_rank"]), now(), now(), p["discord_id"]))
    conn.commit()
    conn.close()
    flash("تم اعتماد الطلب وتحديث رتبة الإداري ✅")
    if CONFIG["AUTO_SEND_DASHBOARD_ON_CHANGE"]:
        send_dashboard_embed_silent()
    return redirect(url_for("promotions"))

@app.route("/promotions/reject/<int:id>")
@login_required
def promotion_reject(id):
    conn = db()
    conn.execute("UPDATE promotions SET status='رفض', decision_date=? WHERE id=?", (now(), id))
    conn.commit()
    conn.close()
    flash("تم رفض الطلب.")
    return redirect(url_for("promotions"))

@app.route("/leaves", methods=["GET", "POST"])
@login_required
def leaves():
    conn = db()
    high_staff = get_approvers(conn)
    staff_options = conn.execute("SELECT discord_id, player_id, name, discord_user, rank, position FROM staff ORDER BY rank_order ASC, name ASC").fetchall()

    if request.method == "POST":
        discord_id = request.form["discord_id"].strip()
        approved_by = request.form.get("approved_by", "").strip()

        if not approved_by:
            flash("لازم تختار المعتمد من قائمة مسؤول الادارة العليا.")
            conn.close()
            return redirect(url_for("leaves"))

        staff = conn.execute("SELECT * FROM staff WHERE discord_id=?", (discord_id,)).fetchone()
        if not staff:
            flash("Discord ID غير موجود في إدارة البيانات.")
            conn.close()
            return redirect(url_for("leaves"))

        start = request.form.get("start_date")
        end = request.form.get("end_date")
        days = calc_days(start, end)
        leave_no = f"LV-{next_number(conn, 'leaves'):04d}"

        conn.execute("""
            INSERT INTO leaves
            (leave_no, discord_id, player_id, name, rank, start_date, end_date, days, reason,
             status, approved_by, decision_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            leave_no, discord_id, staff["player_id"], staff["name"], staff["rank"],
            start, end, days, request.form.get("reason", ""), request.form.get("status", "قيد المراجعة"),
            approved_by, "", request.form.get("notes", "")
        ))
        conn.commit()
        flash("تم إنشاء طلب الإجازة ✅")
        conn.close()
        return redirect(url_for("leaves"))

    rows = conn.execute("SELECT * FROM leaves ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("leaves.html", rows=rows, high_staff=high_staff, staff_options=staff_options)

@app.route("/leaves/approve/<int:id>")
@login_required
def leave_approve(id):
    conn = db()
    l = conn.execute("SELECT * FROM leaves WHERE id=?", (id,)).fetchone()
    if l:
        conn.execute("UPDATE leaves SET status='مقبولة', decision_date=? WHERE id=?", (now(), id))
        conn.execute("UPDATE staff SET status='إجازة', updated_at=? WHERE discord_id=?", (now(), l["discord_id"]))
        conn.commit()
        flash("تم اعتماد الإجازة وتحديث الحالة ✅")
        if CONFIG["AUTO_SEND_DASHBOARD_ON_CHANGE"]:
            send_dashboard_embed_silent()
    conn.close()
    return redirect(url_for("leaves"))

@app.route("/leaves/end/<int:id>")
@login_required
def leave_end(id):
    conn = db()
    l = conn.execute("SELECT * FROM leaves WHERE id=?", (id,)).fetchone()
    if l:
        conn.execute("UPDATE leaves SET status='منتهية', decision_date=? WHERE id=?", (now(), id))
        conn.execute("UPDATE staff SET status='نشط', updated_at=? WHERE discord_id=?", (now(), l["discord_id"]))
        conn.commit()
        flash("تم إنهاء الإجازة ورجوع الحالة نشط ✅")
    conn.close()
    return redirect(url_for("leaves"))

@app.route("/leaves/reject/<int:id>")
@login_required
def leave_reject(id):
    conn = db()
    conn.execute("UPDATE leaves SET status='مرفوضة', decision_date=? WHERE id=?", (now(), id))
    conn.commit()
    conn.close()
    flash("تم رفض الإجازة.")
    return redirect(url_for("leaves"))

@app.route("/profile")
@login_required
def profile():
    q = request.args.get("q", "").strip()
    staff = None
    promotions_rows, leaves_rows, positions_rows = [], [], []
    conn = db()
    if q:
        like = f"%{q}%"
        staff = conn.execute("""
            SELECT * FROM staff
            WHERE discord_id LIKE ? OR player_id LIKE ? OR discord_user LIKE ? OR name LIKE ?
            ORDER BY rank_order ASC LIMIT 1
        """, (like, like, like, like)).fetchone()
        if staff:
            promotions_rows = conn.execute("SELECT * FROM promotions WHERE discord_id=? ORDER BY id DESC", (staff["discord_id"],)).fetchall()
            leaves_rows = conn.execute("SELECT * FROM leaves WHERE discord_id=? ORDER BY id DESC", (staff["discord_id"],)).fetchall()
            positions_rows = conn.execute("SELECT * FROM positions_log WHERE discord_id=? ORDER BY id DESC", (staff["discord_id"],)).fetchall()
    conn.close()
    return render_template("profile.html", q=q, staff=staff, promotions=promotions_rows, leaves=leaves_rows, positions=positions_rows)

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def next_number(conn, table):
    return conn.execute(f"SELECT COUNT(*) + 1 FROM {table}").fetchone()[0]

def calc_days(start, end):
    try:
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end, "%Y-%m-%d").date()
        return (e - s).days + 1
    except Exception:
        return 0

def detect_rank_operation(from_rank, to_rank):
    a, b = rank_index(from_rank), rank_index(to_rank)
    if b < a:
        return "ترقية"
    if b > a:
        return "تنزيل رتبة"
    return "نفس الرتبة"

def add_position_log(conn, staff, position, status, notes):
    no = f"PO-{next_number(conn, 'positions_log'):04d}"
    conn.execute("""
        INSERT INTO positions_log
        (log_no, discord_id, player_id, name, position, assigned_date, removed_date, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (no, staff["discord_id"], staff["player_id"], staff["name"], position, now(), "", status, notes))

def update_expired_leaves():
    conn = db()
    today = str(date.today())
    rows = conn.execute("SELECT * FROM leaves WHERE status='مقبولة' AND end_date < ?", (today,)).fetchall()
    for r in rows:
        conn.execute("UPDATE leaves SET status='منتهية', decision_date=? WHERE id=?", (now(), r["id"]))
        conn.execute("UPDATE staff SET status='نشط', updated_at=? WHERE discord_id=?", (now(), r["discord_id"]))
    conn.commit()
    conn.close()



@app.route("/api/staff-search")
@login_required
def api_staff_search():
    q = request.args.get("q", "").strip()
    conn = db()

    if q:
        like = f"%{q}%"
        rows = conn.execute("""
            SELECT discord_id, player_id, discord_user, name, rank, position, status
            FROM staff
            WHERE discord_id LIKE ? OR player_id LIKE ? OR discord_user LIKE ? OR name LIKE ? OR rank LIKE ? OR position LIKE ?
            ORDER BY rank_order ASC, name ASC
            LIMIT 20
        """, (like, like, like, like, like, like)).fetchall()
    else:
        rows = conn.execute("""
            SELECT discord_id, player_id, discord_user, name, rank, position, status
            FROM staff
            ORDER BY rank_order ASC, name ASC
            LIMIT 20
        """).fetchall()

    conn.close()
    return json.dumps([dict(x) for x in rows], ensure_ascii=False)



def send_discord_payload(payload):
    webhook = CONFIG["DISCORD_WEBHOOK_URL"].strip()
    if not webhook:
        return False, "Webhook not configured"
    req = urllib.request.Request(webhook, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)
    return True, "sent"

def build_dashboard_payload():
    conn = db()
    total = conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM staff WHERE status='نشط'").fetchone()[0]
    leave = conn.execute("SELECT COUNT(*) FROM staff WHERE status='إجازة'").fetchone()[0]
    inactive = conn.execute("SELECT COUNT(*) FROM staff WHERE status='غير متفاعل'").fetchone()[0]
    banned = conn.execute("SELECT COUNT(*) FROM staff WHERE status='باند'").fetchone()[0]
    pending_p = conn.execute("SELECT COUNT(*) FROM promotions WHERE status='قيد المراجعة'").fetchone()[0]
    pending_l = conn.execute("SELECT COUNT(*) FROM leaves WHERE status='قيد المراجعة'").fetchone()[0]
    leaders = conn.execute("SELECT name, rank, position FROM staff WHERE position IN ({}) ORDER BY rank_order ASC LIMIT 4".format(",".join("?" for _ in POSITIONS)), POSITIONS).fetchall()
    conn.close()
    leaders_text = "\\n".join([f"• {x['position']} | {x['name']} | {x['rank']}" for x in leaders]) or "لا يوجد"
    return {
        "username": "UAE SHIELD Dashboard",
        "embeds": [{
            "title": "🛡 UAE SHIELD RP | Dashboard",
            "color": 13938487,
            "fields": [
                {"name": "👥 إجمالي الإداريين", "value": str(total), "inline": True},
                {"name": "✅ النشطين", "value": str(active), "inline": True},
                {"name": "✈️ في إجازة", "value": str(leave), "inline": True},
                {"name": "⚠️ غير متفاعلين", "value": str(inactive), "inline": True},
                {"name": "🚫 باند", "value": str(banned), "inline": True},
                {"name": "⭐ طلبات الترقيات", "value": str(pending_p), "inline": True},
                {"name": "📅 طلبات الإجازات", "value": str(pending_l), "inline": True},
                {"name": "👑 القيادة العليا", "value": leaders_text, "inline": False}
            ],
            "footer": {"text": f"آخر تحديث: {now()}"}
        }]
    }

def send_dashboard_embed_silent():
    try:
        send_discord_payload(build_dashboard_payload())
    except Exception:
        pass


@app.route("/discord/send-dashboard")
@login_required
def send_dashboard_to_discord():
    if not CONFIG["DISCORD_WEBHOOK_URL"].strip():
        flash("حط رابط Discord Webhook داخل ملف .env في DISCORD_WEBHOOK_URL.")
        return redirect(url_for("dashboard"))
    try:
        send_discord_payload(build_dashboard_payload())
        flash("تم إرسال الداشبورد إلى Discord ✅")
    except Exception as e:
        flash(f"فشل إرسال Discord Webhook: {e}")
    return redirect(url_for("dashboard"))

@app.route("/settings")
@login_required
def settings():
    safe_config = {
        "DASHBOARD_CHANNEL_NAME": CONFIG["DASHBOARD_CHANNEL_NAME"],
        "REQUIRE_LOGIN": CONFIG["REQUIRE_LOGIN"],
        "OWNER_DISCORD_IDS": CONFIG["OWNER_DISCORD_IDS"],
        "APPROVER_POSITIONS": CONFIG["APPROVER_POSITIONS"],
        "PROMOTION_ALLOWED_POSITIONS": CONFIG["PROMOTION_ALLOWED_POSITIONS"],
        "LEAVE_ALLOWED_POSITIONS": CONFIG["LEAVE_ALLOWED_POSITIONS"],
        "AUTO_SEND_DASHBOARD_ON_CHANGE": CONFIG["AUTO_SEND_DASHBOARD_ON_CHANGE"],
        "DISCORD_WEBHOOK_CONNECTED": bool(CONFIG["DISCORD_WEBHOOK_URL"])
    }
    return render_template("settings.html", config=safe_config)


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
