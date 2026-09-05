#!/usr/bin/env python3
"""浜名湖公式データ取得・正規化。

方針:
- 浜名湖(06)のみ
- 1レースずつ取得
- 公式ページから取得できない値を推測しない
- 同じ艇の複数HTML断片は必ずマージする
- モーター情報は登録番号だけに依存せず、選手名でも照合する
"""
from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE = "https://www.boatrace.jp/owpc/pc/race"
VENUE = "06"
BOATS = (1, 2, 3, 4, 5, 6)


def norm(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value or ""))


def compact(value: str) -> str:
    return re.sub(r"\s+", "", norm(value))


def is_japanese_name(value: str) -> bool:
    value = compact(value)
    return bool(re.fullmatch(r"[一-龥々ぁ-んァ-ヶー]{2,12}", value))


def fetch(url: str, timeout: int = 20, retries: int = 2) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        "Referer": "https://www.boatrace.jp/",
    }
    last = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8", "ignore")
            if len(body) < 1000:
                raise RuntimeError("official page response was unexpectedly short")
            return body
        except Exception as exc:
            last = exc
            if attempt < retries:
                time.sleep(0.7 * (attempt + 1))
    raise last


def row_cells(row):
    return [norm(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]


def boat_no_from_text(text: str):
    text = norm(text).strip()
    m = re.match(r"^([1-6])(?:\D|$)", text)
    if m:
        return int(m.group(1))
    return None


def boat_no_from_row(row):
    for cell in row.find_all(["th", "td"]):
        n = boat_no_from_text(cell.get_text(" ", strip=True))
        if n:
            return n
    # Some variants use full-width lane numbers.
    text = norm(row.get_text(" ", strip=True))
    m = re.search(r"(?:^|\s)([1-6])\s+(?:\d{4}\s*/\s*[ABC][123])", text)
    return int(m.group(1)) if m else None


def name_from_row(row):
    # Official site normally exposes the racer name as an <a>.
    for anchor in row.find_all("a"):
        name = compact(anchor.get_text(" ", strip=True))
        if is_japanese_name(name):
            return name
    for cell in row.find_all(["th", "td"]):
        name = compact(cell.get_text(" ", strip=True))
        if is_japanese_name(name):
            return name
    return None


def class_from_text(text: str):
    m = re.search(r"\b([ABC][123])\b", norm(text))
    return m.group(1) if m else None


def registration_from_text(text: str):
    m = re.search(r"(?<!\d)(\d{4})(?!\d)", norm(text))
    return int(m.group(1)) if m else None


def motor_triplet_from_text(text: str):
    """Find motor No / 2-rentai / 3-rentai from the official racelist row."""
    text = norm(text)
    # Preferred: the motor block is followed by boat number and boat rates.
    patterns = [
        r"(?<!\d)(\d{1,2})\s+(\d{1,3}\.\d+)\s+(\d{1,3}\.\d+)\s+[1-6]\s+\d{1,3}\.\d+\s+\d{1,3}\.\d+",
        r"(?<!\d)(\d{1,2})\s+(\d{1,3}\.\d+)\s+(\d{1,3}\.\d+)(?!\d)",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            motor_no = int(m.group(1))
            m2 = float(m.group(2))
            m3 = float(m.group(3))
            if 1 <= motor_no <= 100 and 0 <= m2 <= 100 and 0 <= m3 <= 100:
                return motor_no, m2, m3
    return None


def merge_boat(dst, src):
    if dst is None:
        dst = {"boat_no": src["boat_no"]}
    for key, value in src.items():
        if key == "boat_no":
            continue
        if key == "raw_cells":
            dst.setdefault("raw_cells", [])
            for cell in value or []:
                if cell not in dst["raw_cells"]:
                    dst["raw_cells"].append(cell)
            continue
        if dst.get(key) in (None, "") and value not in (None, ""):
            dst[key] = value
    return dst


def parse_roster(html: str):
    soup = BeautifulSoup(html, "html.parser")
    merged = {}

    for row in soup.find_all("tr"):
        cells = row_cells(row)
        if not cells:
            continue
        boat_no = boat_no_from_row(row)
        if boat_no not in BOATS:
            continue
        text = " ".join(cells)
        name = name_from_row(row)
        triplet = motor_triplet_from_text(text)
        item = {
            "boat_no": boat_no,
            "racer_name": name,
            "racer_class": class_from_text(text),
            "registration_no": registration_from_text(text),
            "motor_no": triplet[0] if triplet else None,
            "motor_2rentai_rate": triplet[1] if triplet else None,
            "motor_3rentai_rate": triplet[2] if triplet else None,
            "weight": None,
            "raw_cells": cells,
        }
        m = re.search(r"(\d{2,3}\.\d)kg", text)
        if m:
            item["weight"] = float(m.group(1))
        merged[boat_no] = merge_boat(merged.get(boat_no), item)

    # Global name fallback. This handles official desktop/mobile fragments where
    # the lane number and racer-name anchor live in different <tr> elements.
    names = []
    for anchor in soup.find_all("a"):
        href = str(anchor.get("href") or "")
        name = compact(anchor.get_text(" ", strip=True))
        if ("/data/racersearch/profile" in href or "toban=" in href) and is_japanese_name(name) and name not in names:
            names.append(name)
    for boat_no in BOATS:
        if boat_no in merged and not merged[boat_no].get("racer_name") and len(names) >= boat_no:
            merged[boat_no]["racer_name"] = names[boat_no - 1]

    return [merged.get(b, {"boat_no": b, "raw_cells": []}) for b in BOATS]


def parse_before(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = {b: {"boat_no": b, "raw_cells": []} for b in BOATS}

    for row in soup.find_all("tr"):
        cells = row_cells(row)
        if not cells:
            continue
        boat_no = boat_no_from_row(row)
        if boat_no not in BOATS:
            continue
        text = " ".join(cells)
        d = out[boat_no]
        d["raw_cells"] = list(dict.fromkeys(d.get("raw_cells", []) + cells))
        d["raw_text"] = text

        # Exhibition time is normally the first xx.xx in the pre-race row.
        if d.get("exhibition_time") is None:
            m = re.search(r"(?<!\d)(6\.\d{2})(?!\d)", text)
            if m:
                d["exhibition_time"] = float(m.group(1))

        if d.get("exhibition_st") is None:
            for pattern in (r"展示ST[^0-9Ff+-]*([Ff]?-?\d+\.\d+)", r"\b(F?\.?\d+\.\d+)\b"):
                m = re.search(pattern, text)
                if not m:
                    continue
                value = m.group(1).replace("F", "").replace("f", "")
                try:
                    d["exhibition_st"] = float(value)
                    break
                except ValueError:
                    pass

    # The dedicated start-exhibition blocks are the safest ST source.
    for course, block in enumerate(soup.select("div.table1_boatImage1")[:6], start=1):
        num = block.select_one(".table1_boatImage1Number")
        tm = block.select_one(".table1_boatImage1Time")
        if not num or not tm:
            continue
        m = re.search(r"([1-6])", norm(num.get_text(" ", strip=True)))
        st_text = norm(tm.get_text(" ", strip=True))
        st = re.search(r"([Ff]?-?\d+\.\d+)", st_text)
        if not m or not st:
            continue
        value = st.group(1).replace("F", "").replace("f", "")
        try:
            boat_no = int(m.group(1))
            out[boat_no]["exhibition_st"] = float(value)
            out[boat_no]["exhibition_course"] = course
        except ValueError:
            pass

    return [out[b] for b in BOATS]


def parse_motor_ranking(html: str):
    """Return official motor number/2-rentai keyed by normalized racer name."""
    soup = BeautifulSoup(html, "html.parser")
    by_name = {}
    by_reg = {}
    for row in soup.find_all("tr"):
        cells = row_cells(row)
        if not cells:
            continue
        text = " ".join(cells)
        reg = registration_from_text(text)
        name = name_from_row(row)
        # Ranking table order: registration, racer, class, motor no, motor 2-rentai...
        motor = None
        for i, cell in enumerate(cells):
            if re.fullmatch(r"\d{1,2}", cell.strip()) and i + 1 < len(cells):
                try:
                    candidate = int(cell.strip())
                except ValueError:
                    continue
                if 1 <= candidate <= 100 and re.search(r"\d{1,3}\.\d+%?", cells[i + 1]):
                    rate = float(re.sub(r"[^0-9.]", "", cells[i + 1]))
                    if 0 <= rate <= 100:
                        motor = (candidate, rate)
                        break
        if motor is None:
            m = re.search(r"(?<!\d)(\d{1,2})\s+(\d{1,3}\.\d+)%", text)
            if m:
                motor = (int(m.group(1)), float(m.group(2)))
        if motor:
            record = {"motor_no": motor[0], "motor_2rentai_rate": motor[1]}
            if name:
                by_name[compact(name)] = record
            if reg:
                by_reg[reg] = record
    return {"by_name": by_name, "by_reg": by_reg}


def build_race(date: str, race_no: int, fetch_before: bool = True, fetch_result: bool = False):
    rid = f"{date}_06_{int(race_no):02d}"
    urls = {
        "racelist": f"{BASE}/racelist?hd={date}&jcd={VENUE}&rno={race_no}",
        "beforeinfo": f"{BASE}/beforeinfo?hd={date}&jcd={VENUE}&rno={race_no}",
        "result": f"{BASE}/result?hd={date}&jcd={VENUE}&rno={race_no}",
        "rankingmotor": f"{BASE}/rankingmotor?hd={date}&jcd={VENUE}",
    }
    result = {
        "race_id": rid,
        "race_date": date,
        "venue": "浜名湖",
        "race_no": int(race_no),
        "source_url": urls["racelist"],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "status": "incomplete",
        "boats": [],
        "sources": urls,
        "errors": [],
    }

    try:
        result["boats"] = parse_roster(fetch(urls["racelist"]))
    except Exception as exc:
        result["errors"].append({"stage": "racelist", "error": str(exc)})
        return result

    try:
        ranking = parse_motor_ranking(fetch(urls["rankingmotor"]))
        for boat in result["boats"]:
            rec = None
            if boat.get("registration_no") in ranking["by_reg"]:
                rec = ranking["by_reg"][boat["registration_no"]]
            if not rec and boat.get("racer_name"):
                rec = ranking["by_name"].get(compact(boat["racer_name"]))
            if rec:
                if boat.get("motor_no") is None:
                    boat["motor_no"] = rec["motor_no"]
                if boat.get("motor_2rentai_rate") is None:
                    boat["motor_2rentai_rate"] = rec["motor_2rentai_rate"]
        result["motor_data_source"] = urls["rankingmotor"]
        result["motor_field_count"] = len(ranking["by_name"])
    except Exception as exc:
        result["errors"].append({"stage": "rankingmotor", "error": str(exc)})

    if fetch_before:
        try:
            before = parse_before(fetch(urls["beforeinfo"]))
            by = {x["boat_no"]: x for x in before}
            for boat in result["boats"]:
                for key, value in by.get(boat["boat_no"], {}).items():
                    if key != "boat_no" and value not in (None, ""):
                        boat[key] = value
        except Exception as exc:
            result["errors"].append({"stage": "beforeinfo", "error": str(exc)})

    if fetch_result:
        try:
            result["result"] = parse_result(fetch(urls["result"]))
        except Exception as exc:
            result["errors"].append({"stage": "result", "error": str(exc)})

    exact_six = [int(b.get("boat_no", 0)) for b in result["boats"]] == list(BOATS)
    required_names = exact_six and all(b.get("racer_name") for b in result["boats"])
    required_motor = exact_six and all(
        b.get("motor_no") is not None
        and b.get("motor_2rentai_rate") is not None
        and b.get("motor_3rentai_rate") is not None
        for b in result["boats"]
    )
    required_before = exact_six and all(
        b.get("exhibition_time") is not None and b.get("exhibition_st") is not None
        for b in result["boats"]
    )
    result["status"] = (
        "ready_for_simulation" if required_names and required_motor and required_before
        else "needs_exhibition" if required_names and required_motor
        else "incomplete"
    )
    return result


def parse_result(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for row in soup.find_all("tr"):
        cells = row_cells(row)
        if not cells:
            continue
        boat_no = boat_no_from_row(row)
        if boat_no not in BOATS:
            continue
        text = " ".join(cells)
        d = out.setdefault(boat_no, {"boat_no": boat_no, "raw_cells": []})
        d["raw_cells"] = list(dict.fromkeys(d["raw_cells"] + cells))
        m = re.search(r"着順[^0-9]*([1-6])", text)
        if m:
            d["finish"] = int(m.group(1))
        m = re.search(r"進入[^0-9]*([1-6])", text)
        if m:
            d["actual_course"] = int(m.group(1))
        m = re.search(r"ST[^-+0-9]*([Ff]?-?\d+\.\d+)", text)
        if m:
            d["actual_st"] = float(m.group(1).replace("F", "").replace("f", ""))
    return [out[b] for b in BOATS if b in out]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--race", type=int, required=True)
    ap.add_argument("--result", action="store_true")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    data = build_race(args.date, args.race, True, args.result)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps(data, ensure_ascii=False, indent=2))
