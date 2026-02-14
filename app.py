import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 시스템 설정] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# 세션 상태 초기화 (캐시 꼬임 방지)
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.clear()
    st.rerun()

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
    try:
        if not os.path.exists(f_path):
            r = requests.get(f_url, timeout=10)
            with open(f_path, "wb") as f: f.write(r.content)
        return ImageFont.truetype(f_path, int(size))
    except:
        return ImageFont.load_default()

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return rgb + (alpha,)

# --- [2. Strava 인증 로직] ---
# URL 파라미터 감지
q_params = st.query_params
if "code" in q_params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": q_params["code"], "grant_type": "authorization_code"
        }, timeout=15)
        
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            # 중요: 인증 성공 직후 파라미터 초기화하여 캐시 충돌 방지
            st.query_params.clear()
            st.rerun()
        else:
            st.error("인증 코드가 만료되었거나 올바르지 않습니다. 다시 로그인해 주세요.")
            st.query_params.clear()
    except Exception as e:
        st.error(f"인증 연결 중 오류 발생: {e}")

# 인증 토큰이 없으면 로그인 화면 출력
if not st.session_state['access_token']:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
                f"&response_type=code&redirect_uri={ACTUAL_URL}"
                f"&scope=activity:read_all&approval_prompt=force")
    st.markdown("### 🔑 Strava 연동이 필요합니다")
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [3. 데이터 로드 (인증 유효성 실시간 체크)] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
try:
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers, timeout=15)
    if act_res.status_code == 401: # 토큰 만료 시 자동 로그아웃
        logout()
    acts = act_res.json() if act_res.status_code == 200 else []
except:
    acts = []

# --- [4. UI 및 렌더링 로직] ---
# (이하 활동명 90, 날짜 30, 숫자 60, 소문자 km/bpm 등 기존 디자인 설정 적용)
col1, col2, col3 = st.columns([1, 2, 1], gap="medium")
# ... (기존 UI 구성 코드와 동일)
