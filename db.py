import sqlite3

DB_PATH = "schedule.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

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
            )
            -- users (опционально, для входа преподавателей)
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'teacher'
            );

            -- students (студенты группы)
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );

            -- attendance (отметки посещаемости)
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id TEXT NOT NULL,        -- ссылается на lessons.id (текстовый ID из парсера)
                student_id INTEGER NOT NULL,
                status TEXT CHECK(status IN ('present', 'late', 'absent', 'excused')),
                marked_by INTEGER,              -- кто отметил (id из users)
                marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lesson_id) REFERENCES lessons(id),
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (marked_by) REFERENCES users(id),
                UNIQUE(lesson_id, student_id)
            );
        """)

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