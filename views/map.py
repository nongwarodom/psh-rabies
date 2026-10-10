import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from rabies import ui

df = ui.filtered()
st.title("🗺️ แผนที่ GIS อำเภอปราสาท")
st.caption("แผนที่รายตำบล (18 ตำบล) — เลือกตัวชี้วัดเพื่อแสดงสีบนแผนที่")

gj, centroids = ui.load_geojson()
agg = ui.by_area(df, all_tambons=True)

METRICS = {
    "households": ("จำนวนครัวเรือนที่ตอบแบบสำรวจ", "Blues"),
    "residents": ("จำนวนประชากร (คน)", "Blues"),
    "people_bitten_unvax": ("จำนวนผู้ถูกกัด/ข่วน ยังไม่ฉีดวัคซีน (คน)", "Reds"),
    "pct_bitten_people": ("% ผู้ถูกกัด/ข่วน ยังไม่ฉีดวัคซีน ต่อประชากร", "Reds"),
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
style = c2.selectbox("แผนที่พื้นหลัง", ["carto-positron", "open-street-map", "carto-darkmatter"],
                     format_func=lambda s: {"carto-positron": "สว่าง", "open-street-map": "OpenStreetMap",
                                            "carto-darkmatter": "มืด"}[s])
label, scale = METRICS[metric]
is_pct = metric.startswith("pct_")

agg["มีข้อมูล"] = agg["households"].map(lambda v: "มี" if v else "ยังไม่มีข้อมูล")
agg["label"] = agg.apply(lambda r: f"{r.tambon}<br>{r[metric]:.1f}%" if is_pct else f"{r.tambon}<br>{r[metric]:,.0f}", axis=1)

fig = px.choropleth_map(
    agg, geojson=gj, locations="tambon", featureidkey="properties.tambon", color=metric,
    color_continuous_scale=scale, range_color=(0, 100) if is_pct else None,
    map_style=style, center={"lat": 14.62, "lon": 103.40}, zoom=9.3, opacity=0.72,
    hover_name="tambon",
    hover_data={"tambon": False, "households": True, "residents": True, "people_bitten_unvax": True,
                "people_vaccinated": True, "dogs_total": True, "dogs_vaccinated": True,
                "cats_total": True, "cats_vaccinated": True, metric: ":.1f" if is_pct else True},
    labels={**ui.TH_COLS, metric: label},
)
fig.add_trace(go.Scattermap(
    lat=[centroids[t][0] for t in agg["tambon"]], lon=[centroids[t][1] for t in agg["tambon"]],
    mode="text", text=agg["label"], textfont=dict(size=11, color="#111"), hoverinfo="skip", showlegend=False))
fig.update_traces(marker_line_color="#333", marker_line_width=1, selector=dict(type="choroplethmap"))
fig.update_layout(height=680, margin=dict(l=0, r=0, t=0, b=0),
                  coloraxis_colorbar=dict(title=label.replace(" ", "<br>", 1)))
st.plotly_chart(fig, width="stretch")

no_data = agg.loc[agg["households"] == 0, "tambon"].tolist()
if no_data:
    st.warning(f"ตำบลที่ยังไม่มีข้อมูล ({len(no_data)}): " + ", ".join(no_data))

st.subheader("📋 ตารางข้อมูลรายตำบล")
show = agg[["tambon", "households", "residents", "people_bitten_unvax", "pct_bitten_people",
            "people_vaccinated", "dogs_total", "dogs_vaccinated", "pct_dog_vax", "cats_total",
            "cats_vaccinated", "pct_cat_vax", "other_mammals"]].sort_values(metric, ascending=False)
st.dataframe(ui.to_thai(show).round(1), width="stretch", hide_index=True)
st.caption("ขอบเขตตำบล: OpenGISData-Thailand (chingchai) — ใช้เพื่อการแสดงผลเท่านั้น")
