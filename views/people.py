import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from rabies import ui

df = ui.filtered()
st.title("🧑‍⚕️ ประชากรและการถูกสุนัขกัด")
st.caption("จำนวน/สัดส่วนผู้ถูกสุนัขกัดหรือข่วนที่ยังไม่ได้รับวัคซีน และผู้ที่เคยได้รับวัคซีนพิษสุนัขบ้าแล้ว")
if ui.empty_guard(df):
    st.stop()

T = df[ui.SUM_COLS].sum()
hh = len(df)
c = st.columns(4)
ui.kpi(c[0], "👥 ประชากรทั้งหมด", T.residents, f"{hh:,} ครัวเรือน", ui.COLORS["people"])
ui.kpi(c[1], "🩸 ถูกกัด/ข่วน ยังไม่ฉีดวัคซีน", T.people_bitten_unvax,
       f"{ui.fmt_pct(T.people_bitten_unvax, T.residents)} ของประชากร", ui.COLORS["bitten"])
ui.kpi(c[2], "🏠 ครัวเรือนที่มีผู้ถูกกัด", int(df["has_bitten"].sum()),
       f"{ui.fmt_pct(df['has_bitten'].sum(), hh)} ของครัวเรือน", ui.COLORS["unvax"])
ui.kpi(c[3], "💉 เคยฉีดวัคซีนแล้ว", T.people_vaccinated,
       f"{ui.fmt_pct(T.people_vaccinated, T.residents)} ของประชากร", ui.COLORS["vax"])

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

st.subheader("🚨 รายชื่อครัวเรือนที่มีผู้ถูกกัด/ข่วน แต่ยังไม่ได้ฉีดวัคซีน (ควรติดตาม)")
st.caption("🔒 เบอร์โทรถูกปิดบังบางส่วนเพื่อคุ้มครองข้อมูลส่วนบุคคล (เว็บไซต์สาธารณะ) — เจ้าหน้าที่ดูเบอร์เต็มได้ใน Google Sheet ต้นฉบับ")
follow = df[df["has_bitten"]].sort_values(["tambon", "moo"])
cols = ["tambon", "moo", "house_no", "residents", "people_bitten_unvax", "people_vaccinated",
        "dogs_total", "dogs_vaccinated", "phone_masked", "timestamp"]
if follow.empty:
    st.success("ไม่พบครัวเรือนที่มีผู้ถูกกัดแต่ยังไม่ได้ฉีดวัคซีน")
else:
    st.dataframe(ui.to_thai(follow[cols]), width="stretch", hide_index=True)
    st.download_button("⬇️ ดาวน์โหลดรายชื่อติดตาม (CSV)", ui.csv_bytes(ui.to_thai(follow[cols])),
                       "bitten_followup.csv", "text/csv")
