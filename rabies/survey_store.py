"""Storage for the in-app household survey form (แบบบันทึกสำรวจครัวเรือน) — contains PERSONAL DATA.

Two linked tables (1 household → N bitten persons, joined by `household_id`):
    households : one row per surveyed house (same questions as the original Google Form)
    persons    : one row per person bitten / scratched / attacked by a mammal (name, CID, phone, ...)

Backends (chosen automatically, first match wins):
  1. Google Apps Script web app (RECOMMENDED) — secrets [survey_apps_script] url + token.
     The script (scripts/survey_apps_script.gs) is bound to a PRIVATE sheet; no sheet ID and no
     service account are needed by the app. Requests without the right token are rejected.
  2. Private Google Sheet via service account — secrets [survey_sheet] sheet_id AND [gcp_service_account].
     The sheet must be shared as *Editor* with the service account's client_email. Tabs `households`
     and `persons` (with header rows) are created automatically.
  3. Local SQLite file      — data/survey_entries.sqlite (git-ignored). Fine for local use, but on
     Streamlit Cloud the disk is ephemeral → data is lost on restart. Use a Google Sheet there.

The repo is public: never hard-code the sheet ID or any personal data here.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date

from rabies.cleaning import DATA_DIR

SQLITE_PATH = DATA_DIR / "survey_entries.sqlite"

HOUSEHOLD_COLS = [
    "household_id", "submitted_at", "surveyor", "tambon", "moo", "house_no", "owner_phone",
    "residents", "people_bitten", "people_vaccinated", "dogs_total", "dogs_vaccinated",
    "cats_total", "cats_vaccinated", "other_mammals", "consent",
]
PERSON_COLS = [
    "household_id", "person_no", "submitted_at", "tambon", "moo", "house_no",
    "first_name", "last_name", "cid", "age", "sex", "phone", "animal", "animal_other",
    "bite_date", "days_since_bite", "period", "vaccine_status",
]
TABLES = {"households": HOUSEHOLD_COLS, "persons": PERSON_COLS}

# ----------------------------------------------------------------------------- choices
SEX = ["ชาย", "หญิง"]
ANIMALS = ["สุนัข", "แมว", "หนู", "ลิง", "กระรอก/กระแต", "วัว/ควาย", "สุกร", "อื่นๆ (ระบุ)"]
VACCINE_STATUS = ["ได้รับครบ", "อยู่ระหว่างการฉีด", "ยังไม่ได้รับ"]
PERIODS = ["ภายใน 7 วัน", "8–30 วัน", "1–3 เดือน", "มากกว่า 3–6 เดือน", "มากกว่า 6–12 เดือน", "มากกว่า 1 ปี"]


def period_from_days(days: int) -> str:
    if days <= 7:
        return PERIODS[0]
    if days <= 30:
        return PERIODS[1]
    if days <= 90:
        return PERIODS[2]
    if days <= 180:
        return PERIODS[3]
    if days <= 365:
        return PERIODS[4]
    return PERIODS[5]


# ----------------------------------------------------------------------------- validation
def digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def valid_cid(cid: str) -> bool:
    """Thai national ID: 13 digits, last digit = (11 - Σ d_i·(13-i) mod 11) mod 10."""
    if not re.fullmatch(r"\d{13}", cid) or cid[0] == "0":
        return False
    s = sum(int(cid[i]) * (13 - i) for i in range(12))
    return (11 - s % 11) % 10 == int(cid[12])


def valid_phone(p: str) -> bool:
    """Thai phone: 9 digits (landline 0X-XXX-XXXX) or 10 digits (mobile 0X-XXXX-XXXX)."""
    return bool(re.fullmatch(r"0\d{8,9}", p))


def mask_cid(cid: str) -> str:
    return f"{cid[:1]}-xxxx-xxxxx-{cid[-3:-1]}-{cid[-1]}" if len(cid) == 13 else (cid or "-")


def mask_phone(p: str) -> str:
    return f"{p[:3]}-xxx-{p[-3:]}" if len(p) >= 9 else (p or "-")


# ----------------------------------------------------------------------------- backends
def _secrets():
    try:
        import streamlit as st
        return st.secrets
    except Exception:  # noqa: BLE001
        return {}


def backend_name() -> str:
    s = _secrets()
    try:
        a = s.get("survey_apps_script", {})
        if a.get("url") and a.get("token"):
            return "apps_script"
        if s.get("survey_sheet", {}).get("sheet_id") and s.get("gcp_service_account"):
            return "gsheet"
    except Exception:  # noqa: BLE001  (no secrets.toml at all)
        pass
    return "sqlite"


BACKEND_LABEL = {"apps_script": "Google Sheet", "gsheet": "Google Sheet", "sqlite": "ไฟล์ในเครื่อง"}


def _str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


class _SheetStore:
    API = "https://sheets.googleapis.com/v4/spreadsheets"

    def __init__(self, sa_info: dict, sheet_id: str):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_info(
            dict(sa_info), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        self.s = AuthorizedSession(creds)
        self.id = sheet_id
        self.email = sa_info.get("client_email")

    def _check(self, r):
        if r.status_code != 200:
            raise PermissionError(f"บันทึกลง Google Sheet ไม่ได้ (HTTP {r.status_code}) — ตรวจสอบว่าแชร์ชีต"
                                  f"ให้ {self.email} เป็น 'ผู้แก้ไข' แล้ว · {r.text[:200]}")
        return r.json()

    def _ensure_tabs(self):
        meta = self._check(self.s.get(f"{self.API}/{self.id}", params={"fields": "sheets.properties.title"},
                                      timeout=30))
        have = {sh["properties"]["title"] for sh in meta.get("sheets", [])}
        missing = [t for t in TABLES if t not in have]
        if missing:
            self._check(self.s.post(f"{self.API}/{self.id}:batchUpdate", timeout=30, json={
                "requests": [{"addSheet": {"properties": {"title": t}}} for t in missing]}))
        for t, cols in TABLES.items():
            head = self._check(self.s.get(f"{self.API}/{self.id}/values/{t}!1:1", timeout=30))
            if not head.get("values"):
                self._append(t, [cols])

    def _append(self, tab: str, rows: list[list[str]]):
        self._check(self.s.post(
            f"{self.API}/{self.id}/values/{tab}!A1:append", timeout=30,
            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"}, json={"values": rows}))

    def save(self, household: dict, persons: list[dict]):
        self._ensure_tabs()
        self._append("households", [[_str(household.get(c)) for c in HOUSEHOLD_COLS]])
        if persons:
            self._append("persons", [[_str(p.get(c)) for c in PERSON_COLS] for p in persons])


class _SqliteStore:
    def __init__(self, path=SQLITE_PATH):
        path.parent.mkdir(exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as con:
            for t, cols in TABLES.items():
                con.execute(f"CREATE TABLE IF NOT EXISTS {t} ({', '.join(f'{c} TEXT' for c in cols)})")

    def save(self, household: dict, persons: list[dict]):
        with sqlite3.connect(self.path) as con:  # one transaction → household + persons saved together
            con.execute(f"INSERT INTO households VALUES ({','.join('?' * len(HOUSEHOLD_COLS))})",
                        [_str(household.get(c)) for c in HOUSEHOLD_COLS])
            con.executemany(f"INSERT INTO persons VALUES ({','.join('?' * len(PERSON_COLS))})",
                            [[_str(p.get(c)) for c in PERSON_COLS] for p in persons])

    def count(self) -> int:
        with sqlite3.connect(self.path) as con:
            return con.execute("SELECT COUNT(*) FROM households").fetchone()[0]


class _AppsScriptStore:
    """POST {token, tables} to the Apps Script web app bound to the private sheet.

    Apps Script answers a POST with a 302 to script.googleusercontent.com; urllib follows it with a
    GET (body dropped), which is exactly what Google expects, and the JSON result comes back.
    """

    def __init__(self, url: str, token: str):
        self.url, self.token = url, token

    def save(self, household: dict, persons: list[dict]):
        import json
        import urllib.request

        payload = {"token": self.token, "tables": {
            "households": {"columns": HOUSEHOLD_COLS,
                           "rows": [[_str(household.get(c)) for c in HOUSEHOLD_COLS]]},
            "persons": {"columns": PERSON_COLS,
                        "rows": [[_str(p.get(c)) for c in PERSON_COLS] for p in persons]},
        }}
        req = urllib.request.Request(self.url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            raise ConnectionError(f"เชื่อมต่อ Apps Script ไม่ได้: {e}") from None
        try:
            res = json.loads(text)
        except ValueError:
            raise ConnectionError("Apps Script ไม่ได้ตอบกลับเป็น JSON — ตรวจสอบว่า Deploy เป็น Web app, "
                                  "Who has access = Anyone และใช้ URL ที่ลงท้ายด้วย /exec") from None
        if not res.get("ok"):
            err = res.get("error")
            raise PermissionError("TOKEN ไม่ตรงกับ Script Properties" if err == "unauthorized"
                                  else f"Apps Script error: {err}")


def get_store():
    name = backend_name()
    s = _secrets()
    if name == "apps_script":
        return _AppsScriptStore(s["survey_apps_script"]["url"], s["survey_apps_script"]["token"])
    if name == "gsheet":
        return _SheetStore(s["gcp_service_account"], s["survey_sheet"]["sheet_id"])
    return _SqliteStore()


def save(household: dict, persons: list[dict]) -> str:
    """Persist one household + its bitten persons. Returns the backend used."""
    get_store().save(household, persons)
    return backend_name()
