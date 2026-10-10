import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from rabies import ui

df = ui.filtered()
st.title("🐶 สัตว์เลี้ยงและสถานะวัคซีนพิษสุนัขบ้า")
st.caption("จำนวนสุนัข แมว และสัตว์เลี้ยงลูกด้วยนมอื่นๆ พร้อมรายละเอียดการได้รับ / ไม่ได้รับวัคซีน")
if ui.empty_guard(df):
    st.stop()

T = df[ui.SUM_COLS].sum()
c = st.columns(5)
ui.kpi(c[0], "🐕 สุนัขทั้งหมด", T.dogs_total, f"{df['has_dog'].sum()} ครัวเรือนเลี้ยง", ui.COLORS["dog"])
ui.kpi(c[1], "✅ สุนัขฉีดแล้ว / ❌ ยังไม่ฉีด", f"{T.dogs_vaccinated:,.0f} / {T.dogs_unvaccinated:,.0f}",
       f"ครอบคลุม {ui.fmt_pct(T.dogs_vaccinated, T.dogs_total)}", ui.COLORS["vax"])
ui.kpi(c[2], "🐈 แมวทั้งหมด", T.cats_total, f"{df['has_cat'].sum()} ครัวเรือนเลี้ยง", ui.COLORS["cat"])
ui.kpi(c[3], "✅ แมวฉีดแล้ว / ❌ ยังไม่ฉีด", f"{T.cats_vaccinated:,.0f} / {T.cats_unvaccinated:,.0f}",
       f"ครอบคลุม {ui.fmt_pct(T.cats_vaccinated, T.cats_total)}", ui.COLORS["vax"])
ui.kpi(c[4], "🐾 สัตว์ลูกด้วยนมอื่น", T.other_mammals, "ไม่มีข้อมูลวัคซีน", ui.COLORS["mammal"])

st.divider()
st.info("💡 เป้าหมายความครอบคลุมวัคซีนในสัตว์ที่แนะนำเพื่อควบคุมโรคพิษสุนัขบ้า คือ **อย่างน้อย 70%** ของประชากรสัตว์")

animal = st.radio("เลือกชนิดสัตว์", ["สุนัข", "แมว"], horizontal=True)
key = "dogs" if animal == "สุนัข" else "cats"
tot, vax, unv = f"{key}_total", f"{key}_vaccinated", f"{key}_unvaccinated"
pct_col = f"pct_{key[:-1]}_vax"

l, r = st.columns([2, 3])
with l:
    cov = ui.pct(T[vax], T[tot])
    g = go.Figure(go.Indicator(
        mode="gauge+number", value=cov, number={"suffix": "%", "valueformat": ".1f"},
        title={"text": f"ความครอบคลุมวัคซีน{animal}"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": ui.COLORS["vax"]},
               "steps": [{"range": [0, 70], "color": "#fde2d9"}, {"range": [70, 100], "color": "#d8f3ee"}],
               "threshold": {"line": {"color": "#d62828", "width": 4}, "value": 70}}))
    g.update_layout(height=300, margin=dict(t=60, b=10))
    st.plotly_chart(g, width="stretch")
    p = go.Figure(go.Pie(labels=["ฉีดแล้ว", "ยังไม่ฉีด"], values=[T[vax], T[unv]], hole=.5, sort=False,
                         marker_colors=[ui.COLORS["vax"], ui.COLORS["unvax"]], textinfo="value+percent"))
    p.update_layout(height=280, margin=dict(t=10, b=10), legend=dict(orientation="h"))
    st.plotly_chart(p, width="stretch")

