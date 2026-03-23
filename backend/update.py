import time
from parser import parse_schedule_file
from db import (init_db, upsert_group, upsert_teacher, upsert_discipline,
                insert_lesson, set_last_processed_file)

def process_file(file_num):
    lessons = parse_schedule_file(file_num)
    if lessons is None:
        return False
    for l in lessons:
        group_id = upsert_group(l["group"])
        teacher_id = upsert_teacher(l["prepod"])
        disc_id = upsert_discipline(l["disc"])
        l["group_id"] = group_id
        l["teacher_id"] = teacher_id
        l["discipline_id"] = disc_id
        l["room"] = ""
        insert_lesson(l)
    return True

def full_update():
    file_num = 1
    last_valid = 0
    consecutive_missing = 0
    # Перебираем, пока не встретим 10 подряд пустых
    while consecutive_missing < 10:
        print(f"Обработка {file_num}.xml...")
        if not process_file(file_num):
            consecutive_missing += 1
            print(f"  Файл не найден или не содержит расписания")
        else:
            consecutive_missing = 0
            last_valid = file_num
            print(f"  Загружено занятий")
        file_num += 1
        time.sleep(0.5)

    set_last_processed_file(last_valid)
    print(f"Полное обновление завершено. Последний файл: {last_valid}")

if __name__ == "__main__":
    init_db()
    full_update()