import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from rabies import ui
from rabies.cleaning import TAMBONS

df = ui.filtered()
st.title("📊 ภาพรวมการสำรวจโรคพิษสุนัขบ้า")
st.caption("อำเภอปราสาท จังหวัดสุรินทร์ — ข้อมูลครัวเรือน ประชากร สัตว์เลี้ยง และสถานะการได้รับวัคซีน")
if ui.empty_guard(df):
    st.stop()

T = df[ui.SUM_COLS].sum()
hh = ui.households(df)
base_pop = ui.base_population(st.session_state.get("sel_tambons"))
base_hh = ui.base_houses(st.session_state.get("sel_tambons"))

by_src = df.groupby("source")[["hh_count", "residents"]].sum()
st.caption("แหล่งข้อมูลที่รวมอยู่: " + " · ".join(
    f"**{s}** {r.hh_count:,.0f} ครัวเรือน / {r.residents:,.0f} คน" for s, r in by_src.iterrows()))

c = st.columns(6)
ui.kpi(c[0], "📋 ฐานทะเบียนราษฎร์", f"{base_hh:,} หลัง", f"ประชากร {base_pop:,} คน (ก.ย. 2569)", "#6c757d")
ui.kpi(c[1], "🏠 ครัวเรือนที่สำรวจ", hh,
       f"ครอบคลุม {ui.pct(hh, base_hh):.2f}% ของบ้าน · {df.groupby(['tambon','moo']).ngroups} หมู่บ้าน", ui.COLORS["house"])
ui.kpi(c[2], "👥 ผู้ที่สำรวจ (คน)", T.residents,
       f"ครอบคลุม {ui.pct(T.residents, base_pop):.2f}% ของประชากร", ui.COLORS["people"])
ui.kpi(c[3], "🐕 สุนัข (ตัว)", T.dogs_total, f"เลี้ยงใน {T.hh_dog:,.0f} ครัวเรือน*", ui.COLORS["dog"])
ui.kpi(c[4], "🐈 แมว (ตัว)", T.cats_total, f"เลี้ยงใน {T.hh_cat:,.0f} ครัวเรือน*", ui.COLORS["cat"])
ui.kpi(c[5], "🐾 สัตว์ลูกด้วยนมอื่น (ตัว)", T.other_mammals, "*ไม่รวม อสม. (ไม่มีข้อมูลสัตว์)", ui.COLORS["mammal"])

st.write("")
c = st.columns(4)
ui.kpi(c[0], "🩸 ถูกกัด/ข่วน ยังไม่ได้รับวัคซีน", T.people_bitten_unvax,
       f"{ui.fmt_pct(T.people_bitten_unvax, T.residents)} ของผู้ที่สำรวจ", ui.COLORS["bitten"])
ui.kpi(c[1], "💉 ได้รับวัคซีนแล้ว", T.people_vaccinated,
       f"{ui.fmt_pct(T.people_vaccinated, T.residents)} ของผู้ที่สำรวจ (อสม.: ครบชุด + อยู่ระหว่างฉีด)", ui.COLORS["vax"])
ui.kpi(c[2], "🐕 ความครอบคลุมวัคซีนสุนัข", ui.fmt_pct(T.dogs_vaccinated, T.dogs_total),
       f"ฉีดแล้ว {T.dogs_vaccinated:,.0f} / ยังไม่ฉีด {T.dogs_unvaccinated:,.0f} ตัว", ui.COLORS["vax"])
ui.kpi(c[3], "🐈 ความครอบคลุมวัคซีนแมว", ui.fmt_pct(T.cats_vaccinated, T.cats_total),
       f"ฉีดแล้ว {T.cats_vaccinated:,.0f} / ยังไม่ฉีด {T.cats_unvaccinated:,.0f} ตัว", ui.COLORS["vax"])

st.divider()

