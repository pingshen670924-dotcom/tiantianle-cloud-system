import csv
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from california_fantasy5_system import DB_PATH, init_db, setup_dirs, upsert_draw


def parse_numbers(row):
    values = []
    for key in ["n1", "n2", "n3", "n4", "n5"]:
        if key in row and row[key].strip():
            values.append(int(row[key]))
    if len(values) == 5:
        return values
    joined = " ".join(str(value) for value in row.values())
    numbers = [int(x) for x in re.findall(r"\b\d{1,2}\b", joined)]
    candidates = [n for n in numbers if 1 <= n <= 39]
    return candidates[-5:] if len(candidates) >= 5 else []


def parse_date(row):
    for key in ["draw_date", "date", "Date", "Draw Date"]:
        if key in row and row[key].strip():
            value = row[key].strip()
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"]:
                try:
                    return datetime.strptime(value, fmt).date().isoformat()
                except ValueError:
                    pass
            return value
    return ""


def import_csv(path):
    setup_dirs()
    count = 0
    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                draw_date = parse_date(row)
                numbers = parse_numbers(row)
                if draw_date and len(numbers) == 5:
                    before = conn.total_changes
                    upsert_draw(conn, draw_date, numbers, f"csv_import:{path}")
                    count += 1 if conn.total_changes > before else 0
        conn.commit()
    return count


def main():
    if len(sys.argv) < 2:
        print("usage: python import_history_csv.py history.csv")
        raise SystemExit(2)
    count = import_csv(sys.argv[1])
    print(f"imported: {count}")


if __name__ == "__main__":
    main()
