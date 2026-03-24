import threading
import time
from flask import Flask, jsonify, request
from db import get_connection, init_db, get_last_processed_file, set_last_processed_file
from update import process_file, full_update
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5500", "http://localhost:5500"])

# Инициализация БД при старте
init_db()

# ---------- Фоновое обновление ----------
def incremental_update():
    """Проверяет, появился ли новый файл (последний + 1)"""
    last = get_last_processed_file()
    next_file = last + 1
    if process_file(next_file):
        set_last_processed_file(next_file)
        print(f"Добавлен новый файл {next_file}.xml")
    else:
        print("Новых файлов нет.")

def refresh_recent():
    """Перепроверяет последние 2 файла на случай изменений"""
    last = get_last_processed_file()
    for f in range(max(1, last-1), last+1):
        process_file(f)   # перезапишет
    print("Последние файлы обновлены.")

def background_updater():
    # При первом запуске, если база пуста, выполним полное обновление
    if get_last_processed_file() == 0:
        print("Выполняю первичное обновление...")
        full_update()
    # Затем каждые 6 часов проверяем новые файлы
    while True:
        time.sleep(6 * 3600)      # 6 часов
        incremental_update()
        # Раз в сутки перепроверяем последние файлы
        # (для простоты делаем это тоже каждые 6 часов, можно вынести в отдельный таймер)
        refresh_recent()

# Запускаем фоновый поток
thread = threading.Thread(target=background_updater, daemon=True)
thread.start()

# ---------- API ----------
@app.route("/schedule", methods=["GET"])
def get_schedule():
    """
    Получение расписания.
    Параметры:
        group (обязательный) - код группы
        date (обязательный) - дата в формате YYYY-MM-DD
    Возвращает JSON список занятий на указанную дату для группы.
    """
    group = request.args.get("group")
    date = request.args.get("date")
    if not group or not date:
        return jsonify({"error": "Параметры group и date обязательны"}), 400

    with get_connection() as conn:
        cur = conn.execute("""
            SELECT l.id, l.date, l.para, l.podgr, l.zam, t.name, d.name, l.room
            FROM lessons l
            JOIN groups g ON l.group_id = g.id
            LEFT JOIN teachers t ON l.teacher_id = t.id
            LEFT JOIN disciplines d ON l.discipline_id = d.id
            WHERE g.code = ? AND SUBSTR(l.date, 1, 10) = ?
            ORDER BY l.para, l.podgr
        """, (group, date))
        rows = cur.fetchall()
        schedule = []
        for row in rows:
            schedule.append({
                "id": row[0],
                "date": row[1],
                "para": row[2],
                "podgr": row[3],
                "zam": bool(row[4]),   # заменённое занятие?
                "teacher": row[5] or "",
                "discipline": row[6] or "",
                "room": row[7] or ""
            })
        return jsonify(schedule)

@app.route("/schedule/week", methods=["GET"])
def get_week_schedule():
    """
    Расписание на неделю для группы.
    Параметры:
        group (обязательный) - код группы
        week_start (обязательный) - дата начала недели (понедельник) в формате YYYY-MM-DD
    Возвращает JSON с расписанием на 7 дней (пн-вс).
    """
    group = request.args.get("group")
    week_start = request.args.get("week_start")
    if not group or not week_start:
        return jsonify({"error": "Параметры group и week_start обязательны"}), 400

    # Вычисляем даты с понедельника по воскресенье
    from datetime import datetime, timedelta
    try:
        start_date = datetime.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "week_start должен быть в формате YYYY-MM-DD"}), 400

    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    with get_connection() as conn:
        cur = conn.execute("""
            SELECT l.id, l.date, l.para, l.podgr, l.zam, t.name, d.name, l.room
            FROM lessons l
            JOIN groups g ON l.group_id = g.id
            LEFT JOIN teachers t ON l.teacher_id = t.id
            LEFT JOIN disciplines d ON l.discipline_id = d.id
            WHERE g.code = ? AND SUBSTR(l.date,1,10) IN ({})
            ORDER BY l.date, l.para, l.podgr
        """.format(','.join(['?']*7)), (group, *dates))
        rows = cur.fetchall()

        # Группируем по датам
        schedule_by_day = {d: [] for d in dates}
        for row in rows:
            schedule_by_day[row[1]].append({
                "id": row[0],
                "para": row[2],
                "podgr": row[3],
                "zam": bool(row[4]),
                "teacher": row[5] or "",
                "discipline": row[6] or "",
                "room": row[7] or ""
            })
        return jsonify(schedule_by_day)

@app.route("/groups", methods=["GET"])
def list_groups():
    """Список всех групп (коды)"""
    with get_connection() as conn:
        cur = conn.execute("SELECT code FROM groups ORDER BY code")
        groups = [row[0] for row in cur.fetchall()]
        return jsonify(groups)

@app.route("/teachers", methods=["GET"])
def list_teachers():
    """Список всех преподавателей (имена)"""
    with get_connection() as conn:
        cur = conn.execute("SELECT name FROM teachers ORDER BY name")
        teachers = [row[0] for row in cur.fetchall()]
        return jsonify(teachers)

