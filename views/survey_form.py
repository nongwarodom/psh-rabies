"""📝 แบบบันทึกสำรวจครัวเรือน — in-app version of the Google Form + per-person details of everyone
bitten / scratched / attacked by a mammal. Contains PERSONAL DATA (name, CID, phone) → see rabies/survey_store.py.
"""
import uuid
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from rabies import survey_store as store
from rabies.cleaning import TAMBONS

st.title("📝 แบบบันทึกสำรวจครัวเรือน")
st.caption("แบบสำรวจข้อมูลประชากรและสัตว์เลี้ยงในครัวเรือนเพื่อเฝ้าระวังโรคพิษสุนัขบ้า อำเภอปราสาท จังหวัดสุรินทร์ "
           "· พร้อมข้อมูลรายบุคคลของผู้ที่ถูกสัตว์เลี้ยงลูกด้วยนม กัด/ข่วน/ทำร้าย ในระยะ 1 ปี")

# ----------------------------------------------------------------------------- access control
try:
    PASSWORD = st.secrets.get("survey_form", {}).get("password", "")
except Exception:  # noqa: BLE001  (no secrets.toml)
    PASSWORD = ""
if PASSWORD and not st.session_state.get("survey_auth"):
    with st.form("survey_login"):
        st.markdown("🔒 หน้านี้บันทึก **ข้อมูลส่วนบุคคล** — กรุณาใส่รหัสผ่านสำหรับเจ้าหน้าที่/อสม.")
        pw = st.text_input("รหัสผ่าน", type="password")
        if st.form_submit_button("เข้าสู่ระบบ", type="primary"):
            if pw == PASSWORD:
                st.session_state["survey_auth"] = True
                st.rerun()
            st.error("รหัสผ่านไม่ถูกต้อง")
    st.stop()

backend = store.backend_name()
if backend == "sqlite":
    st.warning("⚠️ ยังไม่ได้เชื่อมต่อ Google Sheet (`[survey_apps_script]` url + token ใน secrets) — "
               "ข้อมูลจะบันทึกลงไฟล์ในเครื่อง `data/survey_entries.sqlite` ซึ่ง **จะหายเมื่อแอปบน Streamlit Cloud รีสตาร์ท**")
if not PASSWORD:
    st.info("ℹ️ ยังไม่ได้ตั้งรหัสผ่านหน้าแบบบันทึก (`[survey_form] password` ใน secrets) — ใครก็ส่งข้อมูลได้ "
            "(แต่หน้านี้ไม่แสดงข้อมูลส่วนบุคคลที่บันทึกไว้)")

# ----------------------------------------------------------------------------- helpers
nonce = st.session_state.setdefault("survey_nonce", 0)  # bump → every widget resets after a save


def k(name: str) -> str:
    return f"sv{nonce}_{name}"


if msg := st.session_state.pop("survey_saved_msg", None):
    st.success(msg)
    st.balloons()

TODAY = date.today()
count = dict(min_value=0, max_value=200, step=1, value=0)

# ----------------------------------------------------------------------------- 1. household
st.subheader("🏠 1. ข้อมูลครัวเรือน")
c = st.columns([2, 2, 1, 1.3])
surveyor = c[0].text_input("ชื่อผู้สำรวจ / อสม.", key=k("surveyor"))
tambon = c[1].selectbox("ตำบล *", TAMBONS, index=None, placeholder="เลือกตำบล", key=k("tambon"))
moo = c[2].selectbox("หมู่ที่ *", list(range(1, 21)), index=None, placeholder="หมู่", key=k("moo"))
house_no = c[3].text_input("บ้านเลขที่ *", key=k("house_no"), placeholder="เช่น 123/4")
c = st.columns(3)
owner_phone = c[0].text_input("เบอร์โทรเจ้าของบ้าน", key=k("owner_phone"), max_chars=12, placeholder="0812345678")
residents = c[1].number_input("จำนวนผู้อาศัยในบ้าน (คน) *", key=k("residents"), **{**count, "min_value": 1, "value": 1})
people_vaccinated = c[2].number_input("จำนวนผู้ที่เคยฉีดวัคซีนพิษสุนัขบ้าแล้ว (คน)", key=k("pvax"), **count)

# ----------------------------------------------------------------------------- 2. animals
st.subheader("🐶 2. สัตว์เลี้ยงในบ้าน")
c = st.columns(5)
dogs_total = c[0].number_input("สุนัขทั้งหมด (ตัว)", key=k("dogs"), **count)
dogs_vax = c[1].number_input("สุนัขที่ได้รับวัคซีนแล้ว (ตัว)", key=k("dogs_vax"), **count)
cats_total = c[2].number_input("แมวทั้งหมด (ตัว)", key=k("cats"), **count)
cats_vax = c[3].number_input("แมวที่ได้รับวัคซีนแล้ว (ตัว)", key=k("cats_vax"), **count)
other_mammals = c[4].number_input("สัตว์เลี้ยงลูกด้วยนมอื่นๆ (ตัว)", key=k("other"), **count)

