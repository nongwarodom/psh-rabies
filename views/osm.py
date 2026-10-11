import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from rabies import osm, ui

st.title("🚪 ผลสำรวจ อสม. เคาะประตูบ้าน")
data, warnings, as_of = osm.load()
st.caption(f"แบบสำรวจ อสม. เคาะประตูบ้าน (ป้องกันโรคพิษสุนัขบ้า) อำเภอปราสาท จังหวัดสุรินทร์ — "
           f"ข้อมูล ณ วันที่ {osm.thai_date(as_of)} · ข้อมูลสรุปรายพื้นที่ แยกจากแบบสำรวจ Google Form")

sel = st.session_state.get("sel_tambons") or []
df = data[data["tambon"].isin(sel)] if sel else data
if df.empty:
    st.info("ไม่มีข้อมูล อสม. ในตำบลที่เลือก")
    st.stop()
for w in warnings:
    st.warning(f"⚠️ ตรวจพบข้อมูลไม่สอดคล้อง: {w}")

T = df[osm.COUNT_COLS].sum()
c = st.columns(6)
ui.kpi(c[0], "👥 จำนวนที่สำรวจ", T.persons, f"{len(df)} จุดสำรวจ · {df['tambon'].nunique()} ตำบล", ui.COLORS["people"])
ui.kpi(c[1], "🏠 หลังคาเรือน", T.households, "ไม่รวมตลาดสด", ui.COLORS["house"])
ui.kpi(c[2], "🩸 เคยถูกกัด/ข่วน/เลีย (1 ปี)", T.bitten_yes,
       f"{ui.fmt_pct(T.bitten_yes, T.persons)} ของผู้ที่สำรวจ", ui.COLORS["bitten"])
ui.kpi(c[3], "✅ ฉีดวัคซีนครบชุด", T.vax_full, f"{ui.fmt_pct(T.vax_full, T.bitten_yes)} ของผู้ถูกกัด", ui.COLORS["vax"])
ui.kpi(c[4], "⏳ ไม่ครบ / อยู่ระหว่างฉีด", f"{T.vax_partial:,.0f} / {T.vax_in_progress:,.0f}",
       f"{ui.fmt_pct(T.vax_partial + T.vax_in_progress, T.bitten_yes)} ของผู้ถูกกัด", "#f4a261")
ui.kpi(c[5], "❌ ไม่ได้รับวัคซีน", T.vax_none, f"{ui.fmt_pct(T.vax_none, T.bitten_yes)} ของผู้ถูกกัด", ui.COLORS["bitten"])

st.divider()

# ---- flow: surveyed -> bitten -> vaccine status
l, r = st.columns([3, 2])
with l:
    st.subheader("🔀 เส้นทาง: ผู้ที่สำรวจ → ถูกกัด → สถานะวัคซีน")
    labels = ["ผู้ที่สำรวจ", "เคยถูกกัด/ข่วน/เลีย", "ไม่เคย"] + list(osm.VAX_LABELS.values())
    vals = [T[c] for c in osm.VAX_COLS]
    src = [0, 0] + [1] * 4
    tgt = [1, 2, 3, 4, 5, 6]
    val = [T.bitten_yes, T.bitten_no] + vals
    keep = [i for i, v in enumerate(val) if v > 0]
    node_colors = [ui.COLORS["people"], ui.COLORS["bitten"], "#adb5bd"] + list(osm.VAX_COLORS.values())
    fig = go.Figure(go.Sankey(
        node=dict(label=[f"{lb} ({v:,.0f})" for lb, v in zip(labels, [T.persons, T.bitten_yes, T.bitten_no] + vals)],
                  color=node_colors, pad=18, thickness=18),
        link=dict(source=[src[i] for i in keep], target=[tgt[i] for i in keep], value=[val[i] for i in keep],
                  color="rgba(150,150,150,.25)")))
    fig.update_layout(height=380, margin=dict(t=10, b=10, l=10, r=10), font=dict(family=ui.FONT, size=13))
    st.plotly_chart(fig, width="stretch")
