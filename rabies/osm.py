"""อสม. door-to-door survey summary (แบบสำรวจ อสม. เคาะประตูบ้าน ป้องกันโรคพิษสุนัขบ้า).

This is an *aggregated* dataset (one row per location) that is separate from the Google-Form
household survey, so it is shown on its own page and never added to Google-Form totals
(different questions + possible overlap of people → double counting).

File: data/osm_summary.csv — to update, add rows with a newer `as_of` date (YYYY-MM-DD, ค.ศ.).
The latest `as_of` per location is used.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PATH = Path(__file__).resolve().parents[1] / "data" / "osm_summary.csv"
COUNT_COLS = ["persons", "households", "bitten_yes", "bitten_no",
              "vax_full", "vax_partial", "vax_in_progress", "vax_none"]
VAX_COLS = ["vax_full", "vax_partial", "vax_in_progress", "vax_none"]
VAX_LABELS = {"vax_full": "ได้รับวัคซีนครบชุด", "vax_partial": "ได้รับไม่ครบชุด",
              "vax_in_progress": "อยู่ระหว่างฉีด", "vax_none": "ไม่ได้รับวัคซีน"}
VAX_COLORS = {"ได้รับวัคซีนครบชุด": "#2a9d8f", "ได้รับไม่ครบชุด": "#e9c46a",
              "อยู่ระหว่างฉีด": "#f4a261", "ไม่ได้รับวัคซีน": "#d62828"}

TH_COLS = {
    "location": "สถานที่", "location_type": "ประเภท", "tambon": "ตำบล", "moo": "หมู่ที่",
    "persons": "จำนวนที่สำรวจ (คน)", "households": "หลังคาเรือน",
    "bitten_yes": "เคยถูกกัด/ข่วน/เลีย (คน)", "bitten_no": "ไม่เคย (คน)",
    "vax_full": "ฉีดครบชุด", "vax_partial": "ไม่ครบชุด", "vax_in_progress": "อยู่ระหว่างฉีด",
    "vax_none": "ไม่ได้รับวัคซีน", "pct_bitten": "% เคยถูกกัด",
    "pct_full": "% ฉีดครบชุด (ของผู้ถูกกัด)", "pct_none": "% ไม่ได้รับวัคซีน (ของผู้ถูกกัด)",
}


def load(path: Path = PATH) -> tuple[pd.DataFrame, list[str], pd.Timestamp | None]:
    """Return (latest rows, list of validation warnings, as_of date)."""
    if not path.exists():
        return pd.DataFrame(columns=["location", "tambon", "moo", *COUNT_COLS]), [], None
    df = pd.read_csv(path, dtype={"location": str, "tambon": str})
    df["as_of"] = pd.to_datetime(df["as_of"], errors="coerce")
    df = df.sort_values("as_of").groupby("location", as_index=False).tail(1)
    for c in COUNT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["moo"] = pd.to_numeric(df["moo"], errors="coerce").astype("Int64")

    warnings = []
    for r in df.itertuples():
        if r.bitten_yes + r.bitten_no != r.persons:
            warnings.append(f"{r.location}: เคย ({r.bitten_yes}) + ไม่เคย ({r.bitten_no}) ≠ จำนวนที่สำรวจ ({r.persons})")
        vs = sum(getattr(r, c) for c in VAX_COLS)
        if vs != r.bitten_yes:
            warnings.append(f"{r.location}: ผลรวมสถานะวัคซีน ({vs}) ≠ ผู้เคยถูกกัด ({r.bitten_yes})")
    return df.reset_index(drop=True), warnings, df["as_of"].max()


def add_rates(agg: pd.DataFrame) -> pd.DataFrame:
    agg = agg.copy()
    p = lambda a, b: (a / b * 100).where(b > 0, 0.0)  # noqa: E731
    agg["pct_bitten"] = p(agg.bitten_yes, agg.persons)
    agg["pct_full"] = p(agg.vax_full, agg.bitten_yes)
    agg["pct_none"] = p(agg.vax_none, agg.bitten_yes)
    return agg


def summarise(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    agg = df.groupby(keys, dropna=False)[COUNT_COLS].sum(min_count=1).reset_index()
    agg["households"] = agg["households"].fillna(0)
    return add_rates(agg)


def thai_date(ts: pd.Timestamp | None) -> str:
    if ts is None or pd.isna(ts):
        return "-"
    months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม",
              "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    return f"{ts.day} {months[ts.month - 1]} {ts.year + 543}"
