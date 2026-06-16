# fantasy5_full_history_tool_v3.py
# California Fantasy 5 full-history scraper V3
# Main source: Lotto-8 paged archive
# Backup source: Lottolyzer first summary page
# Output: fantasy5_full_history.csv
#
# Fixed:
# - Correct Lotto-8 parser for:
#   10/05
#   26(SUN) 09, 11, 17, 25, 29
# - Correct Lottolyzer parser for:
#   11873 2026-05-10 9,11,17,25,29
# - No Chinese BAT corruption
# - No infinite official 403 loop
# - Saves debug HTML/text when parsing fails

import csv
import re
import sys
import time
import random
from datetime import datetime
from pathlib import Path

try:
    import requests
except Exception:
    print("[ERROR] requests is missing. Run install_dependencies.bat first.")
    input("Press Enter to exit...")
    sys.exit(1)

OUT_CSV = Path("fantasy5_full_history.csv")
LOG_TXT = Path("scraper_log.txt")
DEBUG_DIR = Path("debug_pages")
DEBUG_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
    "Referer": "https://www.google.com/",
}

session = requests.Session()
session.headers.update(HEADERS)


def log(msg):
    print(msg)
    with LOG_TXT.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def fetch(url, name, timeout=30):
    try:
        r = session.get(url, timeout=timeout)
        log(f"[FETCH] {name} HTTP {r.status_code} {url}")
        # Force best guess text decode.
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding or "utf-8"
        text = r.text
        DEBUG_DIR.joinpath(f"{name}.html").write_text(text, encoding="utf-8", errors="ignore")
        if r.status_code != 200:
            return ""
        return text
    except Exception as e:
        log(f"[ERROR] fetch failed: {url} -> {e}")
        return ""


def clean_text(html):
    text = html
    text = text.replace("&nbsp;", " ")
    text = text.replace("\xa0", " ")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</tr>|</p>|</li>|</div>|</td>|</span>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*", "\n", text)
    return text


def parse_nums(s):
    nums = [int(x) for x in re.findall(r"\d{1,2}", s)]
    if len(nums) < 5:
        return None
    nums = nums[:5]
    if len(nums) == 5 and len(set(nums)) == 5 and all(1 <= n <= 39 for n in nums):
        return nums
    return None


def parse_lotto8_page(html, page_no):
    """
    Real visible format from Lotto-8:
    10/05
    26(SUN) 09, 11, 17, 25, 29
    """
    text = clean_text(html)
    DEBUG_DIR.joinpath(f"lotto8_page_{page_no}_text.txt").write_text(text[:20000], encoding="utf-8", errors="ignore")

    rows = []

    # Pattern A: line break format.
    pat = re.compile(
        r"(?P<day>\d{2})/(?P<month>\d{2})\s+"
        r"(?P<yy>\d{2})\([A-Z]{3}\)\s+"
        r"(?P<nums>\d{1,2}\s*,\s*\d{1,2}\s*,\s*\d{1,2}\s*,\s*\d{1,2}\s*,\s*\d{1,2})",
        flags=re.I
    )

    for m in pat.finditer(text):
        yy = int(m.group("yy"))
        year = 2000 + yy if yy <= 80 else 1900 + yy
        month = int(m.group("month"))
        day = int(m.group("day"))
        try:
            draw_date = datetime(year, month, day).strftime("%Y-%m-%d")
        except Exception:
            continue
        nums = parse_nums(m.group("nums"))
        if not nums:
            continue
        rows.append({
            "draw_date": draw_date,
            "draw_no": "",
            "n1": nums[0],
            "n2": nums[1],
            "n3": nums[2],
            "n4": nums[3],
            "n5": nums[4],
            "source": "lotto8",
        })

    return rows


def parse_lottolyzer(html):
    """
    Real visible format from Lottolyzer:
    11873 2026-05-10 9,11,17,25,29 ...
    """
    text = clean_text(html)
    DEBUG_DIR.joinpath("lottolyzer_text.txt").write_text(text[:20000], encoding="utf-8", errors="ignore")
    rows = []

    pat = re.compile(
        r"\b(?P<draw>\d{4,6})\s+"
        r"(?P<date>(?:19|20)\d{2}-\d{2}-\d{2})\s+"
        r"(?P<nums>\d{1,2},\d{1,2},\d{1,2},\d{1,2},\d{1,2})\b"
    )

    for m in pat.finditer(text):
        nums = parse_nums(m.group("nums"))
        if not nums:
            continue
        rows.append({
            "draw_date": m.group("date"),
            "draw_no": int(m.group("draw")),
            "n1": nums[0],
            "n2": nums[1],
            "n3": nums[2],
            "n4": nums[3],
            "n5": nums[4],
            "source": "lottolyzer",
        })
    return rows


