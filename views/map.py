import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from rabies import ui

df = ui.filtered()
st.title("🗺️ แผนที่ GIS อำเภอปราสาท")
st.caption("แผนที่รายตำบล (18 ตำบล) — เลือกตัวชี้วัดเพื่อแสดงสีบนแผนที่ · วางเมาส์บนตำบลเพื่อดูรายละเอียด")

gj, centroids = ui.load_geojson()
agg = ui.by_area(df, all_tambons=True)

METRICS = {
    "pct_coverage": ("% ความครอบคลุมการสำรวจ (ผู้อาศัยที่สำรวจ ÷ ประชากรทะเบียน)", "Blues"),
    "pop_total": ("ประชากรทะเบียนราษฎร์ (คน)", "Blues"),
    "households": ("จำนวนครัวเรือนที่ตอบแบบสำรวจ", "Blues"),
    "residents": ("จำนวนผู้อาศัยที่สำรวจ (คน)", "Blues"),
    "people_bitten_unvax": ("จำนวนผู้ถูกกัด/ข่วน ยังไม่ฉีดวัคซีน (คน)", "Reds"),
    "pct_bitten_people": ("% ผู้ถูกกัด/ข่วน ยังไม่ฉีดวัคซีน ต่อผู้อาศัยที่สำรวจ", "Reds"),
    "pct_hh_bitten": ("% ครัวเรือนที่มีผู้ถูกกัด", "Reds"),
    "people_vaccinated": ("จำนวนคนที่เคยฉีดวัคซีน (คน)", "Greens"),
    "pct_vax_people": ("% คนที่เคยฉีดวัคซีน", "Greens"),
    "dogs_total": ("จำนวนสุนัข (ตัว)", "Oranges"),
    "dogs_unvaccinated": ("สุนัขที่ยังไม่ฉีดวัคซีน (ตัว)", "OrRd"),
    "pct_dog_vax": ("% ความครอบคลุมวัคซีนสุนัข", "RdYlGn"),
    "cats_total": ("จำนวนแมว (ตัว)", "Purples"),
    "cats_unvaccinated": ("แมวที่ยังไม่ฉีดวัคซีน (ตัว)", "OrRd"),
    "pct_cat_vax": ("% ความครอบคลุมวัคซีนแมว", "RdYlGn"),
    "other_mammals": ("สัตว์เลี้ยงลูกด้วยนมอื่นๆ (ตัว)", "Greys"),
}

c1, c2 = st.columns([3, 1])
metric = c1.selectbox("ตัวชี้วัด", list(METRICS), format_func=lambda k: METRICS[k][0])
show_value = c2.toggle("แสดงค่าบนแผนที่", value=True)
label, scale = METRICS[metric]
is_pct = metric.startswith("pct_")
fmt = (lambda v: f"{v:.1f}%") if is_pct else (lambda v: f"{v:,.0f}")

if is_pct:
    vmax = 100 if metric != "pct_coverage" else max(5.0, float(agg[metric].max()) * 1.1)
    rng = (0, vmax)
else:
    rng = (0, max(1.0, float(agg[metric].max())))

fig = px.choropleth(
    agg, geojson=gj, locations="tambon", featureidkey="properties.tambon", color=metric,
    color_continuous_scale=scale, range_color=rng, hover_name="tambon",
    hover_data={"tambon": False, "pop_total": ":,", "households": True, "residents": True,
                "pct_coverage": ":.2f", "people_bitten_unvax": True, "people_vaccinated": True,
                "dogs_total": True, "dogs_vaccinated": True, "cats_total": True, "cats_vaccinated": True},
    labels={**ui.TH_COLS, metric: label},
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_traces(marker_line_color="#ffffff", marker_line_width=1.5)

# Labels drawn as SVG text by the browser → Thai renders correctly (tile-map glyphs cannot).
names = agg["tambon"].tolist()
text = [f"<b>{t}</b><br>{fmt(v)}" if show_value else f"<b>{t}</b>" for t, v in zip(names, agg[metric])]
diverging = scale in ("RdYlGn",)
norm = [(v - rng[0]) / (rng[1] - rng[0]) if rng[1] > rng[0] else 0 for v in agg[metric]]
colors = [("#fff" if (n < 0.15 or n > 0.85) else "#111") if diverging else ("#fff" if n > 0.6 else "#111")
          for n in norm]
fig.add_trace(go.Scattergeo(
    lat=[centroids[t][0] for t in names], lon=[centroids[t][1] for t in names], mode="text", text=text,
    textfont=dict(family=ui.FONT, size=12, color=colors), hoverinfo="skip", showlegend=False))
fig.update_layout(height=700, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                  geo_bgcolor="rgba(0,0,0,0)", coloraxis_colorbar=dict(title=label.split(" (")[0].replace(" ", "<br>", 1)))
st.plotly_chart(fig, width="stretch")

no_data = agg.loc[agg["households"] == 0, "tambon"].tolist()
if no_data:
    st.warning(f"ตำบลที่ยังไม่มีข้อมูลการสำรวจ ({len(no_data)}): " + ", ".join(no_data))

st.subheader("📋 ตารางข้อมูลรายตำบล")
show = agg[["tambon", "pop_total", "households", "residents", "pct_coverage", "people_bitten_unvax",
            "pct_bitten_people", "people_vaccinated", "dogs_total", "dogs_vaccinated", "pct_dog_vax",
            "cats_total", "cats_vaccinated", "pct_cat_vax", "other_mammals"]].sort_values(metric, ascending=False)
st.dataframe(ui.to_thai(show).round(2), width="stretch", hide_index=True)
st.caption(f"ประชากรฐาน: {ui.POP_SOURCE} · ขอบเขตตำบล: OpenGISData-Thailand (chingchai) — ใช้เพื่อการแสดงผลเท่านั้น")
