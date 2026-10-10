import plotly.express as px
import streamlit as st

from rabies import ui

st.title("🧹 คุณภาพข้อมูลและการทำความสะอาดข้อมูล")
st.caption(f"แหล่งข้อมูล: {st.session_state.get('source_note', '')}")

stats = st.session_state["stats"]
log = st.session_state["df_log"]
excluded = st.session_state["df_excluded"]
clean = st.session_state["df_all"]
raw = st.session_state["df_raw"]


def _mask(v) -> str:
    d = "".join(ch for ch in str(v) if ch.isdigit())
    return f"{d[:3]}-xxx-{d[-3:]}" if len(d) >= 6 else ("xxx" if d else "")


# 🔒 public site: never expose full phone numbers
raw = raw.copy()
for col in [c for c in raw.columns if "เบอร์" in c or "phone" in c.lower()]:
    raw[col] = raw[col].map(_mask)
clean = clean.drop(columns=["phone"], errors="ignore")
log = log.copy()
is_phone = log["คอลัมน์"] == "เบอร์โทร"
log.loc[is_phone, "ค่าเดิม"] = log.loc[is_phone, "ค่าเดิม"].map(_mask)
log.loc[is_phone, "ค่าใหม่"] = log.loc[is_phone, "ค่าใหม่"].map(_mask)

c = st.columns(4)
ui.kpi(c[0], "📥 แถวข้อมูลดิบ", stats["raw_rows"], "จาก Google Sheets", ui.COLORS["people"])
ui.kpi(c[1], "✅ แถวที่ใช้วิเคราะห์", stats["clean_rows"], ui.fmt_pct(stats["clean_rows"], stats["raw_rows"]), ui.COLORS["vax"])
ui.kpi(c[2], "🗑️ แถวที่ตัดออก", stats["excluded"] + stats["empty_rows"], "ซ้ำ / ทดสอบ / ไม่สมบูรณ์", ui.COLORS["unvax"])
ui.kpi(c[3], "🛠️ จำนวนการแก้ไขค่า", stats["fixes"], "ทุกการเปลี่ยนแปลงถูกบันทึก", ui.COLORS["house"])

with st.expander("📖 กฎการทำความสะอาดข้อมูล (Cleaning rules)", expanded=False):
    st.markdown("""
1. **ตัวเลข** — ตัดหน่วยและข้อความออก (เช่น `2 คน`, `5 ตัว`, `4ตัง` → 2, 5, 4), แปลงเลขไทย (๐-๙) และคำ (หนึ่ง, สอง ...)
2. **ค่าว่าง/ไม่มี** — `-`, `--`, `_`, `ไม่มี`, ช่องว่าง → 0
3. **ตำบล** — ตัดคำว่า "ต./ตำบล" และจับคู่ชื่อที่สะกดใกล้เคียงกับ 18 ตำบลของอำเภอปราสาท
4. **หมู่ที่** — ดึงเฉพาะตัวเลข (เช่น `หมู่ 9`, `ม.9` → 9)
5. **บ้านเลขที่** — ดึงเฉพาะเลขที่บ้าน ตัดที่อยู่ส่วนเกิน (เช่น `55ม.3ต.กังแอน...` → 55)
6. **เบอร์โทร** — เก็บเฉพาะตัวเลข เติม 0 นำหน้าถ้าหาย, แปลง +66 → 0
7. **ความสอดคล้อง** — สัตว์ที่ฉีดวัคซีนต้องไม่เกินจำนวนทั้งหมด; ผู้ถูกกัด + ผู้ฉีดวัคซีน ต้องไม่เกินผู้อาศัย
8. **ข้อมูลทดสอบ** — แถวที่มีคำว่า "ทดสอบ/test" ถูกตัดออก
9. **ข้อมูลซ้ำ** — บ้านเดียวกัน (ตำบล + หมู่ + บ้านเลขที่) เก็บเฉพาะรายการที่ส่งล่าสุด
10. **ไม่สมบูรณ์** — ไม่ทราบตำบล หรือจำนวนผู้อาศัย = 0 ถูกตัดออก
""")

st.subheader("🗑️ แถวที่ถูกตัดออก")
if excluded.empty:
    st.success("ไม่มีแถวที่ถูกตัดออก")
else:
    show = excluded[["row_id", "exclude_reason", "timestamp", "tambon", "moo", "house_no", "residents"]]
    st.dataframe(ui.to_thai(show).rename(columns={"row_id": "แถวต้นฉบับ", "exclude_reason": "เหตุผล"}),
                 width="stretch", hide_index=True)

st.subheader("🛠️ บันทึกการแก้ไขค่า")
if log.empty:
    st.success("ไม่มีการแก้ไขค่า")
else:
    counts = log["ปัญหา"].value_counts().reset_index()
    counts.columns = ["ปัญหา", "จำนวน"]
    fig = px.bar(counts, x="จำนวน", y="ปัญหา", orientation="h", text="จำนวน",
                 color_discrete_sequence=[ui.COLORS["dog"]])
    fig.update_layout(height=60 + 38 * len(counts), margin=dict(t=10, b=10), yaxis_title="")
    st.plotly_chart(fig, width="stretch")
    issues = st.multiselect("กรองตามประเภทปัญหา", counts["ปัญหา"].tolist(), placeholder="ทุกประเภท")
    view = log if not issues else log[log["ปัญหา"].isin(issues)]
    st.dataframe(view.astype(str), width="stretch", hide_index=True)

st.divider()
st.subheader("⬇️ ดาวน์โหลดข้อมูล")
c1, c2, c3 = st.columns(3)
c1.download_button("ข้อมูลที่ทำความสะอาดแล้ว (CSV)", ui.csv_bytes(clean.drop(columns=["house_key"], errors="ignore")),
                   "clean_survey.csv", "text/csv", width="stretch")
c2.download_button("บันทึกการแก้ไข (CSV)", ui.csv_bytes(log), "cleaning_log.csv", "text/csv",
                   width="stretch")
c3.download_button("ข้อมูลดิบ (CSV)", ui.csv_bytes(raw), "raw_survey.csv", "text/csv", width="stretch")

with st.expander("ดูข้อมูลดิบ"):
    st.dataframe(raw, width="stretch", hide_index=True)
