"""การมารับบริการที่โรงพยาบาลหลังถูกสัตว์กัด (HOSxP 5 ปี, ข้อมูลไม่ระบุตัวตน)."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from rabies import bites as B
from rabies import ui


@st.cache_data(ttl=3600, show_spinner="กำลังโหลดข้อมูลผู้ป่วยถูกสัตว์กัด...")
def _load():
    try:
        secrets = st.secrets if len(st.secrets) else None
    except Exception:  # noqa: BLE001  (no secrets.toml locally)
        secrets = None
    src, note = B.read_source(secrets)
    return B.load(src), note, pd.Timestamp.now()


try:
    raw, src_note, loaded_at = _load()
except (FileNotFoundError, PermissionError) as e:
    st.error(str(e))
    st.stop()

st.title("🏥 ผู้มารับบริการหลังถูกสัตว์กัด (ข้อมูลโรงพยาบาล 5 ปี)")
st.caption(f"ข้อมูล OPD จาก HOSxP (ไม่ระบุตัวตน) · {raw['date'].min():%d/%m/%Y} – {raw['date'].max():%d/%m/%Y} · "
           "จำแนกสัตว์จากรหัส ICD-10: W54 = สุนัข · W55 = แมว/สัตว์เลี้ยงลูกด้วยนมอื่น · Z20.3 = ไม่ระบุสัตว์")
s1, s2 = st.columns([5, 1])
s1.caption(f"แหล่งข้อมูล: {src_note} · โหลดเมื่อ {loaded_at:%d/%m/%Y %H:%M} (รีเฟรชอัตโนมัติทุก 1 ชั่วโมง)")
if s2.button("🔄 โหลดใหม่", key="bite_reload", width="stretch"):
    _load.clear()
    st.rerun()

# ----------------------------------------------------------------------------- page filters
with st.container(border=True):
    f1, f2, f3, f4 = st.columns([2, 3, 2, 2])
    dmin, dmax = raw["date"].min().date(), raw["date"].max().date()
    rng = f1.date_input("ช่วงวันที่มารับบริการ", (dmin, dmax), min_value=dmin, max_value=dmax, key="bite_dates")
    animals = f2.multiselect("ชนิดสัตว์", B.ANIMALS, default=B.ANIMALS, key="bite_animals")
    scope = f3.radio("พื้นที่", ["ทุกพื้นที่", "เฉพาะผู้อาศัยใน อ.ปราสาท"], key="bite_scope")
    sexes = f4.multiselect("เพศ", ["ชาย", "หญิง"], default=["ชาย", "หญิง"], key="bite_sex")

df = raw[raw["animal"].isin(animals or B.ANIMALS)]
if isinstance(rng, (list, tuple)) and len(rng) == 2:
    df = df[(df["date"].dt.date >= rng[0]) & (df["date"].dt.date <= rng[1])]
if scope.startswith("เฉพาะ"):
    df = df[df["in_prasat"]]
df = df[df["sex_th"].isin(sexes or ["ชาย", "หญิง"])]
if ui.empty_guard(df):
    st.stop()

n = len(df)
c = st.columns(5)
ui.kpi(c[0], "🩸 ครั้งที่มารับบริการ", n, f"เฉลี่ย {n / max((df['date'].max() - df['date'].min()).days / 365.25, 1/12):,.0f} ครั้ง/ปี",
       ui.COLORS["bitten"])
ui.kpi(c[1], "🐕 ถูกสุนัขกัด", int((df["animal"] == B.ANIMALS[0]).sum()),
       ui.fmt_pct((df["animal"] == B.ANIMALS[0]).sum(), n), ui.COLORS["dog"])
ui.kpi(c[2], "🐈 แมว/สัตว์อื่นกัด", int((df["animal"] == B.ANIMALS[1]).sum()),
       ui.fmt_pct((df["animal"] == B.ANIMALS[1]).sum(), n), ui.COLORS["cat"])
ui.kpi(c[3], "💉 เคยได้รับวัคซีนมาก่อนถูกกัด", int(df["had_prior_vaccine"].sum()),
       ui.fmt_pct(df["had_prior_vaccine"].sum(), n), ui.COLORS["vax"])
ui.kpi(c[4], "⚠️ ไม่เคยได้รับวัคซีนเลย (ตลอดชีวิต)", int((~df["ever_vaccinated_lifetime"]).sum()),
       ui.fmt_pct((~df["ever_vaccinated_lifetime"]).sum(), n), ui.COLORS["unvax"])

tab_trend, tab_map, tab_demo = st.tabs(["📈 แนวโน้ม & สถานะวัคซีน", "🗺️ แผนที่อุบัติการณ์", "👥 ประชากรศาสตร์"])

# ============================================================================= TREND
with tab_trend:
    g1, g2 = st.columns([3, 2])
    gran = g1.radio("ช่วงเวลา", ["รายเดือน", "รายไตรมาส", "รายปีงบประมาณ"], horizontal=True, index=0, key="bite_gran")
    trim = g2.toggle("ตัดช่วงต้น/ท้ายที่ข้อมูลไม่ครบช่วง", value=True, key="bite_trim",
                     help="เช่น เดือน/ปีงบประมาณแรกและสุดท้ายที่มีข้อมูลไม่เต็มช่วง จะทำให้กราฟดูลดลงผิดความจริง")
    col = {"รายเดือน": "month", "รายไตรมาส": "quarter", "รายปีงบประมาณ": "fy"}[gran]
    xlab = {"month": "เดือน", "quarter": "ไตรมาส", "fy": "ปีงบประมาณ (พ.ศ.)"}[col]

    t = df.copy()
    if trim:
        lo, hi = raw["date"].min(), raw["date"].max()
        if col == "fy":
            starts = pd.to_datetime((t["fy"] - 544).astype(str) + "-10-01")
            ends = starts + pd.DateOffset(years=1) - pd.Timedelta(days=1)
        else:
            per = t["date"].dt.to_period("M" if col == "month" else "Q")
            starts, ends = per.dt.start_time, per.dt.end_time.dt.normalize()
        t = t[(starts >= lo.normalize()) & (ends <= hi.normalize())]
    if t.empty:
        st.info("ช่วงเวลาที่เลือกสั้นเกินไปสำหรับการแสดงแนวโน้ม — ปิดตัวเลือก 'ตัดช่วงต้น/ท้าย' หรือขยายช่วงวันที่")
    else:
        xaxis = dict(type="category") if col == "fy" else {}

        st.subheader("จำนวนผู้มารับบริการ จำแนกตามชนิดสัตว์")
        a = t.groupby([col, "animal"]).size().rename("ครั้ง").reset_index()
        fig = px.bar(a, x=col, y="ครั้ง", color="animal", color_discrete_map=B.ANIMAL_COLORS,
                     category_orders={"animal": B.ANIMALS}, labels={col: xlab, "animal": "ชนิดสัตว์"},
                     text_auto=col == "fy")
        tot = t.groupby(col).size()
        fig.add_trace(go.Scatter(x=tot.index, y=tot.rolling(3 if col != "fy" else 1, min_periods=1).mean(),
                                 name="รวม (ค่าเฉลี่ยเคลื่อนที่ 3 ช่วง)" if col != "fy" else "รวม",
                                 mode="lines+markers", line=dict(color="#264653", width=2.5)))
        fig.update_layout(height=420, margin=dict(t=10, b=10), legend=dict(orientation="h", y=1.08, title=""),
                          xaxis=xaxis)
        st.plotly_chart(fig, width="stretch")

        st.subheader("สถานะวัคซีนพิษสุนัขบ้าของผู้ถูกกัด")
        st.caption("แบ่งกลุ่มไม่ซ้ำกัด: **เคยได้รับวัคซีนมาก่อน** = `had_prior_vaccine` · "
                   "**ฉีดครั้งแรกในครั้งนี้** = ไม่เคยฉีดก่อนถูกกัด แต่ `ever_vaccinated_lifetime` = จริง · "
                   "**ไม่เคยได้รับวัคซีนเลย** = `ever_vaccinated_lifetime` = เท็จ")
        m1, m2 = st.columns([2, 3])
        vmode = m1.radio("แสดงเป็น", ["จำนวน (ครั้ง)", "ร้อยละ (%)"], horizontal=True, key="bite_vmode")
        split = m2.selectbox("แยกตามชนิดสัตว์", ["รวมทุกชนิด", *B.ANIMALS[:2]], key="bite_split")
        tv = t if split == "รวมทุกชนิด" else t[t["animal"] == split]
        s = tv.groupby([col, "status"]).size().rename("ครั้ง").reset_index()
        if s.empty:
            st.info("ไม่มีข้อมูลของสัตว์ชนิดนี้ในช่วงที่เลือก")
        else:
            s["ร้อยละ"] = s["ครั้ง"] / s.groupby(col)["ครั้ง"].transform("sum") * 100
            ycol = "ร้อยละ" if vmode.startswith("ร้อยละ") else "ครั้ง"
            fig = px.bar(s, x=col, y=ycol, color="status", color_discrete_map=B.STATUS_COLORS,
                         category_orders={"status": B.STATUS}, labels={col: xlab, "status": "สถานะวัคซีน"},
                         hover_data={"ครั้ง": True, "ร้อยละ": ":.1f"})
            if ycol == "ร้อยละ":
                fig.update_yaxes(range=[0, 100], ticksuffix="%")
            fig.update_layout(height=400, margin=dict(t=10, b=10), legend=dict(orientation="h", y=1.08, title=""),
                              xaxis=xaxis, bargap=0.15)
            st.plotly_chart(fig, width="stretch")

        st.subheader("ร้อยละผู้ที่เคยได้รับวัคซีนมาก่อน / เคยได้รับวัคซีนตลอดชีวิต จำแนกตามชนิดสัตว์")
        flag = st.radio("ตัวชี้วัด", ["% เคยได้รับวัคซีนมาก่อนถูกกัด (had_prior_vaccine)",
                                      "% เคยได้รับวัคซีนตลอดชีวิต (ever_vaccinated_lifetime)",
                                      "% ได้รับ PEP ในครั้งนี้ (got_pep_this_episode)"], key="bite_flag")
        fcol = flag.split("(")[1].rstrip(")")
        lines = t.groupby([col, "animal"])[fcol].agg(["mean", "size"]).reset_index()
        lines = pd.concat([lines, t.groupby(col)[fcol].agg(["mean", "size"]).reset_index().assign(animal="รวม")])
        lines["pct"] = lines["mean"] * 100
        lines = lines[lines["size"] >= 5]  # hide unstable points
        fig = px.line(lines, x=col, y="pct", color="animal", markers=True,
                      color_discrete_map={**B.ANIMAL_COLORS, "รวม": "#264653"},
                      category_orders={"animal": ["รวม", *B.ANIMALS]},
                      labels={col: xlab, "pct": "ร้อยละ", "animal": "", "size": "จำนวนครั้ง"},
                      hover_data={"size": True, "pct": ":.1f"})
        fig.update_yaxes(ticksuffix="%")
        fig.update_layout(height=380, margin=dict(t=10, b=10), legend=dict(orientation="h", y=1.08), xaxis=xaxis)
        st.plotly_chart(fig, width="stretch")
        st.caption("แสดงเฉพาะจุดที่มีผู้ป่วย ≥ 5 ราย เพื่อหลีกเลี่ยงค่าร้อยละที่ผันผวนจากจำนวนน้อย")

    st.subheader("ระยะเวลาตั้งแต่ได้รับวัคซีนเข็มล่าสุดจนถึงวันที่ถูกกัด (เฉพาะผู้เคยได้รับวัคซีนมาก่อน)")
    pv = df[df["had_prior_vaccine"] & df["years_since_last_vax"].notna()].copy()
    if pv.empty:
        st.info("ไม่มีผู้ที่เคยได้รับวัคซีนมาก่อนในตัวกรองนี้")
    else:
        bins = [-0.01, 0.5, 1, 3, 5, 10, 100]
        labs = ["≤ 6 เดือน", "6 เดือน–1 ปี", "1–3 ปี", "3–5 ปี", "5–10 ปี", "> 10 ปี"]
        pv["ช่วง"] = pd.cut(pv["years_since_last_vax"], bins, labels=labs)
        h = pv.groupby(["ช่วง", "animal"], observed=False).size().rename("ครั้ง").reset_index()
        l, r = st.columns([3, 1])
        fig = px.bar(h, x="ช่วง", y="ครั้ง", color="animal", color_discrete_map=B.ANIMAL_COLORS,
                     category_orders={"animal": B.ANIMALS, "ช่วง": labs}, text_auto=True,
                     labels={"ช่วง": "ระยะห่างจากเข็มล่าสุด", "animal": "ชนิดสัตว์"})
        fig.update_layout(height=340, margin=dict(t=10, b=10), legend=dict(orientation="h", y=1.1, title=""))
        l.plotly_chart(fig, width="stretch")
        ui.kpi(r, "ค่ามัธยฐาน", f"{pv['years_since_last_vax'].median():.1f} ปี",
               f"≤ 6 เดือน: {ui.fmt_pct((pv['years_since_last_vax'] <= 0.5).sum(), len(pv))}", ui.COLORS["vax"])

    st.subheader("📋 สรุปรายปีงบประมาณ")
    y = df.groupby("fy").agg(ครั้ง=("animal", "size"),
                             สุนัข=("animal", lambda s: (s == B.ANIMALS[0]).sum()),
                             แมว_สัตว์อื่น=("animal", lambda s: (s == B.ANIMALS[1]).sum()),
                             เคยฉีดก่อน=("had_prior_vaccine", "mean"),
                             เคยฉีดตลอดชีวิต=("ever_vaccinated_lifetime", "mean"),
                             ได้PEP=("got_pep_this_episode", "mean"),
                             วันแรก=("date", "min"), วันสุดท้าย=("date", "max")).reset_index()
    y["เปลี่ยนแปลงจากปีก่อน (%)"] = y["ครั้ง"].pct_change() * 100
    for k in ("เคยฉีดก่อน", "เคยฉีดตลอดชีวิต", "ได้PEP"):
        y[k] = y[k] * 100
    y = y.rename(columns={"fy": "ปีงบประมาณ", "แมว_สัตว์อื่น": "แมว/สัตว์อื่น", "เคยฉีดก่อน": "% เคยฉีดก่อนถูกกัด",
                          "เคยฉีดตลอดชีวิต": "% เคยฉีดตลอดชีวิต", "ได้PEP": "% ได้ PEP ครั้งนี้"})
    y["วันแรก"], y["วันสุดท้าย"] = y["วันแรก"].dt.strftime("%d/%m/%Y"), y["วันสุดท้าย"].dt.strftime("%d/%m/%Y")
    st.dataframe(y.round(1), width="stretch", hide_index=True)
    st.caption("ปีงบประมาณ = 1 ต.ค. – 30 ก.ย. · ปีแรก/ปีล่าสุดอาจมีข้อมูลไม่ครบปี (ดูคอลัมน์วันแรก/วันสุดท้าย)")

# ============================================================================= MAP
with tab_map:
    st.caption("อุบัติการณ์ = จำนวนครั้งที่มารับบริการ ÷ ประชากรทะเบียนราษฎร์ × 100,000 ÷ จำนวนปี "
               "(คิดเฉพาะผู้ที่มีที่อยู่ใน อ.ปราสาท) · ใช้ตัวกรองด้านบน (วันที่/ชนิดสัตว์/เพศ)")
    mp = df[df["in_prasat"]]
    k1, k2, k3, k4 = st.columns([2, 2, 3, 1])
    m_animal = k1.selectbox("ชนิดสัตว์", ["ทุกชนิด (ตามตัวกรอง)", *B.ANIMALS], key="map_animal")
    fys = sorted(mp["fy"].unique().tolist())
    m_fy = k2.selectbox("ปีงบประมาณ", ["ทุกปี (เฉลี่ยต่อปี)", *fys], key="map_fy")
    METRICS = {
        "incidence": ("อุบัติการณ์ต่อประชากรแสนคนต่อปี", "Reds", lambda v: f"{v:,.0f}"),
        "episodes": ("จำนวนครั้งที่มารับบริการ", "OrRd", lambda v: f"{v:,.0f}"),
        "pct_prior": ("% เคยได้รับวัคซีนมาก่อนถูกกัด", "Greens", lambda v: f"{v:.1f}%"),
    }
    metric = k3.selectbox("ตัวชี้วัดบนแผนที่", list(METRICS), format_func=lambda k: METRICS[k][0], key="map_metric")
    show_val = k4.toggle("แสดงค่า", value=True, key="map_showval")

    if m_animal != "ทุกชนิด (ตามตัวกรอง)":
        mp = mp[mp["animal"] == m_animal]
    if m_fy != "ทุกปี (เฉลี่ยต่อปี)":
        mp = mp[mp["fy"] == m_fy]
        f_start, f_end = pd.Timestamp(f"{m_fy - 544}-10-01"), pd.Timestamp(f"{m_fy - 543}-09-30")
    else:
        f_start, f_end = pd.Timestamp(dmin), pd.Timestamp(dmax)
    # exposure time = overlap of selected fiscal year with date filter and with the data period
    lo = max(f_start, pd.Timestamp(rng[0]) if isinstance(rng, (list, tuple)) and len(rng) == 2 else f_start,
             raw["date"].min())
    hi = min(f_end, pd.Timestamp(rng[1]) if isinstance(rng, (list, tuple)) and len(rng) == 2 else f_end,
             raw["date"].max())
    years = max((hi - lo).days + 1, 1) / 365.25

    agg = B.incidence_by_tambon(mp, years)
    gj, centroids = ui.load_geojson()
    label, scale, fmt = METRICS[metric]
    vmax = 100 if metric == "pct_prior" else max(1.0, float(agg[metric].max()))
    fig = px.choropleth(agg, geojson=gj, locations="tambon", featureidkey="properties.tambon", color=metric,
                        color_continuous_scale=scale, range_color=(0, vmax), hover_name="tambon",
                        hover_data={"tambon": False, "pop_total": ":,", "episodes": ":,", "incidence": ":,.1f",
                                    B.ANIMALS[0]: ":,", B.ANIMALS[1]: ":,", "pct_prior": ":.1f"},
                        labels={"pop_total": "ประชากร", "episodes": "จำนวนครั้ง", "incidence": "ต่อแสนคน/ปี",
                                "pct_prior": "% เคยฉีดก่อน", metric: label})
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_traces(marker_line_color="#ffffff", marker_line_width=1.5)
    names = agg["tambon"].tolist()
    norm = [v / vmax if vmax else 0 for v in agg[metric]]
    fig.add_trace(go.Scattergeo(
        lat=[centroids[t][0] for t in names], lon=[centroids[t][1] for t in names], mode="text",
        text=[f"<b>{t}</b><br>{fmt(v)}" if show_val else f"<b>{t}</b>" for t, v in zip(names, agg[metric])],
        textfont=dict(family=ui.FONT, size=12, color=["#fff" if x > 0.6 else "#111" for x in norm]),
        hoverinfo="skip", showlegend=False))
    fig.update_layout(height=650, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      geo_bgcolor="rgba(0,0,0,0)", coloraxis_colorbar=dict(title=label.replace(" ", "<br>", 1)))
    mc1, mc2 = st.columns([3, 2])
    mc1.plotly_chart(fig, width="stretch")

    with mc2:
        tot_inc = agg["episodes"].sum() / agg["pop_total"].sum() * 100_000 / years
        ui.kpi(st, "อุบัติการณ์รวม อ.ปราสาท", f"{tot_inc:,.0f}",
               f"ต่อแสนประชากรต่อปี · {int(agg['episodes'].sum()):,} ครั้ง / {years:.2f} ปี", ui.COLORS["bitten"])
        st.write("")
        bar = agg.sort_values("incidence")
        fig = px.bar(bar, x="incidence", y="tambon", orientation="h", color="incidence",
                     color_continuous_scale="Reds", text=bar["incidence"].map(lambda v: f"{v:,.0f}"),
                     labels={"incidence": "ต่อแสนคน/ปี", "tambon": ""})
        fig.update_layout(height=560, margin=dict(t=10, b=10), coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch")

    st.subheader("อุบัติการณ์รายตำบล × ปีงบประมาณ (ต่อแสนประชากร)")
    hm = df[df["in_prasat"]]
    if m_animal != "ทุกชนิด (ตามตัวกรอง)":
        hm = hm[hm["animal"] == m_animal]
    piv = hm.pivot_table(index="tambon", columns="fy", aggfunc="size", fill_value=0)
    piv = piv.reindex(B.TAMBONS, fill_value=0)
    pop = B.POPULATION.set_index("tambon")["pop_total"].reindex(piv.index)
    rate = piv.div(pop, axis=0) * 100_000
    fig = px.imshow(rate.round(0), text_auto=",.0f", aspect="auto", color_continuous_scale="Reds",
                    labels=dict(x="ปีงบประมาณ", y="ตำบล", color="ต่อแสนคน"))
    fig.update_xaxes(type="category")
    fig.update_layout(height=560, margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("ค่าในตารางเป็นอัตราต่อแสนประชากร *ในปีงบประมาณนั้น* (ไม่ปรับตามจำนวนวัน) — ปีแรกและปีล่าสุดอาจไม่ครบปี")

    out_area = int((~df["in_prasat"]).sum())
    st.info(f"ผู้มารับบริการที่มีที่อยู่นอก อ.ปราสาท หรือไม่ทราบตำบล: {out_area:,} ครั้ง "
            f"({ui.fmt_pct(out_area, n)}) — ไม่นำมาคำนวณในแผนที่")
    show = agg.sort_values("incidence", ascending=False).rename(columns={
        "tambon": "ตำบล", "pop_total": "ประชากรทะเบียน", "episodes": "จำนวนครั้ง",
        "pct_prior": "% เคยฉีดก่อนถูกกัด", "incidence": "อุบัติการณ์/แสน/ปี"})
    st.dataframe(show.round(1), width="stretch", hide_index=True)
    st.download_button("⬇️ ดาวน์โหลดตาราง (CSV)", ui.csv_bytes(show.round(2)), "bite_incidence_by_tambon.csv",
                       "text/csv")
    st.caption(f"ประชากรฐาน: {ui.POP_SOURCE} (ใช้ค่าเดียวกันทุกปี) · ขอบเขตตำบล: OpenGISData-Thailand")

# ============================================================================= DEMOGRAPHICS
with tab_demo:
    d = df[df["sex_th"].isin(["ชาย", "หญิง"])]
    c = st.columns(4)
    ui.kpi(c[0], "อายุมัธยฐาน", f"{d['age_at_visit'].median():.0f} ปี",
           f"IQR {d['age_at_visit'].quantile(.25):.0f}–{d['age_at_visit'].quantile(.75):.0f} ปี", ui.COLORS["people"])
    ui.kpi(c[1], "เด็กอายุ < 15 ปี", ui.fmt_pct((d["age_at_visit"] < 15).sum(), len(d)),
           f"{(d['age_at_visit'] < 15).sum():,} ครั้ง", ui.COLORS["dog"])
    ui.kpi(c[2], "ผู้สูงอายุ 60+ ปี", ui.fmt_pct((d["age_at_visit"] >= 60).sum(), len(d)),
           f"{(d['age_at_visit'] >= 60).sum():,} ครั้ง", ui.COLORS["cat"])
    male, female = (d["sex_th"] == "ชาย").sum(), (d["sex_th"] == "หญิง").sum()
    ui.kpi(c[3], "ชาย : หญิง", f"{male / female:.2f} : 1" if female else "-",
           f"ชาย {male:,} · หญิง {female:,}", ui.COLORS["house"])

    l, r = st.columns(2)
    with l:
        st.subheader("พีระมิดอายุ–เพศ ของผู้ถูกกัด")
        bins5 = list(range(-1, 80, 5)) + [200]
        lab5 = [f"{i}-{i + 4}" for i in range(0, 80, 5)] + ["80+"]
        p = d.assign(ag=pd.cut(d["age_at_visit"], bins5, labels=lab5)).groupby(["ag", "sex_th"], observed=False) \
            .size().unstack(fill_value=0).reindex(columns=["ชาย", "หญิง"], fill_value=0)
        fig = go.Figure([
            go.Bar(y=lab5, x=-p["ชาย"], name="ชาย", orientation="h", marker_color=ui.COLORS["people"],
                   customdata=p["ชาย"], hovertemplate="%{y} ปี: %{customdata:,} ครั้ง<extra>ชาย</extra>"),
            go.Bar(y=lab5, x=p["หญิง"], name="หญิง", orientation="h", marker_color=ui.COLORS["unvax"],
                   hovertemplate="%{y} ปี: %{x:,} ครั้ง<extra>หญิง</extra>")])
        mx = int(p.values.max()) if p.size else 1
        ticks = [round(v) for v in (-mx, -mx / 2, 0, mx / 2, mx)]
        fig.update_layout(barmode="overlay", bargap=0.05, height=460, margin=dict(t=10, b=10),
                          xaxis=dict(tickvals=ticks, ticktext=[f"{abs(v):,}" for v in ticks], title="จำนวนครั้ง"),
                          yaxis_title="กลุ่มอายุ (ปี)", legend=dict(orientation="h", y=1.06))
        st.plotly_chart(fig, width="stretch")
    with r:
        st.subheader("ชนิดสัตว์ จำแนกตามกลุ่มอายุ")
        ag = d.groupby(["age_group", "animal"], observed=False).size().rename("ครั้ง").reset_index()
        fig = px.bar(ag, x="age_group", y="ครั้ง", color="animal", color_discrete_map=B.ANIMAL_COLORS,
                     category_orders={"animal": B.ANIMALS, "age_group": B.AGE_LABELS},
                     labels={"age_group": "กลุ่มอายุ (ปี)", "animal": "ชนิดสัตว์"})
        fig.update_layout(height=460, margin=dict(t=10, b=10), barnorm="percent", yaxis_title="ร้อยละ",
                          legend=dict(orientation="h", y=1.08, title=""))
        st.plotly_chart(fig, width="stretch")

    l, r = st.columns(2)
    with l:
        st.subheader("สถานะวัคซีน จำแนกตามกลุ่มอายุ")
        sv = d.groupby(["age_group", "status"], observed=False).size().rename("ครั้ง").reset_index()
        fig = px.bar(sv, x="age_group", y="ครั้ง", color="status", color_discrete_map=B.STATUS_COLORS,
                     category_orders={"status": B.STATUS, "age_group": B.AGE_LABELS},
                     labels={"age_group": "กลุ่มอายุ (ปี)", "status": ""})
        fig.update_layout(height=400, margin=dict(t=10, b=10), barnorm="percent", yaxis_title="ร้อยละ",
                          legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, width="stretch")
    with r:
        st.subheader("เพศ จำแนกตามชนิดสัตว์")
        sx = d.groupby(["animal", "sex_th"]).size().rename("ครั้ง").reset_index()
        fig = px.bar(sx, x="animal", y="ครั้ง", color="sex_th", barmode="group", text_auto=",",
                     color_discrete_map={"ชาย": ui.COLORS["people"], "หญิง": ui.COLORS["unvax"]},
                     category_orders={"animal": B.ANIMALS}, labels={"animal": "", "sex_th": "เพศ"})
        fig.update_layout(height=400, margin=dict(t=10, b=10), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, width="stretch")

    st.subheader("สถานที่และกิจกรรมขณะถูกกัด (จากรหัส ICD-10 หลักที่ 4 และ 5)")
    l, r = st.columns(2)
    for colname, title, box in (("place", "สถานที่เกิดเหตุ", l), ("activity", "กิจกรรมขณะเกิดเหตุ", r)):
        pc = d.groupby([colname, "animal"]).size().rename("ครั้ง").reset_index()
        order = d[colname].value_counts().index.tolist()[::-1]
        fig = px.bar(pc, y=colname, x="ครั้ง", color="animal", orientation="h", color_discrete_map=B.ANIMAL_COLORS,
                     category_orders={colname: order, "animal": B.ANIMALS}, labels={colname: "", "animal": ""},
                     title=title)
        fig.update_layout(height=400, margin=dict(t=40, b=10), legend=dict(orientation="h", y=-0.15))
        box.plotly_chart(fig, width="stretch")
    st.caption("รหัส W54/W55 หลักที่ 4 = สถานที่, หลักที่ 5 = กิจกรรม · ส่วนใหญ่ลงรหัส 9 (ไม่ระบุ) — "
               "ควรส่งเสริมการบันทึกรหัสให้ละเอียดขึ้น")

    st.subheader("ช่วงเวลาที่มารับบริการ")
    l, r = st.columns(2)
    with l:
        hw = d.dropna(subset=["hour"]).pivot_table(index="dow", columns="hour", aggfunc="size", fill_value=0) \
            .reindex(index=B.TH_DOW, columns=range(24), fill_value=0)
        fig = px.imshow(hw, aspect="auto", color_continuous_scale="Blues",
                        labels=dict(x="ชั่วโมง", y="", color="ครั้ง"), title="วันในสัปดาห์ × ชั่วโมง")
        fig.update_layout(height=360, margin=dict(t=40, b=10))
        st.plotly_chart(fig, width="stretch")
    with r:
        mo = d.groupby(["month_num", "animal"]).size().rename("ครั้ง").reset_index()
        nyears = d.groupby("month_num")["year_be"].nunique().rename("ny")
        mo = mo.merge(nyears, on="month_num")
        mo["เฉลี่ยต่อเดือน"] = mo["ครั้ง"] / mo["ny"]
        mo["เดือน"] = mo["month_num"].map(lambda m: B.TH_MONTH[m - 1])
        fig = px.line(mo, x="เดือน", y="เฉลี่ยต่อเดือน", color="animal", markers=True,
                      color_discrete_map=B.ANIMAL_COLORS, category_orders={"เดือน": B.TH_MONTH,
                                                                           "animal": B.ANIMALS},
                      labels={"animal": ""}, title="ฤดูกาล: ค่าเฉลี่ยจำนวนครั้งต่อเดือน")
        fig.update_layout(height=360, margin=dict(t=40, b=10), legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, width="stretch")
