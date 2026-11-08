"""메뉴 1 — 제안요청서 작성 화면 (v1 app.py에서 이동)."""
import hashlib
from datetime import date, datetime, time
from io import BytesIO

import streamlit as st

from core import rfq_core as core
from core.common import DEFAULT_SUPPLIERS, DEFAULT_TEMPLATE

st.title("📝 제안요청서 작성")
st.caption("구매요청서 엑셀을 올리면 구매요청 건별 × 협력사별 제안요청서(.docx)를 만들어 드립니다.")


def _digest(data):
    return hashlib.md5(data).hexdigest()[:12]


# ---------------------------------------------------------------- ① 파일 올리기
st.header("① 파일 올리기")
req_file = st.file_uploader("구매요청서 (.xlsx)", type=["xlsx"], key="req_file")

with st.expander("양식·협력사목록 바꾸기 (선택)"):
    st.caption("올리지 않으면 기본 내장 파일을 사용합니다.")
    tpl_file = st.file_uploader("제안요청서 양식 (.docx)", type=["docx"], key="tpl_file")
    sup_file = st.file_uploader("협력사목록 (.xlsx)", type=["xlsx"], key="sup_file")

if tpl_file is not None:
    template_bytes, template_name = tpl_file.getvalue(), tpl_file.name
else:
    template_bytes, template_name = DEFAULT_TEMPLATE.read_bytes(), "기본 양식"
if sup_file is not None:
    sup_bytes, sup_name = sup_file.getvalue(), sup_file.name
else:
    sup_bytes, sup_name = DEFAULT_SUPPLIERS.read_bytes(), "기본 협력사목록"

st.caption(f"사용 중: 양식 = {template_name} / 협력사목록 = {sup_name}")

try:
    core.validate_template(template_bytes)
except core.TemplateError as e:
    st.error(str(e))
    st.stop()

try:
    suppliers = core.load_suppliers(BytesIO(sup_bytes))
except core.ColumnError as e:
    st.error(f"협력사목록에 필수 열이 없습니다: **{', '.join(e.missing)}**")
    st.stop()
except Exception as e:
    st.error(f"협력사목록을 읽을 수 없습니다: {e}")
    st.stop()

shared = st.session_state.get("shared_req")
if req_file is not None:
    req_bytes = req_file.getvalue()
    st.session_state["shared_req"] = {"name": req_file.name, "bytes": req_bytes}
elif shared:
    req_bytes = shared["bytes"]
    st.caption(f"앞서 올린 구매요청서 사용 중: {shared['name']} (새로 올리면 바뀝니다)")
else:
    st.info("구매요청서 엑셀 파일을 올려 주세요.")
    st.stop()

try:
    requests = core.load_requests(BytesIO(req_bytes))
except core.ColumnError as e:
    st.error(f"구매요청서에 필수 열이 없습니다: **{', '.join(e.missing)}**")
    st.stop()
except Exception as e:
    st.error(f"구매요청서를 읽을 수 없습니다: {e}")
    st.stop()

# ---------------------------------------------------------------- ② 작성 설정
st.header("② 작성 설정")
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    req_date = st.date_input("요청일", value=date.today(), format="YYYY-MM-DD")

# 요청일이 바뀌면 회신 기한을 다시 계산한다
if st.session_state.get("_last_req_date") != req_date or "deadline_date" not in st.session_state:
    st.session_state["_last_req_date"] = req_date
    st.session_state["deadline_date"] = core.add_business_days(req_date, 3)
    st.session_state["deadline_time"] = time(17, 0)

with c2:
    deadline_date = st.date_input("견적 회신 기한 (날짜)", key="deadline_date", format="YYYY-MM-DD",
                                  help="요청일 + 3영업일(토·일 제외)로 자동 계산됩니다. 공휴일은 직접 고쳐 주세요.")
with c3:
    deadline_time = st.time_input("견적 회신 기한 (시각)", key="deadline_time", step=1800)

deadline = core.format_deadline(deadline_date, deadline_time.strftime("%H:%M"))
st.markdown(f"요청서에 들어갈 회신 기한: **{deadline}**")
if deadline_date.weekday() >= 5:
    st.warning("회신 기한이 주말입니다.")