with r:
    st.subheader("💉 สถานะวัคซีนของผู้ถูกกัด")
    pie = go.Figure(go.Pie(labels=list(osm.VAX_LABELS.values()), values=vals, hole=.55, sort=False,
                           marker_colors=list(osm.VAX_COLORS.values()), textinfo="value+percent"))
    pie.update_layout(height=380, margin=dict(t=10, b=10), legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(pie, width="stretch")

# ---- by location
st.subheader("📍 เปรียบเทียบรายจุดสำรวจ")
loc = osm.add_rates(df)
loc["จุดสำรวจ"] = loc["location"] + " (" + loc["tambon"] + ")"
l, r = st.columns(2)
with l:
    fig = px.bar(loc, x="จุดสำรวจ", y="pct_bitten", text=loc.apply(lambda x: f"{x.bitten_yes:.0f}/{x.persons:.0f} ({x.pct_bitten:.1f}%)", axis=1),
                 color_discrete_sequence=[ui.COLORS["bitten"]], labels={"pct_bitten": "% เคยถูกกัด/ข่วน/เลีย ใน 1 ปี"})
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(height=380, margin=dict(t=30, b=10), yaxis_range=[0, max(5, loc["pct_bitten"].max() * 1.3)])
    st.plotly_chart(fig, width="stretch")
with r:
    long = loc.melt(id_vars="จุดสำรวจ", value_vars=osm.VAX_COLS, var_name="สถานะ", value_name="คน")
    long["สถานะ"] = long["สถานะ"].map(osm.VAX_LABELS)
    fig = px.bar(long, x="จุดสำรวจ", y="คน", color="สถานะ", text_auto=True, color_discrete_map=osm.VAX_COLORS,
                 labels={"คน": "ผู้ถูกกัด (คน)"})
    fig.update_layout(height=380, margin=dict(t=30, b=10), legend=dict(title="", orientation="h", y=-0.2))
    st.plotly_chart(fig, width="stretch")

# ---- tables
st.subheader("📋 ตารางข้อมูล")
tab1, tab2, tab3 = st.tabs(["รายจุดสำรวจ", "รายหมู่บ้าน (รวมตลาดสดเข้ากับ ม.2 กังแอน)", "รายตำบล"])
cols = ["persons", "households", "bitten_yes", "bitten_no", "pct_bitten",
        "vax_full", "vax_partial", "vax_in_progress", "vax_none", "pct_full", "pct_none"]


def show(t, frame, keys):
    out = frame[keys + cols].copy()
    out["households"] = out["households"].fillna(0)
    out = out.rename(columns=osm.TH_COLS).round(1)
    t.dataframe(out, width="stretch", hide_index=True)
    return out


show(tab1, loc, ["location", "location_type", "tambon", "moo"])
show(tab2, osm.summarise(df, ["tambon", "moo"]), ["tambon", "moo"])
tam = osm.summarise(df, ["tambon"]).merge(ui.POPULATION[["tambon", "pop_total", "houses_total"]], on="tambon", how="left")
tam["pct_hh_cov"] = tam.households / tam.houses_total * 100
out = show(tab3, tam, ["tambon"])
tab3.caption("ความครอบคลุมหลังคาเรือนเทียบบ้านทะเบียนราษฎร์: " + " · ".join(
    f"{r.tambon} {r.households:,.0f}/{r.houses_total:,.0f} หลัง ({r.pct_hh_cov:.1f}%)" for r in tam.itertuples()))

st.download_button("⬇️ ดาวน์โหลดข้อมูล อสม. (CSV)", ui.csv_bytes(loc[["location", "location_type", "tambon", "moo"] + cols]
                                                             .rename(columns=osm.TH_COLS).round(1)),
                   "osm_summary.csv", "text/csv")
st.caption("หมายเหตุ: ตลาดสดเมืองปราสาท อยู่ในพื้นที่ ม.2 ต.กังแอน (ไม่มีจำนวนหลังคาเรือน) · "
           "ร้อยละสถานะวัคซีนคิดจากผู้ที่เคยถูกกัด/ข่วน/เลีย ภายใน 1 ปี")