@app.route("/disciplines", methods=["GET"])
def list_disciplines():
    """Список всех дисциплин"""
    with get_connection() as conn:
        cur = conn.execute("SELECT name FROM disciplines ORDER BY name")
        disciplines = [row[0] for row in cur.fetchall()]
        return jsonify(disciplines)

@app.route("/update", methods=["POST"])
def trigger_update():
    """Принудительное обновление (новые файлы + перезапись последних)"""
    # Запускаем в отдельном потоке, чтобы не блокировать ответ
    def update():
        incremental_update()
        refresh_recent()
    thread = threading.Thread(target=update)
    thread.start()
    return jsonify({"status": "Обновление запущено в фоне"}), 202

@app.route('/students', methods=['GET'])
def get_students():
    group_code = request.args.get('group')
    if not group_code:
        return jsonify({'error': 'group param required'}), 400

    with get_connection() as conn:
        # получаем group_id по коду
        cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group_code,))
        group_row = cur.fetchone()
        if not group_row:
            return jsonify([])   # группа не найдена

        cur = conn.execute("""
            SELECT id, full_name, is_active, notes, subgroup
            FROM students
            WHERE group_id = ?
            ORDER BY full_name
        """, (group_row[0],))
        students = [{'id': row[0], 'full_name': row[1], 'is_active': bool(row[2]), 'notes': row[3], 'subgroup': row[4]} for row in cur.fetchall()]
        return jsonify(students)

@app.route('/students', methods=['POST'])
def add_student():
    data = request.json
    group_code = data.get('group')
    full_name = data.get('full_name')
    if not group_code or not full_name:
        return jsonify({'error': 'group and full_name required'}), 400

    with get_connection() as conn:
        cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group_code,))
        group_row = cur.fetchone()
        if not group_row:
            return jsonify({'error': 'Group not found'}), 404

        # вставка
        subgroup = data.get('subgroup', 0)
        cur = conn.execute("""
            INSERT INTO students (group_id, full_name, is_active, notes, subgroup)
            VALUES (?, ?, 1, ?, ?)
            RETURNING id
        """, (group_row[0], full_name, data.get('notes', ''), subgroup))
        student_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({'id': student_id}), 201

@app.route('/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    data = request.json
    with get_connection() as conn:
        conn.execute("""
            UPDATE students
            SET full_name = COALESCE(?, full_name),
                is_active = COALESCE(?, is_active),
                notes = COALESCE(?, notes),
                subgroup = COALESCE(?, subgroup)
            WHERE id = ?
        """, (data.get('full_name'), data.get('is_active'), data.get('notes'), data.get('subgroup'), student_id))
        conn.commit()
        return jsonify({'success': True})

@app.route('/students/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        conn.commit()
        return jsonify({'success': True})

@app.route('/attendance', methods=['GET'])
def get_attendance():
    lesson_id = request.args.get('lesson_id')
    if not lesson_id:
        return jsonify({'error': 'lesson_id required'}), 400

    with get_connection() as conn:
        cur = conn.execute("""
            SELECT a.student_id, a.status, a.marked_at, s.full_name
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.lesson_id = ?
        """, (lesson_id,))
        records = [{'student_id': row[0], 'status': row[1], 'marked_at': row[2], 'student_name': row[3]} for row in cur.fetchall()]
        return jsonify(records)

@app.route('/attendance', methods=['POST'])
def set_attendance():
    data = request.json
    lesson_id = data.get('lesson_id')
    student_id = data.get('student_id')
    status = data.get('status')  # может быть null для удаления

    if not lesson_id or not student_id:
        return jsonify({'error': 'lesson_id and student_id required'}), 400

    with get_connection() as conn:
        # Получаем подгруппу занятия
        cur = conn.execute("SELECT podgr FROM lessons WHERE id = ?", (lesson_id,))
        lesson_row = cur.fetchone()
        if not lesson_row:
            return jsonify({'error': 'Lesson not found'}), 404
        lesson_podgr = lesson_row[0] or 0

        # Получаем подгруппу студента
        cur = conn.execute("SELECT subgroup FROM students WHERE id = ?", (student_id,))
        student_row = cur.fetchone()
        if not student_row:
            return jsonify({'error': 'Student not found'}), 404
        student_subgroup = student_row[0] or 0

        # Проверка соответствия подгрупп
        # lesson_podgr: 0 - общее занятие, 1 - первая подгруппа, 2 - вторая подгруппа
        # student_subgroup: 0 - общая группа, 1 - первая подгруппа, 2 - вторая подгруппа
        if lesson_podgr != 0 and student_subgroup != 0 and lesson_podgr != student_subgroup:
            return jsonify({'error': f'Student belongs to subgroup {student_subgroup}, but lesson is for subgroup {lesson_podgr}'}), 400

        if status is None:
            conn.execute("DELETE FROM attendance WHERE lesson_id = ? AND student_id = ?", (lesson_id, student_id))
        else:
            conn.execute("""
                INSERT OR REPLACE INTO attendance (lesson_id, student_id, status, marked_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (lesson_id, student_id, status))
        conn.commit()
        return jsonify({'success': True})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ---------- Запуск ----------
if __name__ == "__main__":
    app.run(debug=True)