if deadline_date <= req_date:
    st.warning("회신 기한이 요청일과 같거나 이전입니다.")

# ---------------------------------------------------------------- ③ 대상 확인
st.header("③ 대상 확인")
targets, warns, infos = core.build_targets(requests, suppliers)

for msg in infos:
    st.info(msg)
for msg in warns:
    st.warning(msg)

if targets.empty:
    st.error("제안요청서를 만들 대상이 없습니다.")
    st.stop()

n_pr = targets["요청번호"].nunique()
st.markdown(f"#### 구매요청 {n_pr}건 → 제안요청서 {len(targets)}건 예정")

view = targets.copy()
view["수량"] = view["수량"] + " " + view["단위"]
view = view[["포함", "요청번호", "품목", "수량", "희망 납기", "협력사", "담당자", "비고"]]

editor_key = f"editor_{_digest(req_bytes)}_{_digest(sup_bytes)}"
edited = st.data_editor(
    view,
    key=editor_key,
    hide_index=True,
    width="stretch",
    disabled=[c for c in view.columns if c != "포함"],
    column_config={
        "포함": st.column_config.CheckboxColumn("포함", help="체크를 풀면 이번에 만들지 않습니다."),
        "비고": st.column_config.TextColumn("비고 (화면에만 표시)"),
    },
)

with st.expander("협력사 연락처 보기"):
    st.dataframe(
        targets[["협력사", "담당자", "전화", "이메일", "결제 조건", "비고"]].drop_duplicates(),
        hide_index=True, width="stretch",
    )

selected = targets[edited["포함"].fillna(False).astype(bool).values]
st.caption(f"선택: {len(selected)}건 / 전체 {len(targets)}건")

# ---------------------------------------------------------------- ④ 만들기
st.header("④ 만들기")
signature = (
    _digest(req_bytes), _digest(sup_bytes), _digest(template_bytes),
    str(req_date), deadline, tuple(selected["RFQ번호"]),
)
if st.button("제안요청서 만들기", key="rfq_make", type="primary", disabled=selected.empty):
    files, results = [], []
    with st.spinner("제안요청서를 만드는 중입니다..."):
        for _, row in selected.iterrows():
            data = core.make_rfq_docx(template_bytes, row, req_date, deadline)
            name = core.make_filename(row)
            files.append((name, data))
            results.append({"RFQ번호": row["RFQ번호"], "협력사": row["협력사"], "품목": row["품목"],
                            "파일명": name, "data": data})
    st.session_state["rfq_results"] = {
        "signature": signature,
        "items": results,
        "zip": core.make_zip(files),
        "zip_name": core.zip_filename(req_date),
        "made_at": datetime.now().strftime("%H:%M:%S"),
    }
if selected.empty:
    st.caption("체크된 건이 없어 만들 수 없습니다.")

# ---------------------------------------------------------------- ⑤ 결과 목록
res = st.session_state.get("rfq_results")
if res:
    st.header("⑤ 결과 목록")
    if res["signature"] != signature:
        st.warning("파일이나 설정이 바뀌었습니다. 아래 결과는 이전 설정 기준이니 [제안요청서 만들기]를 다시 눌러 주세요.")
    st.success(f"{len(res['items'])}건 생성 완료 ({res['made_at']})")
    st.download_button(
        f"📦 전체 ZIP 다운로드 ({res['zip_name']})", data=res["zip"], file_name=res["zip_name"],
        mime="application/zip", type="primary", on_click="ignore",
    )
    head = st.columns([3, 2, 3, 2])
    for col, title in zip(head, ["요청번호", "협력사", "품목", "파일"]):
        col.markdown(f"**{title}**")
    for i, item in enumerate(res["items"]):
        cols = st.columns([3, 2, 3, 2])
        cols[0].write(item["RFQ번호"])
        cols[1].write(item["협력사"])
        cols[2].write(item["품목"])
        cols[3].download_button(
            "다운로드", data=item["data"], file_name=item["파일명"], key=f"dl_{i}",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            on_click="ignore", help=item["파일명"],
        )
