import sqlite3
import threading
import time
import os
from flask import Flask, jsonify, request, send_file
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from db import add_curator_group, get_available_groups, get_connection, get_curator_groups, get_group_code_by_id, init_db, get_last_processed_file, set_last_processed_file, get_user_by_username, user_has_group_access, remove_curator_groups
from update import process_file, full_update
from flask_cors import CORS
import io
from datetime import datetime
from report_generator import generate_excel_report, generate_pdf_report

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'xUFXVEhR0vRg1ZISBWMVZdnI3E8Vg32Zx8X2bESaVGn')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # отключаем истечение для простоты, но в продакшене лучше установить
jwt = JWTManager(app)
CORS(app, origins=["http://127.0.0.1:5500", "http://localhost:5500", "http://localhost:3000", "http://127.0.0.1:3000"], supports_credentials=True)

# ---------- Фоновое обновление ----------
def incremental_update():
    last = get_last_processed_file()
    next_file = last + 1
    if process_file(next_file):
        set_last_processed_file(next_file)
        print(f"Добавлен новый файл {next_file}.xml")
    else:
        print("Новых файлов нет.")

def refresh_recent():
    last = get_last_processed_file()
    for f in range(max(1, last-1), last+1):
        process_file(f)
    print("Последние файлы обновлены.")

def background_updater():
    if get_last_processed_file() == 0:
        print("Выполняю первичное обновление...")
        full_update()
    while True:
        time.sleep(6 * 3600)
        incremental_update()
        refresh_recent()

thread = threading.Thread(target=background_updater, daemon=True)
thread.start()

# ---------- API ----------
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = get_user_by_username(username)
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({"msg": "Неверное имя или пароль"}), 401
    access_token = create_access_token(identity=str(user['id']))
    return jsonify({
        "access_token": access_token,
        "role": user['role'],
        "group_id": user.get('group_id'),
        "curator_group_id": user.get('curator_group_id')
    })

@app.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    with get_connection() as conn:
        cur = conn.execute("SELECT id, username, role, group_id, curator_group_id FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            return jsonify({
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "group_id": row[3],
                "curator_group_id": row[4]
            })
    return jsonify({"error": "User not found"}), 404

@app.route("/groups", methods=["GET"])
@jwt_required()
def list_groups():
    user_id = int(get_jwt_identity())
    with get_connection() as conn:
        cur = conn.execute("SELECT role, group_id FROM users WHERE id = ?", (user_id,))
        user_row = cur.fetchone()
        if not user_row:
            return jsonify([])
        role = user_row[0]
        groups_data = []

        if role == 'admin':
            cur = conn.execute("SELECT code FROM groups ORDER BY code")
            groups_data = [{"code": row[0], "is_curator": False} for row in cur.fetchall()]
        elif role == 'headman':
            group_id = user_row[1]
            if group_id:
                cur = conn.execute("SELECT code FROM groups WHERE id = ?", (group_id,))
                row = cur.fetchone()
                if row:
                    groups_data = [{"code": row[0], "is_curator": False}]
        elif role == 'curator':
            # курируемые группы
            cur = conn.execute("""
                SELECT g.code FROM user_curator_groups ucg
                JOIN groups g ON ucg.group_id = g.id
                WHERE ucg.user_id = ?
            """, (user_id,))
            curator_codes = [row[0] for row in cur.fetchall()]
            # группы, где преподаватель ведёт занятия
            cur = conn.execute("""
                SELECT DISTINCT g.code FROM lessons l
                JOIN groups g ON l.group_id = g.id
                WHERE l.teacher_id IN (SELECT id FROM teachers WHERE name IN (SELECT full_name FROM users WHERE id = ?))
            """, (user_id,))
            teacher_codes = [row[0] for row in cur.fetchall()]
            all_codes = set(curator_codes + teacher_codes)
            groups_data = [{"code": code, "is_curator": code in curator_codes} for code in all_codes]
        else:  # teacher
            cur = conn.execute("""
                SELECT DISTINCT g.code FROM lessons l
                JOIN groups g ON l.group_id = g.id
                WHERE l.teacher_id IN (SELECT id FROM teachers WHERE name IN (SELECT full_name FROM users WHERE id = ?))
            """, (user_id,))
            groups_data = [{"code": row[0], "is_curator": False} for row in cur.fetchall()]

        return jsonify(groups_data)

