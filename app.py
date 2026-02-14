import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl

# --- [1. 기본 설정] ---
st.set_page_config(page_title="TITAN BOY", layout="wide")
mpl.use('Agg')

API_CONFIGS = {
    "PRIMARY": {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'},
    "SECONDARY": {"ID": '202274', "SECRET": '63f6a7007ebe6b405763fc3104e17bb53b468ad0'}
}
CURRENT_CFG = API_CONFIGS["PRIMARY"] 
CLIENT_ID, CLIENT_SECRET = CURRENT_CFG["ID"], CURRENT_CFG["SECRET"]
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

if 'access_token' not in st.session_state: st.session_state['access_token'] = None

def logout_and_clear():
    st.cache_data.clear(); st.cache_resource.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

# --- [2. 인증 로직] ---
query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": query_params["code"], "grant_type": "authorization_code"
        }, timeout=15).json()
        if 'access_token' in res:
            st.session_state['access_token'] = res['access_token']
            st.query_params.clear(); st.rerun()
    except: pass

# --- [3. 사이드바: 오직 Manual Edit만] ---
with st.sidebar:
    st.header("✍️ MANUAL EDIT")
    # 아래 메인 로직에서 결정된 값을 편집할 수 있도록 구성
    v_act = st.text_input("활동명")
    v_date = st.text_input("날짜")
    v_dist = st.text_input("거리 km")
    v_time = st.text_input("시간")
    v_pace = st.text_input("페이스")
    v_hr = st.text_input("심박 bpm")

# --- [4. 메인 상단: TITAN BOY & Strava] ---
st.title("TITAN BOY")
if st.session_state['access_token'] is None:
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url, use_container_width=True)
else:
    c_status, c_logout = st.columns([4, 1])
    with c_status: st.success("✅ Strava 연결됨")
    with c_logout: st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)

st.divider()

# --- [5. 메인 2열 구성] ---
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("📝 ACTIVITY & FILES")
    mode = st.radio("모드 선택", ["DAILY", "WEEKLY"], horizontal=True)
    
    bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("🔘 원형 로고", type=['jpg','jpeg','png'])
    
    # 데이터 로드
    acts = []
    if st.session_state['access_token']:
        headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
        r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)
        if r.status_code == 200: acts = r.json()
    
    a = None
    if acts:
        act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
        sel_str = st.selectbox("🏃 활동 선택", act_options)
        a = acts[act_options.index(sel_str)]
        # 기본값 세팅 (사이드바 입력창과 연동하려면 session_state 활용 권장하나, 여기선 로직 흐름 유지)
        if not v_act: # 수동 입력이 없을 때만 스트라바 데이터 적용
            d_km = a.get('distance', 0)/1000; m_sec = a.get('moving_time', 0)
            v_act, v_date, v_dist = a['name'], a['start_date_local'][:10], f"{d_km:.2f}"
            v_time = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}"
            v_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
            v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"

with col_right:
    st.subheader("🎨 DESIGN")
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트 선택", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    
    c1, c2 = st.columns(2)
    with c1: m_color = st.color_picker("포인트 컬러", "#FFD700")
    with c2: sub_color = st.color_picker("서브 컬러", "#FFFFFF")
    
    ry = st.number_input("박스 Y 위치", 0, 1920, 1400 if mode=="DAILY" else 750)
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    vis_sz = st.slider("지도/그래프 크기", 50, 1080, 200 if mode=="DAILY" else 1080)
    vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 150)

# --- [6. 하단 결과물 미리보기] ---
st.divider()
st.subheader("🖼️ PREVIEW")

try:
    # (폰트 로드 및 렌더링 로직 - 가로모드 1080 고정 및 가운데 정렬 적용)
    # ... 이전 렌더링 코드와 동일 ...
    
    # 렌더링 후 이미지 표시
    # st.image(final_img, use_container_width=True)
    # st.download_button(...)
    st.info("설정을 완료하면 아래에 이미지가 생성됩니다.")
except:
    pass
