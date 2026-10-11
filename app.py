"""แดชบอร์ดสำรวจโรคพิษสุนัขบ้า อำเภอปราสาท จังหวัดสุรินทร์

Run:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="แดชบอร์ดพิษสุนัขบ้า อ.ปราสาท", page_icon="assets/psh_icon.png", layout="wide")

from rabies import osm, ui  # noqa: E402  (after set_page_config)

ui.inject_css()
# Logo sits at the very top of the sidebar, above the page menu (size enlarged via CSS in ui.py)
st.logo("assets/psh_logo.png", size="large", icon_image="assets/psh_icon.png")

df, raw, log, excluded, stats, source_note, loaded_at = ui.load_data()
osm_data, _, _ = osm.load()
combined = ui.combine(df, osm.to_rows(osm_data))
st.session_state.update(df_all=df, df_combined=combined, df_raw=raw, df_log=log, df_excluded=excluded,
                        stats=stats, source_note=source_note)

st.sidebar.markdown("## 🐕 สำรวจพิษสุนัขบ้า\n**อำเภอปราสาท จ.สุรินทร์**")
st.session_state["df_filtered"] = ui.sidebar_filters(combined)

st.sidebar.divider()
st.sidebar.markdown('<div class="credit">โดย กลุ่มงานเวชกรรมสังคม<br>โรงพยาบาลปราสาท</div>',
                    unsafe_allow_html=True)
if st.sidebar.button("🔄 ดึงข้อมูลล่าสุด", width="stretch"):
    ui.load_data.clear()
    st.rerun()
st.sidebar.caption(f"แหล่งข้อมูล: {source_note}\n\nอัปเดต: {loaded_at:%d/%m/%Y %H:%M:%S} "
                   f"(รีเฟรชอัตโนมัติทุก 5 นาที)")

pages = [
    st.Page("views/overview.py", title="ภาพรวม", icon="📊", default=True),
    st.Page("views/map.py", title="แผนที่ GIS", icon="🗺️"),
    st.Page("views/people.py", title="ประชากรและการถูกกัด", icon="🧑‍⚕️"),
    st.Page("views/animals.py", title="สัตว์เลี้ยงและวัคซีน", icon="🐶"),
    st.Page("views/osm.py", title="ผลสำรวจ อสม.", icon="🚪"),
    st.Page("views/area.py", title="รายตำบล/หมู่บ้าน", icon="🏘️"),
    st.Page("views/quality.py", title="คุณภาพข้อมูล", icon="🧹"),
]
st.navigation(pages).run()