# ----------------------------------------------------------------------------- 3. bitten persons
st.subheader("🩸 3. ผู้ที่ถูกสัตว์เลี้ยงลูกด้วยนม กัด/ข่วน/ทำร้าย ในระยะ 1 ปี")
n_bitten = st.number_input("จำนวนผู้ที่ถูกสัตว์กัด/ข่วน/ทำร้าย ภายใน 1 ปี (คน) — ใส่ 0 หากไม่มี",
                           key=k("n_bitten"), min_value=0, max_value=30, step=1, value=0)

persons_raw = []
for i in range(int(n_bitten)):
    p = lambda name, i=i: k(f"p{i}_{name}")  # noqa: E731
    with st.container(border=True):
        st.markdown(f"**👤 คนที่ {i + 1}**")
        c = st.columns([2, 2, 2.2])
        first = c[0].text_input("ชื่อ *", key=p("first"))
        last = c[1].text_input("นามสกุล *", key=p("last"))
        with c[2]:
            no_cid = st.checkbox("ไม่ทราบ/ไม่มีเลขบัตรประชาชน", key=p("no_cid"))
            cid = st.text_input("เลขบัตรประชาชน (13 หลัก) *", key=p("cid"), max_chars=17, disabled=no_cid,
                                placeholder="1234567890123", label_visibility="collapsed")
        c = st.columns([1, 1.3, 2, 2.5])
        age = c[0].number_input("อายุ (ปี) *", key=p("age"), min_value=0, max_value=120, step=1, value=None)
        sex = c[1].radio("เพศ *", store.SEX, index=None, key=p("sex"), horizontal=True)
        phone = c[2].text_input("เบอร์โทรติดต่อ", key=p("phone"), max_chars=12, placeholder="0812345678")
        with c[3]:
            animal = st.selectbox("สัตว์ที่กัด/ข่วน/ทำร้าย *", store.ANIMALS, index=None,
                                  placeholder="เลือกชนิดสัตว์", key=p("animal"))
            animal_other = (st.text_input("ระบุชนิดสัตว์ *", key=p("animal_other"))
                            if animal == store.ANIMALS[-1] else "")
        c = st.columns([1.3, 2, 2.5])
        with c[0]:
            know_date = st.toggle("ทราบวันที่ถูกกัด", value=True, key=p("know_date"))
        with c[1]:
            if know_date:
                bite_date = st.date_input("วันที่ถูกกัด/ข่วน/ทำร้าย *", value=None, key=p("bite_date"),
                                          min_value=TODAY - timedelta(days=730), max_value=TODAY,
                                          format="DD/MM/YYYY")
                days = (TODAY - bite_date).days if bite_date else None
                period = store.period_from_days(days) if days is not None else None
                if days is not None:
                    st.caption(f"⏱️ ผ่านมาแล้ว **{days} วัน** ({period})")
            else:
                bite_date, days = None, None
                period = st.selectbox("ระยะเวลาจากวันที่ถูกกัด (โดยประมาณ) *", store.PERIODS, index=None,
                                      placeholder="เลือกช่วงเวลา", key=p("period"))
        vaccine = c[2].radio("ได้รับวัคซีนพิษสุนัขบ้าหรือยัง *", store.VACCINE_STATUS, index=None,
                             key=p("vaccine"), horizontal=True)
        if vaccine == "ยังไม่ได้รับ" and days is not None and days <= 30:
            st.error("🚨 ถูกกัดภายใน 30 วันและยังไม่ได้รับวัคซีน — แนะนำให้ไปรับวัคซีนที่ รพ./รพ.สต. โดยเร็ว")
        persons_raw.append(dict(person_no=i + 1, first_name=first.strip(), last_name=last.strip(),
                                cid="" if no_cid else store.digits(cid), no_cid=no_cid, age=age, sex=sex,
                                phone=store.digits(phone), animal=animal, animal_other=animal_other.strip(),
                                bite_date=bite_date, days_since_bite=days, period=period, vaccine_status=vaccine))

# ----------------------------------------------------------------------------- 4. consent + submit
st.subheader("✅ 4. ยืนยันและบันทึก")
consent = st.checkbox("ผู้ให้ข้อมูลได้รับทราบและยินยอมให้เก็บข้อมูลส่วนบุคคล (ชื่อ เลขบัตรประชาชน เบอร์โทร) "
                      "เพื่อใช้ในการติดตามและป้องกันโรคพิษสุนัขบ้าของหน่วยงานสาธารณสุขเท่านั้น (พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล)",
                      key=k("consent"))


