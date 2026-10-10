"""Shared Streamlit helpers: data loading, filters, theme, KPI cards, aggregation."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.io as pio
import streamlit as st

from rabies.cleaning import CSV_URL, DATA_DIR, TAMBONS, clean, load_raw
from rabies.population import POP_SOURCE, POPULATION, base_houses, base_population  # noqa: F401

GEOJSON_PATH = DATA_DIR / "prasat_tambon.geojson"
BACKUP_RAW = DATA_DIR / "raw_backup.csv"

# ----------------------------------------------------------------------------- theme
COLORS = {
    "vax": "#2a9d8f", "unvax": "#e76f51", "bitten": "#d62828", "other": "#adb5bd",
    "house": "#264653", "people": "#457b9d", "dog": "#f4a261", "cat": "#8d6cab", "mammal": "#6c757d",
}
FONT = "Sarabun, Tahoma, sans-serif"

pio.templates["thai"] = pio.templates["plotly_white"]
pio.templates["thai"].layout.font = dict(family=FONT, size=14)
pio.templates["thai"].layout.title.font = dict(family=FONT, size=17)
pio.templates["thai"].layout.hoverlabel = dict(font_family=FONT)
pio.templates["thai"].layout.colorway = ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51",
                                         "#457b9d", "#8d6cab", "#6c757d"]
pio.templates.default = "thai"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, select, textarea,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"], h1, h2, h3, h4 {
  font-family: 'Sarabun', Tahoma, sans-serif !important;
}
.kpi {background:#fff;border-radius:14px;padding:14px 18px;border-left:6px solid var(--c);
      box-shadow:0 1px 6px rgba(0,0,0,.08);height:100%;}
.kpi .lbl{font-size:.95rem;color:#555;margin-bottom:2px}
.kpi .val{font-size:2rem;font-weight:700;color:#222;line-height:1.1}
.kpi .sub{font-size:.85rem;color:#777}
.block-container{padding-top:1.6rem}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def kpi(col, label, value, sub="", color="#264653"):
    if isinstance(value, (int, float)):
        value = f"{value:,.0f}"
    col.markdown(f'<div class="kpi" style="--c:{color}"><div class="lbl">{label}</div>'
                 f'<div class="val">{value}</div><div class="sub">{sub}</div></div>',
                 unsafe_allow_html=True)


def pct(a, b) -> float:
    return (a / b * 100) if b else 0.0


def fmt_pct(a, b) -> str:
    return f"{pct(a, b):.1f}%"


# ----------------------------------------------------------------------------- data
@st.cache_data(ttl=300, show_spinner="กำลังดึงข้อมูลจาก Google Sheets และทำความสะอาดข้อมูล...")
def load_data():
    """Fetch the live sheet (falls back to the last good backup if offline)."""
    source_note = "Google Sheets (ออนไลน์)"
    try:
        raw = load_raw(CSV_URL)
        DATA_DIR.mkdir(exist_ok=True)
        raw.drop(columns=["row_id"]).to_csv(BACKUP_RAW, index=False, encoding="utf-8-sig")
    except Exception as e:  # noqa: BLE001
        if not BACKUP_RAW.exists():
            raise
        raw = load_raw(BACKUP_RAW)
        source_note = f"ไฟล์สำรอง (เชื่อมต่อไม่ได้: {type(e).__name__})"
    res = clean(raw)
    return res.clean, res.raw, res.log, res.excluded, res.stats, source_note, pd.Timestamp.now()


@st.cache_data
def load_geojson():
    gj = json.loads(Path(GEOJSON_PATH).read_text(encoding="utf-8"))
    cent = {}
    for f in gj["features"]:
        g = f["geometry"]
        rings = [g["coordinates"][0]] if g["type"] == "Polygon" else [p[0] for p in g["coordinates"]]
        ring = max(rings, key=len)
        a = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            cr = x0 * y1 - x1 * y0
            a += cr
            cx += (x0 + x1) * cr
            cy += (y0 + y1) * cr
        if abs(a) < 1e-12:
            xs, ys = zip(*ring)
            cent[f["properties"]["tambon"]] = (sum(ys) / len(ys), sum(xs) / len(xs))
        else:
            cent[f["properties"]["tambon"]] = (cy / (3 * a), cx / (3 * a))
    return gj, cent


def filtered() -> pd.DataFrame:
    return st.session_state.get("df_filtered", pd.DataFrame())


def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    sb = st.sidebar
    sb.markdown("### 🔎 ตัวกรองข้อมูล")
    responded = [t for t in TAMBONS if t in set(df["tambon"])]
    tambons = sb.multiselect("ตำบล", TAMBONS, placeholder="ทุกตำบล",
                             help=f"มีข้อมูลแล้ว {len(responded)} จาก {len(TAMBONS)} ตำบล")
    out = df if not tambons else df[df["tambon"].isin(tambons)]
    moos = sorted(out["moo"].dropna().unique().tolist())
    sel_moo = sb.multiselect("หมู่ที่", moos, placeholder="ทุกหมู่")
    if sel_moo:
        out = out[out["moo"].isin(sel_moo)]
    if len(df):
        dmin, dmax = df["date"].min(), df["date"].max()
        rng = sb.date_input("ช่วงวันที่ตอบแบบสำรวจ", (dmin, dmax), min_value=dmin, max_value=dmax)
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            out = out[(out["date"] >= rng[0]) & (out["date"] <= rng[1])]
    st.session_state["sel_tambons"] = tambons
    return out


# ----------------------------------------------------------------------------- aggregation
SUM_COLS = ["residents", "people_bitten_unvax", "people_vaccinated", "people_other",
            "dogs_total", "dogs_vaccinated", "dogs_unvaccinated",
            "cats_total", "cats_vaccinated", "cats_unvaccinated", "other_mammals"]


def by_area(df: pd.DataFrame, keys=("tambon",), all_tambons=False) -> pd.DataFrame:
    keys = list(keys)
    g = df.groupby(keys, dropna=False)
    agg = g[SUM_COLS].sum()
    agg["households"] = g.size()
    agg["hh_bitten"] = g["has_bitten"].sum()
    agg["hh_dog"] = g["has_dog"].sum()
    agg["hh_cat"] = g["has_cat"].sum()
    agg = agg.reset_index()
    if all_tambons and keys == ["tambon"]:
        agg = pd.DataFrame({"tambon": TAMBONS}).merge(agg, on="tambon", how="left").fillna(0)
    agg["pct_bitten_people"] = agg.apply(lambda r: pct(r.people_bitten_unvax, r.residents), axis=1)
    agg["pct_vax_people"] = agg.apply(lambda r: pct(r.people_vaccinated, r.residents), axis=1)
    agg["pct_hh_bitten"] = agg.apply(lambda r: pct(r.hh_bitten, r.households), axis=1)
    agg["pct_dog_vax"] = agg.apply(lambda r: pct(r.dogs_vaccinated, r.dogs_total), axis=1)
    agg["pct_cat_vax"] = agg.apply(lambda r: pct(r.cats_vaccinated, r.cats_total), axis=1)
    if keys == ["tambon"]:
        agg = agg.merge(POPULATION, on="tambon", how="left")
        agg["pct_coverage"] = agg.apply(lambda r: pct(r.residents, r.pop_total), axis=1)
        agg["pct_hh_coverage"] = agg.apply(lambda r: pct(r.households, r.houses_total), axis=1)
    return agg


TH_COLS = {
    "tambon": "ตำบล", "moo": "หมู่ที่", "house_no": "บ้านเลขที่", "households": "ครัวเรือนที่สำรวจ",
    "residents": "ผู้อาศัย (คน)", "people_bitten_unvax": "ถูกกัด/ข่วน ยังไม่ฉีดวัคซีน (คน)",
    "people_vaccinated": "เคยฉีดวัคซีนแล้ว (คน)", "people_other": "ไม่เคยถูกกัด/ไม่เคยฉีด (คน)",
    "dogs_total": "สุนัข (ตัว)", "dogs_vaccinated": "สุนัขฉีดวัคซีน (ตัว)",
    "dogs_unvaccinated": "สุนัขยังไม่ฉีด (ตัว)", "cats_total": "แมว (ตัว)",
    "cats_vaccinated": "แมวฉีดวัคซีน (ตัว)", "cats_unvaccinated": "แมวยังไม่ฉีด (ตัว)",
    "other_mammals": "สัตว์เลี้ยงลูกด้วยนมอื่น (ตัว)", "hh_bitten": "ครัวเรือนที่มีผู้ถูกกัด",
    "hh_dog": "ครัวเรือนที่เลี้ยงสุนัข", "hh_cat": "ครัวเรือนที่เลี้ยงแมว",
    "pct_bitten_people": "% ผู้ถูกกัดยังไม่ฉีด", "pct_vax_people": "% ผู้เคยฉีดวัคซีน",
    "pct_hh_bitten": "% ครัวเรือนที่มีผู้ถูกกัด", "pct_dog_vax": "% สุนัขฉีดวัคซีน",
    "pct_cat_vax": "% แมวฉีดวัคซีน", "timestamp": "วันเวลาที่ตอบ", "phone": "เบอร์โทร",
    "phone_masked": "เบอร์โทร",
    "pop_male": "ประชากรชาย (ทะเบียน)", "pop_female": "ประชากรหญิง (ทะเบียน)",
    "pop_total": "ประชากรทะเบียนราษฎร์ (คน)", "pct_coverage": "% ความครอบคลุมประชากร",
    "houses_total": "บ้านทะเบียนราษฎร์ (หลัง)", "pct_hh_coverage": "% ความครอบคลุมครัวเรือน",
    "persons_per_house": "คนต่อบ้าน (ทะเบียน)",
}


def to_thai(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=TH_COLS)


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def empty_guard(df: pd.DataFrame) -> bool:
    if df.empty:
        st.info("ไม่มีข้อมูลตามตัวกรองที่เลือก")
        return True
    return False