@app.route("/schedule", methods=["GET"])
@jwt_required()
def get_schedule():
    group = request.args.get("group")   # может быть None
    date = request.args.get("date")
    if not date:
        return jsonify({"error": "Параметр date обязателен"}), 400

    user_id = int(get_jwt_identity())
    with get_connection() as conn:
        role = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()[0]
        teacher_id = None
        if role in ('teacher', 'curator'):
            full_name = conn.execute("SELECT full_name FROM users WHERE id = ?", (user_id,)).fetchone()[0]
            if full_name:
                row = conn.execute("SELECT id FROM teachers WHERE name = ?", (full_name,)).fetchone()
                if row:
                    teacher_id = row[0]

        # Определяем список групп для отображения
        groups_to_show = []
        if group:
            if not user_has_group_access(user_id, group):
                return jsonify({"error": "Доступ запрещён"}), 403
            groups_to_show = [group]
        else:
            # Все доступные группы
            available = get_available_groups(user_id, role, teacher_id, conn)
            if not available:
                return jsonify([])
            groups_to_show = available

        # Формируем условия
        conditions = ["SUBSTR(l.date, 1, 10) = ?"]
        params = [date]
        conditions.append(f"g.code IN ({','.join(['?']*len(groups_to_show))})")
        params.extend(groups_to_show)

        # Решаем, фильтровать ли по преподавателю
        filter_by_teacher = False
        if role == 'teacher':
            filter_by_teacher = True
        elif role == 'curator' and group:
            # Если выбрана конкретная группа и она не курируется
            cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group,))
            group_row = cur.fetchone()
            if group_row:
                group_id_db = group_row[0]
                cur = conn.execute("SELECT 1 FROM user_curator_groups WHERE user_id = ? AND group_id = ?", (user_id, group_id_db))
                if not cur.fetchone():
                    filter_by_teacher = True
        elif role == 'curator' and not group:
            # Без выбранной группы куратор видит только свои занятия
            filter_by_teacher = True

        if filter_by_teacher and teacher_id:
            conditions.append("l.teacher_id = ?")
            params.append(teacher_id)

        query = f"""
            SELECT l.id, l.date, l.para, l.podgr, l.zam, t.name, d.name, l.room, g.code
            FROM lessons l
            JOIN groups g ON l.group_id = g.id
            LEFT JOIN teachers t ON l.teacher_id = t.id
            LEFT JOIN disciplines d ON l.discipline_id = d.id
            WHERE {' AND '.join(conditions)}
            ORDER BY l.para, l.podgr
        """
        rows = conn.execute(query, params).fetchall()
        schedule = []
        for row in rows:
            schedule.append({
                "id": row[0],
                "date": row[1],
                "para": row[2],
                "podgr": row[3],
                "zam": bool(row[4]),
                "teacher": row[5] or "",
                "discipline": row[6] or "",
                "room": row[7] or "",
                "group_code": row[8]
            })
        return jsonify(schedule)

