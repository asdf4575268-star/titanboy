import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 기본 설정] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# 세션 상태 초기화
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

def logout():
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()

# --- [2. 인증 로직 - 최상단 배치] ---
query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    # Strava에서 돌아온 직후 처리
    code = query_params["code"]
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": code, "grant_type": "authorization_code"
    })
    if res.status_code == 200:
        st.session_state['access_token'] = res.json()['access_token']
        st.query_params.clear() # URL 파라미터 삭제 (중요)
        st.rerun()
    else:
        st.error("인증 토큰 교환에 실패했습니다. 다시 시도해주세요.")

# 로그인이 안 되어 있으면 로그인 화면만 출력
if st.session_state['access_token'] is None:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
                f"&response_type=code&redirect_uri={ACTUAL_URL}"
                f"&scope=activity:read_all&approval_prompt=force")
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [3. 메인 앱 로직 - 인증 성공 시에만 실행] ---
@st.cache_resource
def load_font(font_type, size):
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf",
        "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf",
        "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Bold.ttf"
    }
    f_url = fonts.get(font_type, fonts["BlackHanSans"])
    f_path = f"font_{font_type}_{int(size)}.ttf"
    if not os.path.exists(f_path):
        r = requests.get(f_url); f = open(f_path, "wb"); f.write(r.content); f.close()
    return ImageFont.truetype(f_path, int(size))

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return rgb + (alpha,)

# 데이터 로드
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)
if act_res.status_code == 401: logout() # 인증 만료 시 로그아웃
acts = act_res.json() if act_res.status_code == 200 else []

# --- [UI 레이아웃] ---
col1, col2, col3 = st.columns([1, 2, 1], gap="medium")
COLOR_OPTIONS = {"Garmin Yellow": "#FFD700", "Pure White": "#FFFFFF", "Neon Orange": "#FF4500", "Electric Blue": "#00BFFF", "Soft Grey": "#AAAAAA"}

with col2:
    mode = st.radio("작업 모드", ["DAILY", "WEEKLY"], horizontal=True)
    if mode == "DAILY" and acts:
        sel_str = st.selectbox("기록 선택", [f"{a['start_date_local'][:10]} - {a['name']}" for a in acts])
        idx = [f"{x['start_date_local'][:10]} - {x['name']}" for x in acts].index(sel_str)
        a = acts[idx]
        d_km, m_sec = a.get('distance', 0)/1000, a.get('moving_time', 0)
        p_val = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
        h_val = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        t_val = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"
    elif mode == "WEEKLY" and acts:
        w_acts = acts[:7]
        t_dist = sum([x.get('distance', 0) for x in w_acts]) / 1000
        t_time = sum([x.get('moving_time', 0) for x in w_acts])
        avg_p_val = f"{int((t_time/t_dist)//60)}'{int((t_time/t_dist)%60):02d}\"" if t_dist > 0 else "0'00\""
        t_hrs = [x.get('average_heartrate', 0) for x in w_acts if x.get('average_heartrate')]
        avg_hr = int(sum(t_hrs)/len(t_hrs)) if t_hrs else 0
        t_val_w = f"{int(t_time//3600)}h {int((t_time%3600)//60)}m"

with col1:
    st.header("📸 DATA")
    bg_files = st.file_uploader("사진 선택", type=['jpg','jpeg','png'], accept_multiple_files=True)
    if mode == "DAILY":
        v_act, v_date = st.text_input("활동명", a['name']), st.text_input("날짜", a['start_date_local'][:10])
        v_dist, v_pace, v_hr = st.text_input("거리(km)", f"{d_km:.2f}"), st.text_input("페이스(분/km)", p_val), st.text_input("심박(bpm)", h_val)
    else:
        v_act_w = st.text_input("주간 제목", "WEEKLY RECAP")
        v_dist_w, v_time_w, v_pace_w, v_hr_w = st.text_input("총 거리", f"{t_dist:.2f} km"), st.text_input("총 시간", t_val_w), st.text_input("평균 페이스", avg_p_val), st.text_input("평균 심박", f"{avg_hr} bpm")

with col3:
    st.header("🎨 DESIGN")
    show_box = st.checkbox("로그 박스 표시", value=True)
    sel_font = st.selectbox("폰트 선택", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    sel_m_color, sel_sub_color = st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()), index=0), st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)
    m_color, sub_color = COLOR_OPTIONS[sel_m_color], COLOR_OPTIONS[sel_sub_color]
    t_sz, d_sz, n_sz = st.slider("활동명(90)", 10, 200, 90), st.slider("날짜(30)", 5, 100, 30), st.slider("숫자(60)", 10, 200, 60)
    l_sz = st.slider("라벨 크기", 5, 80, 20)
    if mode == "DAILY":
        rx, ry = st.slider("X 위치", 0, 1080, 70), st.slider("Y 위치", 0, 1920, 1150)
        rw, rh = st.slider("박스 너비", 100, 1080, 600), st.slider("박스 높이", 100, 1500, 650)
        box_alpha = st.slider("박스 투명도", 0, 255, 110)
        map_size, map_alpha = st.slider("지도 크기", 50, 400, 150), st.slider("지도 투명도", 0, 255, 255)

# --- [렌더링 로직 생략 (기존과 동일)] ---
# ... (기존의 DAILY/WEEKLY 이미지 생성 및 다운로드 버튼 코드 포함)

st.sidebar.button("🔓 로그아웃", on_click=logout)
