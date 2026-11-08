"""구매 견적 도우미 — 진입점: 메뉴 구성, 공통 사이드바."""
import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core import ai_client  # noqa: E402

st.set_page_config(page_title="구매 견적 도우미", page_icon="🧾", layout="wide")

nav = st.navigation([
    st.Page(APP_DIR / "pages" / "rfq_page.py", title="제안요청서 작성", icon="📝", url_path="rfq", default=True),
    st.Page(APP_DIR / "pages" / "quote_page.py", title="견적 분석·협상전략", icon="📊", url_path="quote"),
])

with st.sidebar:
    st.divider()
    has_key, model = ai_client.status()
    if has_key:
        st.markdown(f"AI 연결 상태: :green[● 연결됨]  \n모델: `{model}`")
    else:
        st.markdown("AI 연결 상태: :gray[○ API 키 없음]")
        st.caption("견적 분석 메뉴를 쓰려면 아래 'AI 설정'에서 API 키를 저장하세요.")

    with st.expander("AI 설정", expanded=not has_key):
        with st.form("ai_settings", clear_on_submit=True):
            new_key = st.text_input("API 키", type="password",
                                    placeholder="새 키를 붙여 넣으세요" if has_key else "sk-ant-...")
            new_model = st.text_input("모델", value=model)
            saved = st.form_submit_button("저장 (.env 파일)")
        if saved:
            ai_client.save_settings(key=new_key or None, model=new_model)
            try:
                used = ai_client.test_connection()
                st.session_state["ai_msg"] = ("success", f"저장했습니다. 연결 확인 완료 ({used})")
            except ai_client.AIError as e:
                st.session_state["ai_msg"] = ("error", f"저장했지만 연결 확인에 실패했습니다: {e}")
            st.rerun()  # 연결 상태·메뉴 2 화면에 새 설정 반영
        msg = st.session_state.pop("ai_msg", None)
        if msg:
            getattr(st, msg[0])(msg[1])
        st.caption("키는 이 프로그램 폴더의 .env 파일에 저장됩니다. 폴더를 다른 사람에게 줄 때는 .env를 빼고 주세요.")
    shared = st.session_state.get("shared_req")
    if shared:
        st.caption(f"구매요청서: {shared['name']}")

nav.run()