@app.route("/schedule/week", methods=["GET"])
@jwt_required()
def get_week_schedule():
    group = request.args.get("group")          # может быть None
    week_start = request.args.get("week_start")
    if not week_start:
        return jsonify({"error": "Параметр week_start обязателен"}), 400

    user_id = int(get_jwt_identity())

    from datetime import datetime, timedelta
    try:
        start_date = datetime.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "week_start должен быть в формате YYYY-MM-DD"}), 400

    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    with get_connection() as conn:
        # 1. Роль пользователя
        cur = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        role = cur.fetchone()[0]

        # 2. Для ролей teacher/curator – получаем teacher_id
        teacher_id = None
        if role in ('teacher', 'curator'):
            cur = conn.execute("SELECT full_name FROM users WHERE id = ?", (user_id,))
            full_name = cur.fetchone()[0]
            if full_name:
                cur = conn.execute("SELECT id FROM teachers WHERE name = ?", (full_name,))
                row = cur.fetchone()
                if row:
                    teacher_id = row[0]

        # 3. Формируем условия WHERE
        conditions = []
        params = []

        # Даты
        conditions.append(f"SUBSTR(l.date,1,10) IN ({','.join(['?']*len(dates))})")
        params.extend(dates)

        # Группа (если указана)
        if group:
            if not user_has_group_access(user_id, group):
                return jsonify({"error": "Доступ запрещён"}), 403
            conditions.append("g.code = ?")
            params.append(group)
        else:
            # Если группа не указана, получаем список доступных групп
            available_groups = get_available_groups(user_id, role, teacher_id, conn)
            if not available_groups:
                return jsonify({d: [] for d in dates})
            conditions.append(f"g.code IN ({','.join(['?']*len(available_groups))})")
            params.extend(available_groups)

        # 4. Фильтр по преподавателю (для teacher и curator без кураторства)
        if role == 'teacher':
            if teacher_id:
                conditions.append("l.teacher_id = ?")
                params.append(teacher_id)
            else:
                return jsonify({d: [] for d in dates})
        elif role == 'curator' and group:
            # Если группа указана и она НЕ курируется, показываем только свои занятия
            cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group,))
            group_row = cur.fetchone()
            if group_row:
                group_id_db = group_row[0]
                cur = conn.execute("SELECT 1 FROM user_curator_groups WHERE user_id = ? AND group_id = ?", (user_id, group_id_db))
                if not cur.fetchone():
                    if teacher_id:
                        conditions.append("l.teacher_id = ?")
                        params.append(teacher_id)
        elif role == 'curator' and not group:
            # Без выбранной группы куратор видит только свои занятия
            if teacher_id:
                conditions.append("l.teacher_id = ?")
                params.append(teacher_id)

        # 5. Запрос
        query = f"""
            SELECT l.id, l.date, l.para, l.podgr, l.zam, t.name, d.name, l.room
            FROM lessons l
            JOIN groups g ON l.group_id = g.id
            LEFT JOIN teachers t ON l.teacher_id = t.id
            LEFT JOIN disciplines d ON l.discipline_id = d.id
            WHERE {' AND '.join(conditions)}
            ORDER BY l.date, l.para, l.podgr
        """
        cur = conn.execute(query, params)
        rows = cur.fetchall()

        # 6. Группировка по дням
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

@app.route('/students', methods=['GET'])
@jwt_required()
def get_students():
    group_code = request.args.get('group')
    if not group_code:
        return jsonify({'error': 'group param required'}), 400

    user_id = get_jwt_identity()
    if not user_has_group_access(user_id, group_code):
        return jsonify({'error': 'Доступ запрещён'}), 403

    with get_connection() as conn:
        cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group_code,))
        group_row = cur.fetchone()
        if not group_row:
            return jsonify([])

        cur = conn.execute("""
            SELECT id, full_name, is_active, notes, subgroup
            FROM students
            WHERE group_id = ?
            ORDER BY full_name
        """, (group_row[0],))
        students = [{'id': row[0], 'full_name': row[1], 'is_active': bool(row[2]), 'notes': row[3], 'subgroup': row[4]} for row in cur.fetchall()]
        return jsonify(students)