def validate() -> list[str]:
    e = []
    if not tambon:
        e.append("กรุณาเลือกตำบล")
    if not moo:
        e.append("กรุณาเลือกหมู่ที่")
    if not house_no.strip():
        e.append("กรุณาใส่บ้านเลขที่")
    if owner_phone.strip() and not store.valid_phone(store.digits(owner_phone)):
        e.append("เบอร์โทรเจ้าของบ้านไม่ถูกต้อง (ต้องขึ้นต้นด้วย 0 และมี 9–10 หลัก)")
    if dogs_vax > dogs_total:
        e.append("จำนวนสุนัขที่ได้รับวัคซีน มากกว่าจำนวนสุนัขทั้งหมด")
    if cats_vax > cats_total:
        e.append("จำนวนแมวที่ได้รับวัคซีน มากกว่าจำนวนแมวทั้งหมด")
    if people_vaccinated > residents:
        e.append("จำนวนผู้ที่เคยฉีดวัคซีน มากกว่าจำนวนผู้อาศัยในบ้าน")
    if n_bitten > residents:
        e.append("จำนวนผู้ถูกกัด มากกว่าจำนวนผู้อาศัยในบ้าน")
    seen = set()
    for q in persons_raw:
        who = f"คนที่ {q['person_no']}"
        miss = [lbl for lbl, ok in [("ชื่อ", q["first_name"]), ("นามสกุล", q["last_name"]),
                                    ("อายุ", q["age"] is not None), ("เพศ", q["sex"]), ("สัตว์ที่กัด", q["animal"]),
                                    ("ระยะเวลาจากวันที่ถูกกัด", q["period"]), ("สถานะวัคซีน", q["vaccine_status"])]
                if not ok]
        if q["animal"] == store.ANIMALS[-1] and not q["animal_other"]:
            miss.append("ชนิดสัตว์ (อื่นๆ)")
        if miss:
            e.append(f"{who}: กรุณากรอก {', '.join(miss)}")
        if not q["no_cid"]:
            if not q["cid"]:
                e.append(f"{who}: กรุณาใส่เลขบัตรประชาชน หรือเลือก 'ไม่ทราบ/ไม่มีเลขบัตรประชาชน'")
            elif not store.valid_cid(q["cid"]):
                e.append(f"{who}: เลขบัตรประชาชนไม่ถูกต้อง (ตรวจสอบ 13 หลัก/เลขตรวจสอบ)")
            elif q["cid"] in seen:
                e.append(f"{who}: เลขบัตรประชาชนซ้ำกับคนอื่นในบ้านนี้")
            seen.add(q["cid"])
        if q["phone"] and not store.valid_phone(q["phone"]):
            e.append(f"{who}: เบอร์โทรไม่ถูกต้อง (ต้องขึ้นต้นด้วย 0 และมี 9–10 หลัก)")
    if not consent:
        e.append("กรุณายืนยันความยินยอมในการเก็บข้อมูลส่วนบุคคล")
    return e


if st.button("💾 บันทึกข้อมูล", type="primary", width="stretch"):
    errors = validate()
    if errors:
        st.error("**กรุณาแก้ไขข้อมูลต่อไปนี้:**\n\n" + "\n".join(f"- {x}" for x in errors))
    else:
        hid = uuid.uuid4().hex[:12]
        now = pd.Timestamp.now(tz="Asia/Bangkok").strftime("%Y-%m-%d %H:%M:%S")
        loc = dict(household_id=hid, submitted_at=now, tambon=tambon, moo=moo, house_no=house_no.strip())
        household = {**loc, "surveyor": surveyor.strip(), "owner_phone": store.digits(owner_phone),
                     "residents": residents, "people_bitten": int(n_bitten), "people_vaccinated": people_vaccinated,
                     "dogs_total": dogs_total, "dogs_vaccinated": dogs_vax, "cats_total": cats_total,
                     "cats_vaccinated": cats_vax, "other_mammals": other_mammals, "consent": True}
        persons = [{**loc, **{c: q[c] for c in store.PERSON_COLS if c in q}} for q in persons_raw]
        try:
            with st.spinner("กำลังบันทึก..."):
                used = store.save(household, persons)
        except Exception as ex:  # noqa: BLE001
            st.error(f"❌ บันทึกไม่สำเร็จ: {ex}")
        else:
            # keep only a MASKED summary in this browser session (never re-display full personal data)
            st.session_state.setdefault("survey_history", []).insert(0, {
                "เวลา": now[11:], "ตำบล": tambon, "หมู่": moo, "บ้านเลขที่": house_no.strip(),
                "ผู้อาศัย": residents, "ผู้ถูกกัด (คน)": int(n_bitten),
                "รายชื่อ (ปิดบัง)": ", ".join(f"{q['first_name']} {q['last_name'][:1]}. ({store.mask_cid(q['cid'])})"
                                              for q in persons_raw) or "-"})
            where = store.BACKEND_LABEL[used]
            st.session_state["survey_saved_msg"] = (f"✅ บันทึกบ้านเลขที่ {house_no.strip()} หมู่ {moo} ต.{tambon} "
                                                    f"และผู้ถูกกัด {int(n_bitten)} คน ลง{where} เรียบร้อย")
            st.session_state["survey_nonce"] = nonce + 1
            st.rerun()

if hist := st.session_state.get("survey_history"):
    st.divider()
    st.markdown(f"**🗂️ รายการที่บันทึกในรอบนี้ ({len(hist)} ครัวเรือน)** — แสดงแบบปิดบังข้อมูลส่วนบุคคล")
    st.dataframe(pd.DataFrame(hist), hide_index=True, width="stretch")
