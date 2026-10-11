"""Hospital bite-episode data (HOSxP export, de-identified, 5 years).

One row = one OPD visit for an animal bite / rabies exposure.
Animal is derived from ICD-10:
    W54   = ถูกสุนัขกัด                         -> "สุนัข"
    W55   = ถูกสัตว์เลี้ยงลูกด้วยนมอื่นกัด (รวมแมว)  -> "แมว/สัตว์เลี้ยงลูกด้วยนมอื่น"
    Z20.3 = สัมผัสโรคพิษสุนัขบ้า ไม่ระบุสัตว์        -> "ไม่ระบุสัตว์ (Z20.3)"
ICD-10 (WHO / ICD-10-TM) does not split cats from other mammals inside W55.
4th character = place of occurrence, 5th = activity.
"""
from __future__ import annotations

import json

import pandas as pd

from rabies.cleaning import DATA_DIR, ROOT, TAMBONS
from rabies.population import POPULATION

FILE_NAME = "rabies_bite_episodes_5yr_deidentified.csv"
CANDIDATES = [ROOT / FILE_NAME, DATA_DIR / FILE_NAME]
PRASAT_CHW, PRASAT_AMP = 32, 5
# Google Sheet ID/gid come ONLY from Streamlit secrets [bite_sheet] — the repo is public, so the
# link-shared patient-level sheet must never be referenced in code.
SHEET_ID = ""
GID = "0"

ANIMALS = ["สุนัข", "แมว/สัตว์เลี้ยงลูกด้วยนมอื่น", "ไม่ระบุสัตว์ (Z20.3)"]
ANIMAL_COLORS = {ANIMALS[0]: "#f4a261", ANIMALS[1]: "#8d6cab", ANIMALS[2]: "#adb5bd"}

# mutually exclusive vaccine status built from the two flags
STATUS = ["เคยได้รับวัคซีนมาก่อน", "ฉีดครั้งแรกในครั้งนี้", "ไม่เคยได้รับวัคซีนเลย"]
STATUS_COLORS = {STATUS[0]: "#2a9d8f", STATUS[1]: "#e9c46a", STATUS[2]: "#d62828"}

SEX = {1: "ชาย", 2: "หญิง"}
AGE_BINS = [-1, 4, 9, 14, 24, 44, 59, 200]
AGE_LABELS = ["0-4", "5-9", "10-14", "15-24", "25-44", "45-59", "60+"]

PLACE = {"0": "บ้าน", "1": "สถานสงเคราะห์/หอพัก", "2": "โรงเรียน/สถานที่ราชการ", "3": "สนามกีฬา",
         "4": "ถนน/ทางหลวง", "5": "ร้านค้า/ที่บริการ", "6": "โรงงาน/ก่อสร้าง", "7": "ไร่นา/ฟาร์ม",
         "8": "สถานที่อื่นที่ระบุ", "9": "ไม่ระบุสถานที่"}
ACTIVITY = {"0": "เล่นกีฬา", "1": "พักผ่อน/สันทนาการ", "2": "ทำงานมีรายได้", "3": "ทำงานอื่นๆ",
            "4": "พักผ่อน/กิน/นอน/กิจวัตร", "8": "กิจกรรมอื่นที่ระบุ", "9": "ไม่ระบุกิจกรรม"}
TH_MONTH = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
TH_DOW = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]


def _animal(codes: str) -> str:
    codes = str(codes).upper()
    if "W54" in codes:
        return ANIMALS[0]
    if "W55" in codes:
        return ANIMALS[1]
    return ANIMALS[2]


def _wcode(codes: str) -> str:
    """First W54/W55 code of the visit ('' if only Z20.3)."""
    for c in str(codes).upper().replace(" ", "").split(","):
        if c.startswith(("W54", "W55")):
            return c
    return ""


def tambon_codes() -> dict[int, str]:
    """tmbpart (1..18) -> Thai tambon name, read from the geojson tam_code (3205xx)."""
    gj = json.loads((DATA_DIR / "prasat_tambon.geojson").read_text(encoding="utf-8"))
    out = {int(f["properties"]["tam_code"][-2:]): f["properties"]["tambon"] for f in gj["features"]}
    return out or {i + 1: t for i, t in enumerate(TAMBONS)}


def _fetch_private_sheet(service_account_info: dict, sheet_id: str, gid: str) -> pd.DataFrame:
    """Download a *private* Google Sheet tab as CSV using a service account.

    The sheet must be shared (Viewer) with the service account's `client_email`.
    """
    from io import StringIO

    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        dict(service_account_info), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    r = AuthorizedSession(creds).get(url, timeout=60)
    if r.status_code != 200 or r.text.lstrip().startswith("<"):
        raise PermissionError(f"อ่าน Google Sheet ไม่ได้ (HTTP {r.status_code}) — "
                              f"ตรวจสอบว่าแชร์ชีตให้ {service_account_info.get('client_email')} แล้ว")
    return pd.read_csv(StringIO(r.content.decode("utf-8-sig")))


