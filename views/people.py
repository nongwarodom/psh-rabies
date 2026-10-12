import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from rabies import survey_store, ui

df = ui.filtered()
st.title("🧑‍⚕️ ประชากรและการถูกสุนัขกัด")
st.caption("จำนวน/สัดส่วนผู้ถูกสุนัขกัดหรือข่วนที่ยังไม่ได้รับวัคซีน และผู้ที่เคยได้รับวัคซีนพิษสุนัขบ้าแล้ว")
if ui.empty_guard(df):
    st.stop()

T = df[ui.SUM_COLS].sum()
hh = ui.households(df)
c = st.columns(4)
ui.kpi(c[0], "👥 ผู้ที่สำรวจทั้งหมด", T.residents, f"{hh:,} ครัวเรือน (ทุกแหล่งข้อมูล)", ui.COLORS["people"])
ui.kpi(c[1], "🩸 ถูกกัด/ข่วน ยังไม่ได้รับวัคซีน", T.people_bitten_unvax,
       f"{ui.fmt_pct(T.people_bitten_unvax, T.residents)} ของผู้ที่สำรวจ", ui.COLORS["bitten"])
ui.kpi(c[2], "🏠 ครัวเรือนที่มีผู้ถูกกัด*", T.hh_bitten,
       f"{ui.fmt_pct(T.hh_bitten, T.hh_bite_known)} ของ {T.hh_bite_known:,.0f} ครัวเรือน (*ไม่รวม อสม.)", ui.COLORS["unvax"])
ui.kpi(c[3], "💉 ได้รับวัคซีนแล้ว", T.people_vaccinated,
       f"{ui.fmt_pct(T.people_vaccinated, T.residents)} ของผู้ที่สำรวจ", ui.COLORS["vax"])
st.caption("นิยาม (ข้อมูล อสม.): ได้รับวัคซีน = ฉีดครบชุด + อยู่ระหว่างฉีด · ยังไม่ได้รับวัคซีน = ไม่ครบชุด + ไม่ได้รับวัคซีน")

