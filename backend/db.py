import sqlite3

DB_PATH = "schedule.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)   # ждать до 10 сек
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS disciplines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                para INTEGER NOT NULL,
                podgr INTEGER,
                zam INTEGER,
                teacher_id INTEGER,
                discipline_id INTEGER,
                group_id INTEGER,
                room TEXT,
                file_num INTEGER,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id),
                FOREIGN KEY (discipline_id) REFERENCES disciplines(id),
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'teacher',
                group_id INTEGER,
                curator_group_id INTEGER,
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (curator_group_id) REFERENCES groups(id)
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                subgroup INTEGER DEFAULT 0,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                status TEXT CHECK(status IN ('present', 'late', 'absent', 'excused')),
                marked_by INTEGER,
                marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lesson_id) REFERENCES lessons(id),
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (marked_by) REFERENCES users(id),
                UNIQUE(lesson_id, student_id)
            );
            CREATE TABLE IF NOT EXISTS user_curator_groups (
                user_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (group_id) REFERENCES groups(id),
                PRIMARY KEY (user_id, group_id)
            );
        """)
        # Миграции: добавляем столбцы если их нет
        try:
            conn.execute("ALTER TABLE users ADD COLUMN group_id INTEGER REFERENCES groups(id)")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN curator_group_id INTEGER REFERENCES groups(id)")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE students ADD COLUMN subgroup INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # Создаём администратора, если нет пользователей
        cur = conn.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            from werkzeug.security import generate_password_hash
            admin_hash = generate_password_hash("admin")
            conn.execute("""
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?)
            """, ("admin", admin_hash, "Администратор", "admin"))
            conn.commit()

def get_user_by_username(username):
    with get_connection() as conn:
        cur = conn.execute("SELECT id, username, password_hash, role, group_id, curator_group_id FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if row:
            return {"id": row[0], "username": row[1], "password_hash": row[2], "role": row[3], "group_id": row[4], "curator_group_id": row[5]}
        return None

def upsert_group(code):
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO groups (code) VALUES (?)", (code,))
        cur = conn.execute("SELECT id FROM groups WHERE code = ?", (code,))
        return cur.fetchone()[0]

def upsert_teacher(name):
    if not name:
        return None
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO teachers (name) VALUES (?)", (name,))
        cur = conn.execute("SELECT id FROM teachers WHERE name = ?", (name,))
        return cur.fetchone()[0]

def upsert_discipline(name):
    if not name:
        return None
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO disciplines (name) VALUES (?)", (name,))
        cur = conn.execute("SELECT id FROM disciplines WHERE name = ?", (name,))
        return cur.fetchone()[0]

def insert_lesson(lesson):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO lessons
            (id, date, para, podgr, zam, teacher_id, discipline_id, group_id, room, file_num)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lesson["id"],
            lesson["date"],
            lesson["para"],
            lesson["podgr"],
            lesson["zam"],
            lesson["teacher_id"],
            lesson["discipline_id"],
            lesson["group_id"],
            lesson.get("room", ""),
            lesson["file_num"]
        ))

def set_last_processed_file(file_num):
    with get_connection() as conn:
        conn.execute("REPLACE INTO metadata (key, value) VALUES ('last_file', ?)", (str(file_num),))

def get_last_processed_file():
    with get_connection() as conn:
        cur = conn.execute("SELECT value FROM metadata WHERE key = 'last_file'")
        row = cur.fetchone()
        return int(row[0]) if row else 0

def get_group_id_by_code(code):
    """Возвращает id группы по её коду."""
    with get_connection() as conn:
        cur = conn.execute("SELECT id FROM groups WHERE code = ?", (code,))
        row = cur.fetchone()
        return row[0] if row else None

def get_group_code_by_id(group_id):
    """Возвращает код группы по её id."""
    with get_connection() as conn:
        cur = conn.execute("SELECT code FROM groups WHERE id = ?", (group_id,))
        row = cur.fetchone()
        return row[0] if row else None

def add_curator_group(user_id, group_id, conn=None):
    if conn is None:
        with get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO user_curator_groups (user_id, group_id) VALUES (?, ?)", (user_id, group_id))
            conn.commit()
    else:
        conn.execute("INSERT OR IGNORE INTO user_curator_groups (user_id, group_id) VALUES (?, ?)", (user_id, group_id))

def remove_curator_groups(user_id, conn=None):
    if conn is None:
        with get_connection() as conn:
            conn.execute("DELETE FROM user_curator_groups WHERE user_id = ?", (user_id,))
            conn.commit()
    else:
        conn.execute("DELETE FROM user_curator_groups WHERE user_id = ?", (user_id,))

def get_curator_groups(user_id, conn=None):
    if conn is None:
        with get_connection() as conn:
            cur = conn.execute("SELECT group_id FROM user_curator_groups WHERE user_id = ?", (user_id,))
            return [row[0] for row in cur.fetchall()]
    else:
        cur = conn.execute("SELECT group_id FROM user_curator_groups WHERE user_id = ?", (user_id,))
        return [row[0] for row in cur.fetchall()]
    
def user_has_group_access(user_id, group_code):
    with get_connection() as conn:
        cur = conn.execute("SELECT role, group_id FROM users WHERE id = ?", (user_id,))
        user_row = cur.fetchone()
        if not user_row:
            return False
        role = user_row[0]
        if role == 'admin':
            return True
        elif role == 'headman':
            group_id = user_row[1]
            if group_id:
                cur = conn.execute("SELECT code FROM groups WHERE id = ?", (group_id,))
                row = cur.fetchone()
                return row and row[0] == group_code
            return False
        elif role == 'curator':
            # 1. Проверяем, есть ли группа в курируемых
            cur = conn.execute("""
                SELECT 1 FROM user_curator_groups ucg
                JOIN groups g ON ucg.group_id = g.id
                WHERE ucg.user_id = ? AND g.code = ?
            """, (user_id, group_code))
            if cur.fetchone():
                return True
            # 2. Проверяем, ведёт ли преподаватель занятия в этой группе
            cur = conn.execute("""
                SELECT 1 FROM lessons l
                JOIN groups g ON l.group_id = g.id
                WHERE l.teacher_id IN (SELECT id FROM teachers WHERE name IN (SELECT full_name FROM users WHERE id = ?))
                  AND g.code = ?
                LIMIT 1
            """, (user_id, group_code))
            return cur.fetchone() is not None
        else:  # teacher
            cur = conn.execute("""
                SELECT 1 FROM lessons l
                JOIN groups g ON l.group_id = g.id
                WHERE l.teacher_id IN (SELECT id FROM teachers WHERE name IN (SELECT full_name FROM users WHERE id = ?))
                  AND g.code = ?
                LIMIT 1
            """, (user_id, group_code))
            return cur.fetchone() is not None

def get_available_groups(user_id, role=None, teacher_id=None, conn=None):
    """Возвращает список кодов групп, доступных пользователю"""
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    try:
        if role is None:
            cur = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,))
            role = cur.fetchone()[0]

        groups = []
        if role == 'admin':
            cur = conn.execute("SELECT code FROM groups ORDER BY code")
            groups = [row[0] for row in cur.fetchall()]
        elif role == 'headman':
            cur = conn.execute("SELECT group_id FROM users WHERE id = ?", (user_id,))
            group_id = cur.fetchone()[0]
            if group_id:
                cur = conn.execute("SELECT code FROM groups WHERE id = ?", (group_id,))
                row = cur.fetchone()
                if row:
                    groups = [row[0]]
        elif role == 'curator':
            # курируемые группы
            cur = conn.execute("""
                SELECT g.code FROM user_curator_groups ucg
                JOIN groups g ON ucg.group_id = g.id
                WHERE ucg.user_id = ?
            """, (user_id,))
            groups = [row[0] for row in cur.fetchall()]
            # группы, где преподаватель ведёт занятия
            if teacher_id is None:
                cur = conn.execute("SELECT full_name FROM users WHERE id = ?", (user_id,))
                full_name = cur.fetchone()[0]
                if full_name:
                    cur = conn.execute("SELECT id FROM teachers WHERE name = ?", (full_name,))
                    row = cur.fetchone()
                    teacher_id = row[0] if row else None
            if teacher_id:
                cur = conn.execute("""
                    SELECT DISTINCT g.code FROM lessons l
                    JOIN groups g ON l.group_id = g.id
                    WHERE l.teacher_id = ?
                """, (teacher_id,))
                groups.extend([row[0] for row in cur.fetchall()])
            groups = list(set(groups))
        else:  # teacher
            if teacher_id is None:
                cur = conn.execute("SELECT full_name FROM users WHERE id = ?", (user_id,))
                full_name = cur.fetchone()[0]
                if full_name:
                    cur = conn.execute("SELECT id FROM teachers WHERE name = ?", (full_name,))
                    row = cur.fetchone()
                    teacher_id = row[0] if row else None
            if teacher_id:
                cur = conn.execute("""
                    SELECT DISTINCT g.code FROM lessons l
                    JOIN groups g ON l.group_id = g.id
                    WHERE l.teacher_id = ?
                """, (teacher_id,))
                groups = [row[0] for row in cur.fetchall()]
        return groups
    finally:
        if close_conn:
            conn.close()