@app.route('/students', methods=['POST'])
@jwt_required()
def add_student():
    data = request.json
    group_code = data.get('group')
    full_name = data.get('full_name')
    if not group_code or not full_name:
        return jsonify({'error': 'group and full_name required'}), 400

    user_id = int(get_jwt_identity())
    if not user_has_group_access(user_id, group_code):
        return jsonify({'error': 'Доступ запрещён'}), 403

    with get_connection() as conn:
        cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group_code,))
        group_row = cur.fetchone()
        if not group_row:
            return jsonify({'error': 'Group not found'}), 404

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
@jwt_required()
def update_student(student_id):
    data = request.json
    with get_connection() as conn:
        cur = conn.execute("SELECT g.code FROM students s JOIN groups g ON s.group_id = g.id WHERE s.id = ?", (student_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Student not found'}), 404
        group_code = row[0]
        user_id = int(get_jwt_identity())
        if not user_has_group_access(user_id, group_code):
            return jsonify({'error': 'Доступ запрещён'}), 403

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
@jwt_required()
def delete_student(student_id):
    with get_connection() as conn:
        cur = conn.execute("SELECT g.code FROM students s JOIN groups g ON s.group_id = g.id WHERE s.id = ?", (student_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Student not found'}), 404
        group_code = row[0]
        user_id = int(get_jwt_identity())
        if not user_has_group_access(user_id, group_code):
            return jsonify({'error': 'Доступ запрещён'}), 403

        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        conn.commit()
        return jsonify({'success': True})

@app.route('/attendance', methods=['GET'])
@jwt_required()
def get_attendance():
    lesson_id = request.args.get('lesson_id')
    if not lesson_id:
        return jsonify({'error': 'lesson_id required'}), 400

    with get_connection() as conn:
        cur = conn.execute("SELECT g.code FROM lessons l JOIN groups g ON l.group_id = g.id WHERE l.id = ?", (lesson_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Lesson not found'}), 404
        group_code = row[0]
        user_id = int(get_jwt_identity())
        if not user_has_group_access(user_id, group_code):
            return jsonify({'error': 'Доступ запрещён'}), 403

        cur = conn.execute("""
            SELECT a.student_id, a.status, a.marked_at, s.full_name
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.lesson_id = ?
        """, (lesson_id,))
        records = [{'student_id': row[0], 'status': row[1], 'marked_at': row[2], 'student_name': row[3]} for row in cur.fetchall()]
        return jsonify(records)

@app.route('/attendance', methods=['POST'])
@jwt_required()
def set_attendance():
    data = request.json
    lesson_id = data.get('lesson_id')
    student_id = data.get('student_id')
    status = data.get('status')
    user_id = int(get_jwt_identity())

    if not lesson_id or not student_id:
        return jsonify({'error': 'lesson_id and student_id required'}), 400

    with get_connection() as conn:
        # Получаем роль пользователя
        cur = conn.execute("SELECT role, group_id, curator_group_id FROM users WHERE id = ?", (user_id,))
        user_row = cur.fetchone()
        if not user_row:
            return jsonify({'error': 'User not found'}), 404
        role = user_row[0]

        # Получаем информацию о занятии
        cur = conn.execute("SELECT podgr, teacher_id, group_id FROM lessons WHERE id = ?", (lesson_id,))
        lesson = cur.fetchone()
        if not lesson:
            return jsonify({'error': 'Lesson not found'}), 404
        lesson_podgr = lesson[0] or 0
        lesson_teacher_id = lesson[1]
        lesson_group_id = lesson[2]

        # Получаем студента и его группу
        cur = conn.execute("""
            SELECT s.id, s.subgroup, s.group_id, g.code
            FROM students s
            JOIN groups g ON s.group_id = g.id
            WHERE s.id = ?
        """, (student_id,))
        student_row = cur.fetchone()
        if not student_row:
            return jsonify({'error': 'Student not found'}), 404
        student_subgroup = student_row[1] or 0
        student_group_id = student_row[2]
        group_code = student_row[3]

        # Проверка подгрупп
        if lesson_podgr != 0 and student_subgroup != 0 and lesson_podgr != student_subgroup:
            return jsonify({'error': f'Student belongs to subgroup {student_subgroup}, but lesson is for subgroup {lesson_podgr}'}), 400

        # Проверка прав на редактирование
        can_edit = False
        if role == 'admin':
            can_edit = True
        elif role == 'teacher':
            # преподаватель может отмечать только на своих занятиях
            cur = conn.execute("SELECT id FROM teachers WHERE name IN (SELECT full_name FROM users WHERE id = ?)", (user_id,))
            teacher_row = cur.fetchone()
            if teacher_row and teacher_row[0] == lesson_teacher_id:
                can_edit = True
        elif role == 'curator':
            # куратор: может отмечать на своих занятиях (как преподаватель)
            cur = conn.execute("SELECT id FROM teachers WHERE name IN (SELECT full_name FROM users WHERE id = ?)", (user_id,))
            teacher_row = cur.fetchone()
            if teacher_row and teacher_row[0] == lesson_teacher_id:
                can_edit = True
        elif role == 'headman':
            # староста может отмечать на любых занятиях своей группы
            headman_group_id = user_row[1]
            if headman_group_id == student_group_id:
                # Проверяем, нет ли уже отметки от преподавателя/куратора
                cur = conn.execute("SELECT status, marked_by FROM attendance WHERE lesson_id = ? AND student_id = ?", (lesson_id, student_id))
                existing = cur.fetchone()
                if existing and existing[1]:
                    cur2 = conn.execute("SELECT role FROM users WHERE id = ?", (existing[1],))
                    marker_role = cur2.fetchone()
                    if marker_role and marker_role[0] in ('teacher', 'curator'):
                        return jsonify({'error': 'Cannot override teacher/curator mark'}), 403
                can_edit = True

        if not can_edit:
            return jsonify({'error': 'Permission denied'}), 403

        # Обновление или удаление
        if status is None:
            conn.execute("DELETE FROM attendance WHERE lesson_id = ? AND student_id = ?", (lesson_id, student_id))
        else:
            conn.execute("""
                INSERT OR REPLACE INTO attendance (lesson_id, student_id, status, marked_by, marked_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (lesson_id, student_id, status, user_id))
        conn.commit()
        return jsonify({'success': True})

@app.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    user_id = int(get_jwt_identity())
    with get_connection() as conn:
        cur = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        role = cur.fetchone()[0]
        if role != 'admin':
            return jsonify({'error': 'Forbidden'}), 403

        cur = conn.execute("SELECT id, username, full_name, role, group_id FROM users")
        users = []
        for row in cur.fetchall():
            uid = row[0]
            username = row[1]
            full_name = row[2]
            user_role = row[3]
            group_id = row[4]  # id группы в БД
            group_code = get_group_code_by_id(group_id) if group_id else None

            curator_group_ids = []
            if user_role == 'curator':
                cur_g = conn.execute("SELECT group_id FROM user_curator_groups WHERE user_id = ?", (uid,))
                curator_group_ids = [get_group_code_by_id(gid) for gid, in cur_g.fetchall()]

            users.append({
                'id': uid,
                'username': username,
                'full_name': full_name,
                'role': user_role,
                'group_id': group_code,               # теперь код, а не id
                'curator_group_ids': curator_group_ids
            })
        return jsonify(users)
    
@app.route('/users', methods=['POST'])
@jwt_required()
def create_user():
    # Только админ может создавать пользователей
    current_user_id = int(get_jwt_identity())
    with get_connection() as conn:
        cur = conn.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        if cur.fetchone()[0] != 'admin':
            return jsonify({'error': 'Forbidden'}), 403

        data = request.json
        username = data.get('username')
        password = data.get('password')
        full_name = data.get('full_name')
        role = data.get('role')
        group_code = data.get('group_id')          # код группы для старосты
        curator_group_codes = data.get('curator_group_ids', [])  # список кодов для куратора

        if not username or not password:
            return jsonify({'error': 'username and password required'}), 400

        # Хэшируем пароль
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(password)

        # Преобразуем код группы в id (если задан)
        group_id = None
        if group_code:
            cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group_code,))
            row = cur.fetchone()
            if row:
                group_id = row[0]
            else:
                return jsonify({'error': f'Group {group_code} not found'}), 400

        try:
            # Вставляем пользователя
            cur = conn.execute("""
                INSERT INTO users (username, password_hash, full_name, role, group_id)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
            """, (username, password_hash, full_name, role, group_id))
            user_id = cur.fetchone()[0]

            # Если роль куратор, добавляем кураторские группы
            if role == 'curator':
                for group_code in curator_group_codes:
                    if group_code:
                        cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group_code,))
                        row = cur.fetchone()
                        if row:
                            add_curator_group(user_id, row[0], conn=conn) 

                        conn.commit()
                        return jsonify({'success': True, 'id': user_id}), 201

        except sqlite3.IntegrityError:
            return jsonify({'error': 'Username already exists'}), 400

@app.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    current_user_id = int(get_jwt_identity())
    with get_connection() as conn:
        cur = conn.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        if cur.fetchone()[0] != 'admin':
            return jsonify({'error': 'Forbidden'}), 403

        data = request.json
        updates = []
        params = []

        if 'full_name' in data:
            updates.append("full_name = ?")
            params.append(data['full_name'])
        if 'role' in data:
            updates.append("role = ?")
            params.append(data['role'])
        if 'group_id' in data:
            group_code = data['group_id']
            group_id = None
            if group_code:
                cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group_code,))
                row = cur.fetchone()
                if row:
                    group_id = row[0]
            updates.append("group_id = ?")
            params.append(group_id)
        if 'curator_group_ids' in data and data['role'] == 'curator':
            # Для куратора обновляем список кураторских групп
            remove_curator_groups(user_id, conn=conn)
            for group_code in data['curator_group_ids']:
                if group_code:
                    cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group_code,))
                    row = cur.fetchone()
                    if row:
                        add_curator_group(user_id, row[0], conn=conn)
        if 'password' in data and data['password']:
            from werkzeug.security import generate_password_hash
            updates.append("password_hash = ?")
            params.append(generate_password_hash(data['password']))

        if updates:
            params.append(user_id)
            conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

        # Возвращаем обновлённые данные пользователя
        cur = conn.execute("SELECT id, username, full_name, role, group_id FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'User not found'}), 404

        user_data = {
            'id': row[0],
            'username': row[1],
            'full_name': row[2],
            'role': row[3],
            'group_id': get_group_code_by_id(row[4]) if row[4] else None,
        }
        if row[3] == 'curator':
            curator_group_ids = get_curator_groups(user_id)
            user_data['curator_group_ids'] = [get_group_code_by_id(gid) for gid in curator_group_ids]
        else:
            user_data['curator_group_ids'] = []

        return jsonify(user_data)

@app.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    current_user_id = int(get_jwt_identity())
    with get_connection() as conn:
        cur = conn.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        if cur.fetchone()[0] != 'admin':
            return jsonify({'error': 'Forbidden'}), 403
        # Нельзя удалить самого себя
        if user_id == current_user_id:
            return jsonify({'error': 'Cannot delete yourself'}), 400

        conn.execute("DELETE FROM user_curator_groups WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return jsonify({'success': True})
    
@app.route('/report', methods=['GET'])
@jwt_required()
def generate_report():
    group_code = request.args.get('group_code')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    fmt = request.args.get('format', 'xlsx').lower()
    if not group_code or not start_date or not end_date:
        return jsonify({'error': 'group_code, start_date, end_date required'}), 400

    try:
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    user_id = int(get_jwt_identity())
    with get_connection() as conn:
        cur = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        role = cur.fetchone()[0]
        if role not in ('headman', 'curator'):
            return jsonify({'error': 'Only headman and curator can generate reports'}), 403

        if not user_has_group_access(user_id, group_code):
            return jsonify({'error': 'Access denied to this group'}), 403

        # Получаем group_id
        cur = conn.execute("SELECT id FROM groups WHERE code = ?", (group_code,))
        group_row = cur.fetchone()
        if not group_row:
            return jsonify({'error': 'Group not found'}), 404
        group_id = group_row[0]

        # Получаем активных студентов с подгруппами
        cur = conn.execute("""
            SELECT id, full_name, subgroup
            FROM students
            WHERE group_id = ? AND is_active = 1
            ORDER BY full_name
        """, (group_id,))
        students = [{'id': row[0], 'full_name': row[1], 'subgroup': row[2] or 0} for row in cur.fetchall()]

        if not students:
            student_data = []
            total_lessons_count = 0
            total_students_count = 0
            total_present = total_late = total_excused = total_absent = 0
            total_possible = 0
        else:
            # Получаем все уроки за период
            cur = conn.execute("""
                SELECT id, date, para, podgr, teacher_id, discipline_id, room
                FROM lessons
                WHERE group_id = ? AND DATE(date) BETWEEN ? AND ?
                ORDER BY date, para, podgr
            """, (group_id, start_date, end_date))
            lessons = cur.fetchall()

            # Группируем уроки в логические занятия по ключу (date, para, discipline_id)
            # Но нужно учитывать, что discipline_id может быть None? Обычно есть. Если None, то тоже группируем.
            logical_lessons = {}  # key -> {'ids': [], 'podgr_set': set(), 'date':..., 'para':..., 'discipline_id':...}
            lesson_to_key = {}
            for row in lessons:
                key = (row['date'][:10], row['para'], row['discipline_id'])
                if key not in logical_lessons:
                    logical_lessons[key] = {
                        'ids': [],
                        'podgr_set': set(),
                        'date': row['date'],
                        'para': row['para'],
                        'discipline_id': row['discipline_id']
                    }
                logical_lessons[key]['ids'].append(row['id'])
                podgr = row['podgr'] if row['podgr'] is not None else 0
                logical_lessons[key]['podgr_set'].add(podgr)
                lesson_to_key[row['id']] = key

            total_lessons_count = len(logical_lessons)
            total_students_count = len(students)

            # Получаем все записи посещаемости для этих уроков
            all_lesson_ids = [lid for group in logical_lessons.values() for lid in group['ids']]
            attendance_records = []
            if all_lesson_ids:
                placeholders = ','.join('?' for _ in all_lesson_ids)
                cur = conn.execute(f"""
                    SELECT lesson_id, student_id, status
                    FROM attendance
                    WHERE lesson_id IN ({placeholders})
                """, all_lesson_ids)
                attendance_records = cur.fetchall()

            # Для каждого студента и логического занятия определим лучший статус
            status_priority = {'present': 4, 'late': 3, 'excused': 2, 'absent': 1}
            attendance_map = {}  # (student_id, logical_key) -> priority
            for lesson_id, student_id, status in attendance_records:
                logical_key = lesson_to_key.get(lesson_id)
                if logical_key:
                    key = (student_id, logical_key)
                    priority = status_priority.get(status, 0)
                    if priority > attendance_map.get(key, 0):
                        attendance_map[key] = priority

            # Для каждого студента считаем статистику
            student_data = []
            total_present = total_late = total_excused = total_absent = 0
            total_possible = 0

            for student in students:
                student_id = student['id']
                student_subgroup = student['subgroup']
                present = late = excused = absent = 0
                lessons_for_student = 0

                for key, logical in logical_lessons.items():
                    podgr_set = logical['podgr_set']
                    # Определяем, участвует ли студент в этом логическом занятии
                    participates = False
                    if 0 in podgr_set:
                        # Общее занятие для всей группы
                        participates = True
                    else:
                        # Занятия по подгруппам
                        if student_subgroup != 0 and student_subgroup in podgr_set:
                            participates = True
                        # Если подгруппа студента 0, но занятие только для подгрупп, то не участвует
                        # Также может быть ситуация, когда podgr_set пуст? Не должно быть, но на всякий случай.
                    if not participates:
                        continue

                    lessons_for_student += 1
                    status_priority_val = attendance_map.get((student_id, key), 0)
                    if status_priority_val == 4:
                        present += 1
                    elif status_priority_val == 3:
                        late += 1
                    elif status_priority_val == 2:
                        excused += 1
                    else:
                        absent += 1

                attended = present + late
                percent = (attended * 100 / lessons_for_student) if lessons_for_student else 0

                student_data.append({
                    'full_name': student['full_name'],
                    'subgroup': 'Общая' if student_subgroup == 0 else f"{student_subgroup}-я подгр.",
                    'present': present,
                    'late': late,
                    'excused': excused,
                    'absent': absent,
                    'total': lessons_for_student,
                    'total_hours': lessons_for_student * 2,
                    'attended': attended,
                    'attended_hours': attended * 2,
                    'percent': round(percent, 1)
                })

                total_present += present
                total_late += late
                total_excused += excused
                total_absent += absent
                total_possible += lessons_for_student

            # Здесь total_possible — сумма по студентам количества логических занятий, в которых они участвуют

    # Генерация отчета
    try:
        if fmt == 'xlsx':
            excel_data = generate_excel_report(
                student_data, group_code, start_date, end_date,
                total_lessons_count, total_students_count,
                total_present, total_late, total_excused, total_absent,
                total_possible, total_possible  # max_possible = total_possible
            )
            filename = f"report_{group_code}_{start_date}_{end_date}.xlsx"
            return send_file(excel_data, download_name=filename, as_attachment=True,
                             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        elif fmt == 'pdf':
            pdf_data = generate_pdf_report(
                student_data, group_code, start_date, end_date,
                total_lessons_count, total_students_count,
                total_present, total_late, total_excused, total_absent,
                total_possible, total_possible
            )
            filename = f"report_{group_code}_{start_date}_{end_date}.pdf"
            return send_file(pdf_data, download_name=filename, as_attachment=True,
                             mimetype='application/pdf')
        else:
            return jsonify({'error': 'Format must be xlsx or pdf'}), 400
    except Exception as e:
        app.logger.error(f"Report generation error: {e}")
        return jsonify({'error': f'Ошибка генерации отчета: {str(e)}'}), 500
    
# В конце оставляем CORS и запуск
if __name__ == "__main__":
    init_db()
    app.run(debug=True)