with r:
    st.subheader(f"{animal}ที่ฉีด / ไม่ได้ฉีดวัคซีน รายตำบล")
    agg = ui.by_area(df)
    long = agg.melt(id_vars=["tambon", pct_col], value_vars=[vax, unv], var_name="สถานะ", value_name="ตัว")
    long["สถานะ"] = long["สถานะ"].map({vax: "ฉีดแล้ว", unv: "ยังไม่ฉีด"})
    fig = px.bar(long, x="tambon", y="ตัว", color="สถานะ", text_auto=True,
                 color_discrete_map={"ฉีดแล้ว": ui.COLORS["vax"], "ยังไม่ฉีด": ui.COLORS["unvax"]},
                 labels={"tambon": "ตำบล"})
    fig.update_layout(height=300, margin=dict(t=10, b=10), legend_title="")
    st.plotly_chart(fig, width="stretch")

    st.subheader(f"% ความครอบคลุมวัคซีน{animal} รายหมู่บ้าน")
    area = ui.by_area(df, keys=("tambon", "moo"))
    area = area[area[tot] > 0]
    area["หมู่บ้าน"] = area["tambon"] + " ม." + area["moo"].astype(str)
    if area.empty:
        st.caption(f"ยังไม่มีข้อมูล{animal}")
    else:
        area = area.sort_values(pct_col)
        fig = px.bar(area, y="หมู่บ้าน", x=pct_col, orientation="h", range_x=[0, 105],
                     text=area.apply(lambda x: f"{x[vax]:.0f}/{x[tot]:.0f} ตัว", axis=1),
                     color=pct_col, color_continuous_scale="RdYlGn", range_color=[0, 100],
                     labels={pct_col: "% ฉีดวัคซีน"})
        fig.add_vline(x=70, line_dash="dash", line_color="#d62828", annotation_text="เป้าหมาย 70%")
        fig.update_layout(height=max(260, 32 * len(area)), margin=dict(t=10, b=10), coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch")

st.divider()
l, r = st.columns(2)
with l:
    st.subheader("🏠 จำนวนสัตว์ต่อครัวเรือน")
    dist = df[["dogs_total", "cats_total"]].rename(columns={"dogs_total": "สุนัข", "cats_total": "แมว"})
    dist = dist.melt(var_name="ชนิด", value_name="จำนวนต่อครัวเรือน")
    fig = px.histogram(dist, x="จำนวนต่อครัวเรือน", color="ชนิด", barmode="group", text_auto=True,
                       color_discrete_map={"สุนัข": ui.COLORS["dog"], "แมว": ui.COLORS["cat"]})
    fig.update_layout(height=340, margin=dict(t=10, b=10), yaxis_title="ครัวเรือน", bargap=.15)
    st.plotly_chart(fig, width="stretch")
with r:
    st.subheader("🐾 สัตว์เลี้ยงทุกชนิด รายตำบล")
    agg = ui.by_area(df)
    long = agg.melt(id_vars="tambon", value_vars=["dogs_total", "cats_total", "other_mammals"],
                    var_name="ชนิด", value_name="ตัว")
    long["ชนิด"] = long["ชนิด"].map({"dogs_total": "สุนัข", "cats_total": "แมว", "other_mammals": "อื่นๆ"})
    fig = px.bar(long, x="tambon", y="ตัว", color="ชนิด", barmode="group", text_auto=True,
                 color_discrete_map={"สุนัข": ui.COLORS["dog"], "แมว": ui.COLORS["cat"], "อื่นๆ": ui.COLORS["mammal"]},
                 labels={"tambon": "ตำบล"})
    fig.update_layout(height=340, margin=dict(t=10, b=10), legend_title="")
    st.plotly_chart(fig, width="stretch")

st.subheader(f"📋 หมู่บ้านที่มี{animal}ยังไม่ได้รับวัคซีน (เป้าหมายการรณรงค์ฉีดวัคซีน)")
st.caption("🔒 แสดงเฉพาะยอดรวมระดับตำบล/หมู่บ้าน")
target = ui.by_area(df, keys=("tambon", "moo"))
target = target[target[unv] > 0].sort_values(unv, ascending=False)
if target.empty:
    st.success(f"ไม่พบ{animal}ที่ยังไม่ได้รับวัคซีน")
else:
    hh_col = "hh_dog" if key == "dogs" else "hh_cat"
    cols = ["tambon", "moo", "households", hh_col, tot, vax, unv, pct_col]
    out = ui.to_thai(target[cols].round(1))
    st.dataframe(out, width="stretch", hide_index=True)
    st.download_button("⬇️ ดาวน์โหลด (CSV)", ui.csv_bytes(out), f"{key}_unvaccinated_by_village.csv", "text/csv")
