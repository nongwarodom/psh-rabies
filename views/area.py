import plotly.express as px
import streamlit as st

from rabies import ui

df = ui.filtered()
st.title("🏘️ สรุปข้อมูลรายตำบล / รายหมู่บ้าน")
if ui.empty_guard(df):
    st.stop()

level = st.radio("ระดับการสรุป", ["รายตำบล", "รายหมู่บ้าน"], horizontal=True)
keys = ("tambon",) if level == "รายตำบล" else ("tambon", "moo")
agg = ui.by_area(df, keys=keys)
cols = list(keys) + ["households", "residents", "people_bitten_unvax", "pct_bitten_people", "hh_bitten",
                     "people_vaccinated", "pct_vax_people", "dogs_total", "dogs_vaccinated",
                     "dogs_unvaccinated", "pct_dog_vax", "cats_total", "cats_vaccinated",
                     "cats_unvaccinated", "pct_cat_vax", "other_mammals"]
table = agg[cols].copy()
total = table.drop(columns=list(keys)).sum(numeric_only=True)
T = df[ui.SUM_COLS].sum()
total["pct_bitten_people"] = ui.pct(T.people_bitten_unvax, T.residents)
total["pct_vax_people"] = ui.pct(T.people_vaccinated, T.residents)
total["pct_dog_vax"] = ui.pct(T.dogs_vaccinated, T.dogs_total)
total["pct_cat_vax"] = ui.pct(T.cats_vaccinated, T.cats_total)

pct_cols = [c for c in cols if c.startswith("pct_")]
cfg = {ui.TH_COLS[c]: st.column_config.ProgressColumn(ui.TH_COLS[c], format="%.1f%%", min_value=0, max_value=100)
       for c in pct_cols}
st.dataframe(ui.to_thai(table), width="stretch", hide_index=True, column_config=cfg)

st.markdown(f"**รวมทั้งหมด:** {total.households:,.0f} ครัวเรือน · {total.residents:,.0f} คน · "
            f"ถูกกัดยังไม่ฉีด {total.people_bitten_unvax:,.0f} คน ({total.pct_bitten_people:.1f}%) · "
            f"สุนัข {total.dogs_total:,.0f} ตัว (ฉีด {total.pct_dog_vax:.1f}%) · "
            f"แมว {total.cats_total:,.0f} ตัว (ฉีด {total.pct_cat_vax:.1f}%)")
st.download_button("⬇️ ดาวน์โหลดตารางสรุป (CSV)", ui.csv_bytes(ui.to_thai(table)), "summary.csv", "text/csv")

st.divider()
st.subheader("🌳 แผนภาพสัดส่วน ตำบล → หมู่บ้าน")
measure = st.selectbox("ขนาดของกล่องแสดง", ["households", "residents", "dogs_total", "cats_total",
                                              "people_bitten_unvax", "dogs_unvaccinated"],
                       format_func=lambda k: ui.TH_COLS[k])
tm = ui.by_area(df, keys=("tambon", "moo"))
tm["หมู่"] = "หมู่ " + tm["moo"].astype(str)
tm = tm[tm[measure] > 0]
if tm.empty:
    st.caption("ไม่มีข้อมูลสำหรับตัวชี้วัดนี้")
else:
    fig = px.treemap(tm, path=[px.Constant("อ.ปราสาท"), "tambon", "หมู่"], values=measure,
                     color="pct_dog_vax", color_continuous_scale="RdYlGn", range_color=[0, 100],
                     labels={"pct_dog_vax": "% สุนัขฉีดวัคซีน", measure: ui.TH_COLS[measure]})
    fig.update_traces(textinfo="label+value")
    fig.update_layout(height=520, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("สีของกล่อง = % ความครอบคลุมวัคซีนสุนัข (แดง = ต่ำ, เขียว = สูง)")

st.caption("🔒 เว็บไซต์สาธารณะแสดงเฉพาะยอดรวมระดับตำบล/หมู่บ้าน ไม่แสดงบ้านเลขที่หรือข้อมูลรายครัวเรือน")