st.divider()
l, r = st.columns([2, 3])
with l:
    st.subheader("สัดส่วนประชากรตามสถานะ")
    fig = go.Figure(go.Pie(
        labels=["ถูกกัด/ข่วน ยังไม่ฉีดวัคซีน", "เคยฉีดวัคซีนแล้ว", "ไม่เคยถูกกัด/ไม่เคยฉีด"],
        values=[T.people_bitten_unvax, T.people_vaccinated, T.people_other], hole=.5, sort=False,
        marker_colors=[ui.COLORS["bitten"], ui.COLORS["vax"], ui.COLORS["other"]],
        textinfo="value+percent"))
    fig.update_layout(height=400, margin=dict(t=10, b=10), legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(fig, width="stretch")
with r:
    st.subheader("จำนวนประชากรตามสถานะ รายตำบล")
    mode = st.radio("แสดงเป็น", ["จำนวน (คน)", "ร้อยละ (%)"], horizontal=True, key="ppl_mode")
    agg = ui.by_area(df)
    long = agg.melt(id_vars="tambon", value_vars=["people_bitten_unvax", "people_vaccinated", "people_other"],
                    var_name="สถานะ", value_name="คน")
    long["สถานะ"] = long["สถานะ"].map({"people_bitten_unvax": "ถูกกัด ยังไม่ฉีด",
                                       "people_vaccinated": "เคยฉีดแล้ว", "people_other": "อื่นๆ"})
    fig = px.bar(long, x="tambon", y="คน", color="สถานะ", text_auto=True,
                 color_discrete_map={"ถูกกัด ยังไม่ฉีด": ui.COLORS["bitten"], "เคยฉีดแล้ว": ui.COLORS["vax"],
                                     "อื่นๆ": ui.COLORS["other"]}, labels={"tambon": "ตำบล"})
    if mode.startswith("ร้อยละ"):
        fig.update_layout(barnorm="percent", yaxis_title="ร้อยละ")
        fig.update_traces(texttemplate="%{y:.0f}%")
    fig.update_layout(height=400, margin=dict(t=10, b=10), legend_title="")
    st.plotly_chart(fig, width="stretch")

st.subheader("📍 สัดส่วนผู้ถูกกัด/ข่วน (ยังไม่ฉีดวัคซีน) รายหมู่บ้าน")
area = ui.by_area(df, keys=("tambon", "moo"))
area["หมู่บ้าน"] = area["tambon"] + " ม." + area["moo"].astype(str)
area = area.sort_values("pct_bitten_people", ascending=False)
fig = px.bar(area, x="หมู่บ้าน", y="pct_bitten_people", color="tambon",
             text=area["people_bitten_unvax"].map(lambda v: f"{v:.0f} คน"),
             hover_data={"residents": True, "people_bitten_unvax": True, "households": True},
             labels={**ui.TH_COLS, "pct_bitten_people": "% ผู้ถูกกัดต่อประชากร"})
fig.update_layout(height=380, margin=dict(t=10, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("🚨 หมู่บ้านที่มีผู้ถูกกัด/ข่วน แต่ยังไม่ได้ฉีดวัคซีน (ควรติดตาม)")
st.caption("🔒 แสดงเฉพาะยอดรวมระดับตำบล/หมู่บ้าน เพื่อคุ้มครองข้อมูลส่วนบุคคล — เจ้าหน้าที่ดูรายครัวเรือนได้ใน Google Sheet ต้นฉบับ")
vil = ui.by_area(df, keys=("tambon", "moo"))
vil = vil[vil["people_bitten_unvax"] > 0].sort_values("people_bitten_unvax", ascending=False)
cols = ["tambon", "moo", "households", "hh_bitten", "people_bitten_unvax", "residents", "pct_bitten_people"]
if vil.empty:
    st.success("ไม่พบผู้ถูกกัดที่ยังไม่ได้ฉีดวัคซีน")
else:
    out = ui.to_thai(vil[cols].round(1))
    st.dataframe(out, width="stretch", hide_index=True)
    st.download_button("⬇️ ดาวน์โหลด (CSV)", ui.csv_bytes(out), "bitten_by_village.csv", "text/csv")

# ---- per-person details from the in-app form (aggregates only — no names / CID / phone)
st.divider()
st.subheader("🩸 ผู้ถูกสัตว์เลี้ยงลูกด้วยนม กัด/ข่วน/ทำร้าย — ข้อมูลรายบุคคลจากแอปสำรวจ")
persons = st.session_state.get("app_persons")
hh_ids = set(df["household_id"].dropna()) if "household_id" in df else set()
if persons is None or persons.empty or not hh_ids:
    st.info("ยังไม่มีข้อมูลรายบุคคลจากหน้า 📝 บันทึกสำรวจครัวเรือน (ตามตัวกรองที่เลือก)")
else:
    p = persons[persons["household_id"].isin(hh_ids)].copy()
    p["age"] = pd.to_numeric(p["age"], errors="coerce")
    p["days_since_bite"] = pd.to_numeric(p["days_since_bite"], errors="coerce")
    p["animal"] = p["animal"].where(p["animal"] != survey_store.ANIMALS[-1],
                                    "อื่นๆ: " + p["animal_other"].fillna("").astype(str))
    n = len(p)
    unvax = int((p["vaccine_status"] == "ยังไม่ได้รับ").sum())
    urgent = int(((p["vaccine_status"] == "ยังไม่ได้รับ") & (p["days_since_bite"] <= 30)).sum())
    c = st.columns(4)
    ui.kpi(c[0], "🩸 ผู้ถูกกัด/ข่วน/ทำร้าย", n, f"จาก {p['household_id'].nunique()} ครัวเรือน", ui.COLORS["bitten"])
    ui.kpi(c[1], "✅ ได้รับวัคซีนครบ", int((p["vaccine_status"] == "ได้รับครบ").sum()),
           ui.fmt_pct((p["vaccine_status"] == "ได้รับครบ").sum(), n), ui.COLORS["vax"])
    ui.kpi(c[2], "❌ ยังไม่ได้รับวัคซีน", unvax, ui.fmt_pct(unvax, n), ui.COLORS["unvax"])
    ui.kpi(c[3], "🚨 ถูกกัด ≤30 วัน & ยังไม่ได้รับ", urgent, "ควรติดตามให้ไปรับวัคซีนโดยเร็ว", "#9d0208")

    vax_colors = {"ได้รับครบ": ui.COLORS["vax"], "อยู่ระหว่างการฉีด": "#f4a261", "ยังไม่ได้รับ": ui.COLORS["bitten"]}
    l, r = st.columns(2)
    with l:
        st.markdown("**💉 สถานะวัคซีน**")
        vc = p["vaccine_status"].value_counts().reindex(survey_store.VACCINE_STATUS, fill_value=0)
        fig = go.Figure(go.Pie(labels=vc.index, values=vc.values, hole=.55, sort=False, textinfo="value+percent",
                               marker_colors=[vax_colors[s] for s in vc.index]))
        fig.update_layout(height=340, margin=dict(t=10, b=10), legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig, width="stretch")
    with r:
        st.markdown("**🐾 สัตว์ที่กัด/ข่วน/ทำร้าย × สถานะวัคซีน**")
        a = p.groupby(["animal", "vaccine_status"]).size().reset_index(name="คน")
        fig = px.bar(a, y="animal", x="คน", color="vaccine_status", orientation="h", text_auto=True,
                     color_discrete_map=vax_colors, labels={"animal": "", "vaccine_status": "สถานะวัคซีน"})
        fig.update_layout(height=340, margin=dict(t=10, b=10), legend=dict(title="", orientation="h", y=-0.2),
                          yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
    l, r = st.columns(2)
    with l:
        st.markdown("**⏱️ ระยะเวลาจากวันที่ถูกกัด × สถานะวัคซีน**")
        a = p.groupby(["period", "vaccine_status"]).size().reset_index(name="คน")
        fig = px.bar(a, x="period", y="คน", color="vaccine_status", text_auto=True, color_discrete_map=vax_colors,
                     category_orders={"period": survey_store.PERIODS},
                     labels={"period": "", "vaccine_status": "สถานะวัคซีน"})
        fig.update_layout(height=340, margin=dict(t=10, b=10), legend=dict(title="", orientation="h", y=-0.25))
        st.plotly_chart(fig, width="stretch")
    with r:
        st.markdown("**👥 กลุ่มอายุ × เพศ**")
        p["กลุ่มอายุ"] = pd.cut(p["age"], [-1, 4, 9, 14, 24, 44, 59, 200],
                                labels=["0-4", "5-9", "10-14", "15-24", "25-44", "45-59", "60+"])
        a = p.groupby(["กลุ่มอายุ", "sex"], observed=False).size().reset_index(name="คน")
        fig = px.bar(a, x="กลุ่มอายุ", y="คน", color="sex", barmode="group", text_auto=True,
                     color_discrete_map={"ชาย": "#457b9d", "หญิง": "#e76f51"}, labels={"sex": "เพศ"})
        fig.update_layout(height=340, margin=dict(t=10, b=10), legend=dict(title="", orientation="h", y=-0.2))
        st.plotly_chart(fig, width="stretch")
    st.caption("🔒 แสดงเฉพาะยอดรวม — ชื่อ เลขบัตรประชาชน และเบอร์โทรอยู่ใน Google Sheet ส่วนตัวเท่านั้น "
               "(ไม่ถูกส่งมายังแดชบอร์ด)")
