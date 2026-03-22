import threading
import time
from flask import Flask, jsonify, request
from db import get_connection, init_db, get_last_processed_file, set_last_processed_file
from update import process_file, full_update

app = Flask(__name__)

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
            SELECT l.date, l.para, l.podgr, l.zam, t.name, d.name, l.room
            FROM lessons l
            JOIN groups g ON l.group_id = g.id
            LEFT JOIN teachers t ON l.teacher_id = t.id
            LEFT JOIN disciplines d ON l.discipline_id = d.id
            WHERE g.code = ? AND l.date = ?
            ORDER BY l.para, l.podgr
        """, (group, date))
        rows = cur.fetchall()
        schedule = []
        for row in rows:
            schedule.append({
                "date": row[0],
                "para": row[1],
                "podgr": row[2],
                "zam": bool(row[3]),   # заменённое занятие?
                "teacher": row[4],
                "discipline": row[5],
                "room": row[6] or ""
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
            SELECT l.date, l.para, l.podgr, l.zam, t.name, d.name, l.room
            FROM lessons l
            JOIN groups g ON l.group_id = g.id
            LEFT JOIN teachers t ON l.teacher_id = t.id
            LEFT JOIN disciplines d ON l.discipline_id = d.id
            WHERE g.code = ? AND l.date IN ({})
            ORDER BY l.date, l.para, l.podgr
        """.format(','.join(['?']*7)), (group, *dates))
        rows = cur.fetchall()

    # Группируем по датам
    schedule_by_day = {d: [] for d in dates}
    for row in rows:
        schedule_by_day[row[0]].append({
            "para": row[1],
            "podgr": row[2],
            "zam": bool(row[3]),
            "teacher": row[4],
            "discipline": row[5],
            "room": row[6] or ""
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

# ---------- Запуск ----------
if __name__ == "__main__":
    app.run(debug=True)