def scrape_lotto8(max_pages=394):
    all_rows = []
    empty_streak = 0

    for page in range(1, max_pages + 1):
        url = f"https://www.lotto-8.com/usa/listltoFT5.asp?indexpage={page}&orderby=new"
        html = fetch(url, f"lotto8_page_{page}")
        rows = parse_lotto8_page(html, page)

        if rows:
            all_rows.extend(rows)
            empty_streak = 0
            log(f"[LOTTO8] page {page}: {len(rows)} rows, total={len(all_rows)}")
        else:
            empty_streak += 1
            log(f"[LOTTO8] page {page}: 0 rows")
            if page <= 3:
                log("[DEBUG] First 1000 chars of text:")
                log(clean_text(html)[:1000])
            if empty_streak >= 8 and page > 10:
                break

        time.sleep(0.10 + random.random() * 0.25)

    return all_rows


def scrape_lottolyzer_first_page():
    url = "https://en.lottolyzer.com/history/united-states/fantasy-5-california/"
    html = fetch(url, "lottolyzer_first_page")
    rows = parse_lottolyzer(html)
    log(f"[LOTTOLYZER] first page rows: {len(rows)}")
    return rows


def merge_rows(rows):
    by_date = {}
    for r in rows:
        key = r["draw_date"]
        if key not in by_date:
            by_date[key] = dict(r)
        else:
            # Prefer source with draw_no
            if not by_date[key].get("draw_no") and r.get("draw_no"):
                old_source = by_date[key].get("source", "")
                by_date[key] = dict(r)
                by_date[key]["source"] = old_source + "+" + r.get("source", "")
            elif r.get("source") not in by_date[key].get("source", ""):
                by_date[key]["source"] += "+" + r.get("source", "")

    out = list(by_date.values())
    out.sort(key=lambda x: x["draw_date"])

    # Add sequential index and fill missing draw_no with index.
    for idx, r in enumerate(out, start=1):
        r["local_index"] = idx
        if not r.get("draw_no"):
            r["draw_no"] = idx

    return out


def validate(rows):
    issues = []
    gaps = []

    for r in rows:
        nums = [int(r[f"n{i}"]) for i in range(1, 6)]
        if len(nums) != 5 or len(set(nums)) != 5 or not all(1 <= n <= 39 for n in nums):
            issues.append(f"bad row: {r}")

    dates = []
    for r in rows:
        try:
            dates.append(datetime.strptime(r["draw_date"], "%Y-%m-%d"))
        except Exception:
            issues.append(f"bad date: {r}")

    for a, b in zip(dates, dates[1:]):
        d = (b - a).days
        if d > 3:
            gaps.append((a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d"), d))

    return issues, gaps


def write_csv(rows):
    fields = ["local_index", "draw_no", "draw_date", "n1", "n2", "n3", "n4", "n5", "source"]
    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def parser_self_test():
    sample_lotto8 = """
    Date California Fantasy 5
    Winning Numbers
    10/05
    26(SUN) 09, 11, 17, 25, 29
    09/05
    26(SAT) 04, 11, 12, 28, 35
    """
    sample_lotto = parse_lotto8_page(sample_lotto8, "selftest")
    if len(sample_lotto) != 2:
        raise RuntimeError("Lotto-8 parser self-test failed")

    sample_lottolyzer = """
    11873 2026-05-10 9,11,17,25,29  11 91
    11872 2026-05-09 4,11,12,28,35  12 90
    """
    sample_lyz = parse_lottolyzer(sample_lottolyzer)
    if len(sample_lyz) != 2:
        raise RuntimeError("Lottolyzer parser self-test failed")

    log("[SELFTEST] parsers OK")


def main():
    if LOG_TXT.exists():
        LOG_TXT.unlink()

    log("=" * 72)
    log("California Fantasy 5 Full History Scraper V3")
    log("Lotto-8 full pages + Lottolyzer first-page cross-check")
    log("=" * 72)

    try:
        parser_self_test()
    except Exception as e:
        log(f"[FATAL] {e}")
        input("Press Enter to exit...")
        return

    rows = []
    rows.extend(scrape_lotto8(max_pages=394))
    rows.extend(scrape_lottolyzer_first_page())

    merged = merge_rows(rows)
    issues, gaps = validate(merged)
    write_csv(merged)

    log("=" * 72)
    log(f"DONE: {OUT_CSV.resolve()}")
    log(f"Total unique draw dates: {len(merged)}")

    if merged:
        log(f"Date range: {merged[0]['draw_date']} -> {merged[-1]['draw_date']}")
        log(f"Latest: draw_no={merged[-1]['draw_no']}, date={merged[-1]['draw_date']}, "
            f"numbers={merged[-1]['n1']},{merged[-1]['n2']},{merged[-1]['n3']},{merged[-1]['n4']},{merged[-1]['n5']}")

    log(f"Validation issues: {len(issues)}")
    for x in issues[:30]:
        log("[ISSUE] " + x)

    log(f"Date gaps over 3 days: {len(gaps)}")
    for g in gaps[:50]:
        log("[GAP] " + str(g))

    if len(merged) == 0:
        log("[IMPORTANT] 0 rows means your network received a blocked/changed page.")
        log("[IMPORTANT] Open debug_pages/lotto8_page_1_text.txt and send me its first 30 lines.")
    elif len(merged) < 10000:
        log("[WARN] Rows are below expected full-history count. Check scraper_log.txt and debug_pages.")
    else:
        log("[OK] Full-history-sized dataset created.")

    log("=" * 72)
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