# ---- cumulative over time (weighted: อสม. rows count as their households / people)
left, right = st.columns([3, 2])
with left:
    st.subheader("📈 จำนวนที่สำรวจสะสม")
    o1, o2 = st.columns(2)
    unit = o1.radio("หน่วย", ["ครัวเรือน", "คน"], horizontal=True, key="cum_unit")
    split = o2.radio("แยกตาม", ["ไม่แยก", "แหล่งข้อมูล", "ตำบล"], horizontal=True, key="cum_split")
    wcol = "hh_count" if unit == "ครัวเรือน" else "residents"
    d = df.sort_values("timestamp").copy()
    grp = {"แหล่งข้อมูล": "source", "ตำบล": "tambon"}.get(split)
    if grp:
        d["สะสม"] = d.groupby(grp)[wcol].cumsum()
        fig = px.line(d, x="timestamp", y="สะสม", color=grp, markers=True, line_shape="hv",
                      labels={"timestamp": "วันเวลา", "tambon": "ตำบล", "source": "แหล่งข้อมูล", "สะสม": f"{unit}สะสม"})
    else:
        d["สะสม"] = d[wcol].cumsum()
        fig = px.area(d, x="timestamp", y="สะสม", markers=True, line_shape="hv",
                      labels={"timestamp": "วันเวลา", "สะสม": f"{unit}สะสม"})
        fig.update_traces(line_color=ui.COLORS["house"])
    fig.update_layout(height=360, margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("🗓️ จำนวนที่สำรวจรายวัน")
    daily = df.groupby(["date", "source"])[wcol].sum().reset_index(name=unit)
    fig = px.bar(daily, x="date", y=unit, color="source", text_auto=True, labels={"date": "วันที่", "source": "แหล่งข้อมูล"},
                 color_discrete_map=ui.SOURCE_COLORS)
    fig.update_layout(height=430, margin=dict(t=10, b=10), legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, width="stretch")

# ---- responses by tambon (all 18) + coverage vs registered population
agg = ui.by_area(df, all_tambons=True).sort_values("pop_total", ascending=True)
agg["สถานะ"] = agg["households"].map(lambda v: "มีข้อมูล" if v > 0 else "ยังไม่มีข้อมูล")
left, right = st.columns(2)
with left:
    st.subheader("🏘️ ครัวเรือนที่สำรวจ รายตำบล")
    src = df.groupby(["tambon", "source"])["hh_count"].sum().reset_index()
    order = agg["tambon"].tolist()
    fig = px.bar(src, y="tambon", x="hh_count", orientation="h", color="source", text_auto=True,
                 category_orders={"tambon": order[::-1]},
                 color_discrete_map=ui.SOURCE_COLORS,
                 labels={"tambon": "ตำบล", "hh_count": "ครัวเรือน", "source": "แหล่งข้อมูล"})
    fig.update_yaxes(categoryorder="array", categoryarray=order)
    fig.update_layout(height=600, margin=dict(t=10, b=10), legend=dict(title="", orientation="h", y=-0.08))
    st.plotly_chart(fig, width="stretch")
    no_data = agg.loc[agg["households"] == 0, "tambon"].tolist()
    if no_data:
        st.caption(f"ยังไม่มีข้อมูล ({len(no_data)} ตำบล): " + ", ".join(no_data))
with right:
    st.subheader("📋 ความครอบคลุมเทียบฐานทะเบียนราษฎร์")
    basis = st.radio("เทียบกับ", ["บ้าน (หลัง)", "ประชากร (คน)"], horizontal=True, key="cov_basis")
    if basis.startswith("บ้าน"):
        num, den, pc, unit = "households", "houses_total", "pct_hh_coverage", "ครัวเรือนที่สำรวจ ÷ บ้านทะเบียน"
    else:
        num, den, pc, unit = "residents", "pop_total", "pct_coverage", "ผู้อาศัยที่สำรวจ ÷ ประชากรทะเบียน"
    fig = px.bar(agg, y="tambon", x=pc, orientation="h",
                 text=agg.apply(lambda r: f"{r[num]:,.0f} / {r[den]:,.0f} ({r[pc]:.2f}%)", axis=1),
                 color_discrete_sequence=[ui.COLORS["people"]],
                 labels={"tambon": "ตำบล", pc: f"% {unit}"},
                 hover_data={den: ":,", num: True})
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(height=560, margin=dict(t=10, b=10, r=150),
                      xaxis_range=[0, max(1.0, agg[pc].max() * 1.35)])
    st.plotly_chart(fig, width="stretch")
st.caption(f"ประชากรฐาน: {ui.POP_SOURCE} (รวมสัญชาติไทยและไม่ใช่สัญชาติไทย) · เรียงตำบลตามจำนวนประชากร")

# ---- vaccine status summary
st.subheader("💉 สรุปสถานะวัคซีน")
c1, c2, c3 = st.columns(3)


def donut(labels, values, colors, title):
    f = go.Figure(go.Pie(labels=labels, values=values, hole=.55, marker_colors=colors,
                         textinfo="value+percent", sort=False))
    f.update_layout(title=title, height=330, margin=dict(t=50, b=10, l=10, r=10),
                    legend=dict(orientation="h", y=-0.1))
    return f


c1.plotly_chart(donut(["ถูกกัด ยังไม่ได้รับวัคซีน", "ได้รับวัคซีนแล้ว", "อื่นๆ"],
                      [T.people_bitten_unvax, T.people_vaccinated, T.people_other],
                      [ui.COLORS["bitten"], ui.COLORS["vax"], ui.COLORS["other"]], "ประชากร"),
                width="stretch")
c2.plotly_chart(donut(["ฉีดแล้ว", "ยังไม่ฉีด"], [T.dogs_vaccinated, T.dogs_unvaccinated],
                      [ui.COLORS["vax"], ui.COLORS["unvax"]], "สุนัข"), width="stretch")
c3.plotly_chart(donut(["ฉีดแล้ว", "ยังไม่ฉีด"], [T.cats_vaccinated, T.cats_unvaccinated],
                      [ui.COLORS["vax"], ui.COLORS["unvax"]], "แมว"), width="stretch")
