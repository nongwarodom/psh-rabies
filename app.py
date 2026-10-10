"""แดชบอร์ดสำรวจโรคพิษสุนัขบ้า อำเภอปราสาท จังหวัดสุรินทร์

Run:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="แดชบอร์ดพิษสุนัขบ้า อ.ปราสาท", page_icon="🐕", layout="wide")

from rabies import ui  # noqa: E402  (after set_page_config)

ui.inject_css()

df, raw, log, excluded, stats, source_note, loaded_at = ui.load_data()
st.session_state.update(df_all=df, df_raw=raw, df_log=log, df_excluded=excluded,
                        stats=stats, source_note=source_note)

st.sidebar.markdown("## 🐕 สำรวจพิษสุนัขบ้า\n**อำเภอปราสาท จ.สุรินทร์**")
st.session_state["df_filtered"] = ui.sidebar_filters(df)

st.sidebar.divider()
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
    st.Page("views/area.py", title="รายตำบล/หมู่บ้าน", icon="🏘️"),
    st.Page("views/quality.py", title="คุณภาพข้อมูล", icon="🧹"),
]
st.navigation(pages).run()