def read_source(secrets=None) -> tuple[pd.DataFrame, str]:
    """Source order: service account (private sheet) → link-shared sheet export → local CSV."""
    errors = []
    cfg = {}
    if secrets is not None:
        try:
            cfg = dict(secrets.get("bite_sheet", {}))
            if "gcp_service_account" in secrets:
                sid, gid = cfg.get("sheet_id", SHEET_ID), str(cfg.get("gid", GID))
                return _fetch_private_sheet(secrets["gcp_service_account"], sid, gid), "Google Sheets (ส่วนตัว)"
        except Exception as e:  # noqa: BLE001
            errors.append(f"{type(e).__name__}: {e}")
    sid, gid = cfg.get("sheet_id", SHEET_ID), str(cfg.get("gid", GID))
    if sid:
        try:
            url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
            df = pd.read_csv(url, encoding="utf-8-sig")
            if "vstdate" not in df.columns:
                raise ValueError("ไม่พบคอลัมน์ vstdate ในชีต")
            return df, "Google Sheets (ออนไลน์)"
        except Exception as e:  # noqa: BLE001
            errors.append(f"{type(e).__name__}: {e}")
    path = next((p for p in CANDIDATES if p.exists()), None)
    if path is not None:
        note = "ไฟล์ CSV ในเครื่อง" + (f" (เชื่อม Google Sheet ไม่ได้: {errors[0]})" if errors else "")
        return pd.read_csv(path), note
    raise FileNotFoundError("ไม่พบข้อมูลผู้ถูกสัตว์กัด: ยังไม่ได้ตั้งค่า [bite_sheet] sheet_id / gid ใน Streamlit secrets "
                            f"และไม่พบไฟล์ {FILE_NAME}" + (f" · {errors[0]}" if errors else ""))


def load(raw: pd.DataFrame | None = None) -> pd.DataFrame:
    df = (raw if raw is not None else read_source()[0]).copy()
    df.columns = [c.strip() for c in df.columns]
    df["date"] = pd.to_datetime(df["vstdate"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    for c in ("age_at_visit", "sex", "chwpart", "amppart", "tmbpart", "moopart"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["icd10_codes"] = df["icd10_codes"].fillna("").astype(str)
    for c in ("had_prior_vaccine", "got_pep_this_episode", "ever_vaccinated_lifetime"):
        df[c] = df[c].astype(str).str.lower().isin(["true", "1", "yes"])

    df["animal"] = df["icd10_codes"].map(_animal)
    w = df["icd10_codes"].map(_wcode)
    df["place"] = w.str[3:4].map(PLACE).fillna("ไม่ระบุสถานที่")
    df["activity"] = w.str[4:5].map(ACTIVITY).fillna("ไม่ระบุกิจกรรม")

    df["status"] = STATUS[1]
    df.loc[df["had_prior_vaccine"], "status"] = STATUS[0]
    df.loc[~df["ever_vaccinated_lifetime"], "status"] = STATUS[2]

    last = pd.to_datetime(df["last_vaccine_date_before_bite"], errors="coerce")
    df["years_since_last_vax"] = (df["date"] - last).dt.days / 365.25

    df["sex_th"] = df["sex"].map(SEX).fillna("ไม่ระบุ")
    df["age_group"] = pd.cut(df["age_at_visit"], AGE_BINS, labels=AGE_LABELS)
    df["hour"] = pd.to_timedelta(df["vsttime"], errors="coerce").dt.components.hours
    df["dow"] = df["date"].dt.dayofweek.map(dict(enumerate(TH_DOW)))
    df["month_num"] = df["date"].dt.month
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df["quarter"] = df["date"].dt.to_period("Q").dt.to_timestamp()
    # Thai fiscal year (ปีงบประมาณ, Oct-Sep) in Buddhist Era
    df["fy"] = df["date"].dt.year + 543 + (df["date"].dt.month >= 10).astype(int)
    df["year_be"] = df["date"].dt.year + 543

    names = tambon_codes()
    in_prasat = (df["chwpart"] == PRASAT_CHW) & (df["amppart"] == PRASAT_AMP)
    df["tambon"] = df["tmbpart"].map(names).where(in_prasat)
    df["in_prasat"] = in_prasat & df["tambon"].notna()
    return df


def incidence_by_tambon(df: pd.DataFrame, years: float) -> pd.DataFrame:
    """Episodes and annualised incidence per 100,000 registered population, all 18 tambons."""
    d = df[df["in_prasat"]]
    cnt = d.groupby("tambon").size().rename("episodes")
    by_a = d.pivot_table(index="tambon", columns="animal", aggfunc="size", fill_value=0)
    prior = d.groupby("tambon")["had_prior_vaccine"].mean().mul(100).rename("pct_prior")
    out = (pd.DataFrame({"tambon": TAMBONS}).merge(POPULATION[["tambon", "pop_total"]], on="tambon", how="left")
           .merge(cnt, on="tambon", how="left").merge(by_a, on="tambon", how="left")
           .merge(prior, on="tambon", how="left"))
    for a in ANIMALS:
        if a not in out:
            out[a] = 0
    out = out.fillna({"episodes": 0, "pct_prior": 0, **{a: 0 for a in ANIMALS}})
    yrs = max(years, 1e-9)
    out["incidence"] = out["episodes"] / out["pop_total"] * 100_000 / yrs
    return out
