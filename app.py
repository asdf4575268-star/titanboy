import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl

# --- [1. 기본 설정 및 제목] ---
st.set_page_config(page_title="TITAN BOY", layout="wide")
mpl.use('Agg')

API_CONFIGS = {
    "PRIMARY": {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'},
    "SECONDARY": {"ID": '202274', "SECRET": '63f6a7007ebe6b405763fc3104e17bb53b468ad0'}
}
CURRENT_CFG = API_CONFIGS["PRIMARY"] 
CLIENT_ID, CLIENT_SECRET = CURRENT_CFG["ID"], CURRENT_CFG["SECRET"]
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

# --- [2. 세션 및 인증 로직] ---
if 'access_token' not in st.session_state: st.session_state['access_token'] = None

def logout_and_clear():
    st.cache_data.clear(); st.cache_resource.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": query_params["code"], "grant_type": "authorization_code"}).json()
    if 'access_token' in res: st.session_state['access_token'] = res['access_token']; st.query_params.clear(); st.rerun()

# --- [메인 상단: TITAN BOY & Strava 버튼] ---
st.title("TITAN BOY")

if st.session_state['access_token'] is None:
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url, use_container_width=True)
else:
    col_status, col_logout = st.columns([4, 1])
    with col_status: st.success("✅ Strava 연결됨")
    with col_logout: st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)

# --- [3. 사이드바: 입력 및 설정창 숨기기] ---
with st.sidebar:
    st.header("⚙️ SETTINGS")
    mode = st.radio("모드 선택", ["DAILY", "WEEKLY"], horizontal=True)
    
    st.subheader("📸 FILES")
    bg_files = st.file_uploader("배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("원형 로고", type=['jpg','jpeg','png'])
    
    st.subheader("✍️ MANUAL INPUT")
    # 초기값 변수 선언
    v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", datetime.now().strftime("%Y-%m-%d"), "0.00", "00:00:00", "0'00\"", "0"
    
    # 데이터 로드 (Strava)
    acts = []
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
    if st.session_state['access_token']:
        r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)
        if r.status_code == 200: acts = r.json()
    
    a = None
    if acts:
        act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
        sel_str = st.selectbox("활동 선택", act_options)
        a = acts[act_options.index(sel_str)]
        if mode == "DAILY":
            d_km = a.get('distance', 0)/1000; m_sec = a.get('moving_time', 0)
            v_act, v_date, v_dist = a['name'], a['start_date_local'][:10], f"{d_km:.2f}"
            v_time = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}"
            v_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
            v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
    
    # 사이드바 입력창
    v_act = st.text_input("활동명", v_act)
    v_date = st.text_input("날짜", v_date)
    v_dist = st.text_input("거리", v_dist)
    v_time = st.text_input("시간", v_time)
    v_pace = st.text_input("페이스", v_pace)
    v_hr = st.text_input("심박", v_hr)

    st.subheader("🎨 DESIGN")
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color = st.color_picker("포인트 컬러", "#FFD700")
    sub_color = st.color_picker("서브 컬러", "#FFFFFF")
    
    ry = st.number_input("Y 위치", 0, 1920, 1400 if mode=="DAILY" else 750)
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    vis_sz = st.slider("지도/그래프 크기", 50, 1080, 200 if mode=="DAILY" else 1080)
    vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 150)

# --- [4. 메인 영역: 결과물 출력 (2열 역할)] ---
# (함수 로드 및 렌더링 로직은 기존과 동일하되, 변수만 사이드바 것을 참조)
# ... [이전 답변의 유틸리티 함수(load_font, hex_to_rgba, create_bar_chart 등) 포함] ...

# [렌더링 실행부 예시]
try:
    # 캔버스 및 폰트 설정 (생략된 함수들은 기존 코드 유지)
    CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1080)
    f_t, f_d, f_n, f_l = load_font(sel_font, 90), load_font(sel_font, 30), load_font(sel_font, 60), load_font(sel_font, 20)
    
    if bg_files:
        canvas = ImageOps.fit(ImageOps.exif_transpose(Image.open(bg_files[0])).convert("RGBA"), (CW, CH))
    else:
        canvas = Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
    
    overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)

    # ... [가로모드 중앙 정렬 및 4분할 로직 적용] ...
    # (위 답변에서 드린 6. 렌더링 엔진 코드를 이곳에 넣으시면 됩니다.)

    st.image(canvas if not overlay else Image.alpha_composite(canvas, overlay).convert("RGB"), use_container_width=True)
    # 다운로드 버튼 등...
except:
    st.info("왼쪽 사이드바에서 사진을 올리거나 Strava 기록을 선택해 주세요.")
