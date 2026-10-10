"""Data-cleaning pipeline for the Prasat rabies household survey (Google Form -> Sheet).

The raw sheet is typed by volunteers, so numeric answers arrive as things like
"2 คน", "4ตัง", "ไม่มี", "-", "_", "--", "", Thai digits, etc. This module turns the
raw sheet into a tidy one-row-per-household table plus a log of every fix.

Usage (CLI):  python -m rabies.cleaning   -> writes data/clean_survey.csv, data/cleaning_log.csv
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

SHEET_ID = "1AiqccPtqRYPWNg4Eg08cKlIIAqnh8TR4bjLh8eiPQ4w"
GID = "247910277"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

TAMBONS = [
    "กังแอน", "ทมอ", "ไพล", "ปรือ", "ทุ่งมน", "ตาเบา", "หนองใหญ่", "โคกยาง", "โคกสะอาด",
    "บ้านไทร", "โชคนาสาม", "เชื้อเพลิง", "ปราสาททนง", "ตานี", "บ้านพลวง", "กันตวจระมวล",
    "สมุด", "ประทัดบุ",
]

# Raw Thai header (matched by keyword, so small header edits don't break the pipeline)
COLUMN_RULES = [
    ("timestamp", ["timestamp", "ประทับเวลา"]),
    ("tambon", ["ตำบล"]),
    ("moo", ["หมู่"]),
    ("house_no", ["บ้านเลขที่"]),
    ("residents", ["ผู้อาศัย"]),
    ("people_bitten_unvax", ["ถูกสุนัขกัด"]),
    ("people_vaccinated", ["เคยฉีดวัคซีน"]),
    ("dogs_vaccinated", ["สุนัขที่ได้รับวัคซีน"]),
    ("dogs_total", ["สุนัขทั้งหมด"]),
    ("cats_vaccinated", ["แมวที่ได้รับวัคซีน"]),
    ("cats_total", ["แมวทั้งหมด"]),
    ("other_mammals", ["ลูกด้วยนมอื่น"]),
    ("phone", ["เบอร์โทร"]),
]

NUMERIC_COLS = [
    "residents", "people_bitten_unvax", "people_vaccinated",
    "dogs_total", "dogs_vaccinated", "cats_total", "cats_vaccinated", "other_mammals",
]

THAI_LABELS = {
    "residents": "จำนวนผู้อาศัย",
    "people_bitten_unvax": "ถูกกัด/ข่วน แต่ยังไม่ฉีดวัคซีน",
    "people_vaccinated": "เคยฉีดวัคซีนแล้ว",
    "dogs_total": "สุนัขทั้งหมด",
    "dogs_vaccinated": "สุนัขที่ได้รับวัคซีน",
    "cats_total": "แมวทั้งหมด",
    "cats_vaccinated": "แมวที่ได้รับวัคซีน",
    "other_mammals": "สัตว์เลี้ยงลูกด้วยนมอื่นๆ",
}

ZERO_TOKENS = {"", "-", "--", "---", "_", "__", "ไม่มี", "ไม่", "ไม่มีค่ะ", "ไม่มีครับ",
               "ไม่ได้เลี้ยง", "ไม่เลี้ยง", "none", "no", "nan", "x", "0"}
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
THAI_NUMBER_WORDS = {
    "หนึ่ง": 1, "สอง": 2, "สาม": 3, "สี่": 4, "ห้า": 5,
    "หก": 6, "เจ็ด": 7, "แปด": 8, "เก้า": 9, "สิบ": 10,
}
TEST_PATTERN = re.compile(r"ทดสอบ|test|ทดลอง", re.IGNORECASE)


@dataclass
class CleanResult:
    clean: pd.DataFrame
    raw: pd.DataFrame
    log: pd.DataFrame
    excluded: pd.DataFrame
    stats: dict = field(default_factory=dict)


class _Logger:
    def __init__(self):
        self.rows = []

    def add(self, row_id, column, before, after, issue):
        self.rows.append({"แถวต้นฉบับ": row_id, "คอลัมน์": column,
                          "ค่าเดิม": before, "ค่าใหม่": after, "ปัญหา": issue})

    def frame(self):
        return pd.DataFrame(self.rows, columns=["แถวต้นฉบับ", "คอลัมน์", "ค่าเดิม", "ค่าใหม่", "ปัญหา"])


# --------------------------------------------------------------------------- loaders
def load_raw(source: str | Path | None = None) -> pd.DataFrame:
    """Read the raw sheet as strings (never let pandas guess types on dirty data)."""
    src = source or CSV_URL
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    df.insert(0, "row_id", range(2, len(df) + 2))  # matches sheet row number
    return df


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping, used = {}, set()
    for key, kws in COLUMN_RULES:
        for col in df.columns:
            if col in used or col == "row_id":
                continue
            if any(k.lower() in col.lower() for k in kws):
                mapping[col] = key
                used.add(col)
                break
    out = df.rename(columns=mapping)
    for key, _ in COLUMN_RULES:
        if key not in out.columns:
            out[key] = ""
    return out[["row_id"] + [k for k, _ in COLUMN_RULES]]


# --------------------------------------------------------------------------- field parsers
def parse_count(value: str) -> tuple[float | None, str | None]:
    """Return (number, issue). number=None means unparseable."""
    s = str(value).strip().translate(THAI_DIGITS)
    s_norm = s.lower().replace(" ", "")
    if s_norm in ZERO_TOKENS or re.fullmatch(r"[-_.\s]+", s_norm or "-"):
        return 0.0, (None if s_norm == "0" else ("ช่องว่าง → 0" if s_norm == "" else "สัญลักษณ์/คำว่าไม่มี → 0"))
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if nums:
        n = float(nums[0])
        if len(nums) > 1:
            return n, "มีหลายตัวเลข ใช้ตัวแรก"
        if not re.fullmatch(r"\d+", s):
            return n, "ตัดหน่วย/ข้อความออก"
        return n, None
    for word, n in THAI_NUMBER_WORDS.items():
        if word in s:
            return float(n), "แปลงคำเป็นตัวเลข"
    return None, "อ่านค่าไม่ได้"


def match_tambon(value: str) -> tuple[str | None, str | None]:
    s = re.sub(r"^(ตำบล|ต\.)\s*", "", str(value).strip())
    s = s.replace(" ", "")
    if s in TAMBONS:
        return s, None
    hit = difflib.get_close_matches(s, TAMBONS, n=1, cutoff=0.6)
    if hit:
        return hit[0], "สะกดผิด → จับคู่ชื่อใกล้เคียง"
    return None, "ไม่พบชื่อตำบลในอำเภอปราสาท"


def parse_moo(value: str) -> tuple[int | None, str | None]:
    s = str(value).translate(THAI_DIGITS)
    m = re.search(r"\d+", s)
    if not m:
        return None, "ไม่ระบุหมู่"
    return int(m.group()), None


def parse_house_no(value: str) -> tuple[str, str | None]:
    s = str(value).translate(THAI_DIGITS).strip()
    m = re.match(r"\s*(\d+(?:\s*/\s*\d+)?)", s)
    if not m:
        return s, ("ไม่ระบุบ้านเลขที่" if not s else None)
    hn = m.group(1).replace(" ", "")
    return hn, (None if hn == s else "ตัดที่อยู่ส่วนเกินออก")


def parse_phone(value: str) -> tuple[str, str | None]:
    d = re.sub(r"\D", "", str(value).translate(THAI_DIGITS))
    if d.startswith("66") and len(d) == 11:
        d = "0" + d[2:]
    if len(d) == 9 and not d.startswith("0"):
        d = "0" + d
    if len(d) not in (9, 10):
        return d, "เบอร์โทรไม่ครบ/ไม่ถูกต้อง"
    return d, None


def parse_timestamp(series: pd.Series) -> pd.Series:
    # Google Forms (US locale) -> M/D/YYYY H:M:S. Fall back to day-first if that fails.
    ts = pd.to_datetime(series, format="%m/%d/%Y %H:%M:%S", errors="coerce")
    miss = ts.isna()
    if miss.any():
        ts[miss] = pd.to_datetime(series[miss], dayfirst=True, errors="coerce")
    return ts


# --------------------------------------------------------------------------- pipeline
def clean(raw: pd.DataFrame) -> CleanResult:
    log = _Logger()
    df = _map_columns(raw.copy())
    n_raw = len(df)

    # 0) drop completely empty rows
    empty = df.drop(columns=["row_id"]).apply(lambda r: "".join(r).strip() == "", axis=1)
    df = df[~empty].copy()

    df["timestamp"] = parse_timestamp(df["timestamp"])
    df["date"] = df["timestamp"].dt.date

    # 1) location fields
    loc_labels = {"tambon": "ตำบล", "moo": "หมู่ที่", "house_no": "บ้านเลขที่", "phone": "เบอร์โทร"}
    for col, fn in [("tambon", match_tambon), ("moo", parse_moo),
                    ("house_no", parse_house_no), ("phone", parse_phone)]:
        new_vals = []
        for rid, v in zip(df["row_id"], df[col]):
            nv, issue = fn(v)
            if issue:
                log.add(rid, loc_labels[col], v, nv, issue)
            new_vals.append(nv)
        df[col] = new_vals

    # 2) numeric fields
    df["n_blank_fields"] = 0
    for col in NUMERIC_COLS:
        new_vals = []
        for i, (rid, v) in enumerate(zip(df["row_id"], df[col])):
            n, issue = parse_count(v)
            if issue:
                log.add(rid, THAI_LABELS[col], v, n, issue)
            if str(v).strip() == "":
                df.iloc[i, df.columns.get_loc("n_blank_fields")] += 1
            new_vals.append(n)
        df[col] = pd.to_numeric(pd.Series(new_vals, index=df.index), errors="coerce")

    # 3) flag test / invalid records
    df["exclude_reason"] = ""
    test_mask = raw.loc[df.index].drop(columns=["row_id"]).apply(
        lambda r: bool(TEST_PATTERN.search(" ".join(r))), axis=1)
    df.loc[test_mask, "exclude_reason"] = "ข้อมูลทดสอบ"
    df.loc[df["tambon"].isna() & (df["exclude_reason"] == ""), "exclude_reason"] = "ไม่ทราบตำบล"
    df.loc[(df["residents"].fillna(0) <= 0) & (df["exclude_reason"] == ""), "exclude_reason"] = "จำนวนผู้อาศัย = 0/ไม่ระบุ"

    # 4) logical consistency fixes
    for total, vax, label in [("dogs_total", "dogs_vaccinated", "สุนัข"), ("cats_total", "cats_vaccinated", "แมว")]:
        bad = df[vax] > df[total]
        for rid, t, v in df.loc[bad, ["row_id", total, vax]].itertuples(index=False):
            log.add(rid, f"{label}ทั้งหมด", t, v, f"{label}ฉีดวัคซีน > {label}ทั้งหมด → ปรับจำนวนทั้งหมดให้เท่ากับที่ฉีด")
        df.loc[bad, total] = df.loc[bad, vax]
    people_sum = df["people_bitten_unvax"] + df["people_vaccinated"]
    bad = people_sum > df["residents"]
    for rid, r, s in zip(df.loc[bad, "row_id"], df.loc[bad, "residents"], people_sum[bad]):
        log.add(rid, "จำนวนผู้อาศัย", r, s, "ผลรวมผู้ถูกกัด+ฉีดวัคซีน > ผู้อาศัย → ปรับผู้อาศัยเพิ่ม")
    df.loc[bad, "residents"] = people_sum[bad]

    # 5) duplicates: same tambon + moo + house_no -> keep the latest submission
    df = df.sort_values("timestamp")
    df["house_key"] = df["tambon"].fillna("?") + "|" + df["moo"].astype(str) + "|" + df["house_no"].astype(str)
    dup = df.duplicated("house_key", keep="last") & (df["exclude_reason"] == "")
    df.loc[dup, "exclude_reason"] = "ส่งซ้ำ (เก็บรายการล่าสุด)"

    excluded = df[df["exclude_reason"] != ""].copy()
    for rid, why in zip(excluded["row_id"], excluded["exclude_reason"]):
        log.add(rid, "ทั้งแถว", "", "ตัดออก", why)
    out = df[df["exclude_reason"] == ""].copy()

    # 6) derived metrics
    out["moo"] = out["moo"].astype("Int64")
    out["people_other"] = (out["residents"] - out["people_bitten_unvax"] - out["people_vaccinated"]).clip(lower=0)
    out["dogs_unvaccinated"] = out["dogs_total"] - out["dogs_vaccinated"]
    out["cats_unvaccinated"] = out["cats_total"] - out["cats_vaccinated"]
    out["has_bitten"] = out["people_bitten_unvax"] > 0
    out["has_dog"] = out["dogs_total"] > 0
    out["has_cat"] = out["cats_total"] > 0
    out["phone_masked"] = out["phone"].astype(str).str.replace(r"^(\d{3})\d+(\d{3})$", r"\1-xxx-\2", regex=True)
    out = out.drop(columns=["exclude_reason"]).reset_index(drop=True)

    log_df = log.frame().sort_values("แถวต้นฉบับ", kind="stable").reset_index(drop=True)
    stats = {"raw_rows": n_raw, "empty_rows": int(empty.sum()), "excluded": len(excluded),
             "clean_rows": len(out), "fixes": len(log_df)}
    return CleanResult(clean=out, raw=raw, log=log_df, excluded=excluded, stats=stats)


def run(source=None) -> CleanResult:
    return clean(load_raw(source))


if __name__ == "__main__":
    res = run()
    DATA_DIR.mkdir(exist_ok=True)
    res.clean.to_csv(DATA_DIR / "clean_survey.csv", index=False, encoding="utf-8-sig")
    res.log.to_csv(DATA_DIR / "cleaning_log.csv", index=False, encoding="utf-8-sig")
    print(res.stats)
