import requests
import xml.etree.ElementTree as ET

BASE_URL = "https://polytech-shedule.ru/data/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def parse_schedule_file(file_num):
    url = f"{BASE_URL}{file_num}.xml"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except Exception as e:
        print(f"Ошибка загрузки {url}: {e}")
        return None

    root = ET.fromstring(resp.content)
    # Проверяем наличие элементов My
    my_elements = root.findall("My")
    if not my_elements:
        return None   # это не файл расписания

    lessons = []
    for my in my_elements:
        lesson = {
            "id": my.findtext("ID") or "",           # ID может быть строкой
            "date": my.findtext("DAT") or "",
            "para": my.findtext("UR") or "0",
            "podgr": my.findtext("IDGG") or "0",
            "prepod": my.findtext("FAMIO") or "",
            "disc": my.findtext("SPPRED.NAIM") or "",
            "group": my.findtext("SPGRUP.NAIM") or "",
            "zam": my.findtext("ZAM") or "0",
            "file_num": file_num
        }
        # Безопасное преобразование числовых полей
        try:
            lesson["para"] = int(lesson["para"])
        except ValueError:
            lesson["para"] = 0
        try:
            lesson["podgr"] = int(lesson["podgr"])
        except ValueError:
            lesson["podgr"] = 0
        try:
            lesson["zam"] = int(lesson["zam"])
        except ValueError:
            lesson["zam"] = 0
        lessons.append(lesson)
    return lessons