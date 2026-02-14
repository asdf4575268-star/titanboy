import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 기본 설정] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

def logout_and_clear():
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state.clear()
    st.query_params.clear()

if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# --- [2. 인증 로직] ---
query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": query_params["code"], "grant_type": "authorization_code"
        }, timeout=15)
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            st.query_params.clear()
            st.rerun()
    except: pass

if st.session_state['access_token'] is None:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
                f"&response_type=code&redirect_uri={ACTUAL_URL}"
                f"&scope=read,activity:read_all&approval_prompt=force")
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [3. 유틸리티 함수 - 요청하신 구글 스포츠 폰트 7종 추가] ---
@st.cache_resource
def load_font(font_type, size):
    fonts = {
        "Tourney": "https://fonts.gstatic.com/s/tourney/v20/rax_Hi1k7QO8wH_j.ttf",
        "Racing Sans One": "https://fonts.gstatic.com/s/racingsansone/v11/sy0e75S_P8qS5YfN08Wv7HqlY7S_.ttf",
        "Playball": "https://fonts.gstatic.com/s/playball/v18/p9X9badmBD_9ioRkae_6.ttf",
        "Audiowide": "https://fonts.gstatic.com/s/audiowide/v16/skcB5BR_3iof8f0BkPh7.ttf",
        "Oswald": "https://fonts.gstatic.com/s/oswald/v49/TK3iW63_YCWgaMoNgxwp.ttf",
        "Montserrat": "https://fonts.gstatic.com/s/montserrat/v25/JTUHjIg1_i6t8kCHKm4532VJOt5-Qfcn9R_c8dT.ttf",
        "League Spartan": "https://fonts.gstatic.com/s/leaguespartan/v11/kJEnBuEW6A7V3W56_f_Xpbe789u27A.ttf"
    }
    
    url = fonts.get(font_type, fonts["Oswald"])
    f_path = f"{font_type}_{int(size)}.ttf"
    
    try:
        if not os.path.exists(f_path):
            r = requests.get(url, timeout=10)
            with open(f_path, "wb") as f: f.write(r.content)
        return ImageFont.truetype(f_path, int(size))
    except:
        return ImageFont.load_default()

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return rgb + (alpha,)

# --- [4. 데이터 로드] ---
acts = []
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
try:
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers, timeout=15)
    if act_res.status_code == 200: acts = act_res.json()
except: pass

# --- [5. UI 레이아웃] ---
col1, col2, col3 = st.columns([1.2, 2, 1], gap="medium")
COLOR_OPTIONS = {"Garmin Yellow": "#FFD700", "Pure White": "#FFFFFF", "Neon Orange": "#FF4500", "Electric Blue": "#00BFFF", "Soft Grey": "#AAAAAA"}

with col2:
    mode = st.radio("모드", ["DAILY", "WEEKLY"], horizontal=True, label_visibility="collapsed")
    if mode == "DAILY" and acts:
        act_options = [f"{a['start_date_local'][:10]} - {a['name']}" for a in acts]
        sel_str = st.selectbox("기록 선택", act_options)
        a = acts[act_options.index(sel_str)]
        d_km, m_sec = a.get('distance', 0)/1000, a.get('moving_time', 0)
        p_val = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
        h_val = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        t_val = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"

with col1:
    st.header("📸 DATA")
    bg_files = st.file_uploader("배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("원형 로고", type=['jpg','jpeg','png'])
    if mode == "DAILY" and acts:
        v_act, v_date = st.text_input("활동명", a['name']), st.text_input("날짜", a['start_date_local'][:10])
        v_dist, v_pace, v_hr = st.text_input("거리(km)", f"{d_km:.2f}"), st.text_input("페이스(분/km)", p_val), st.text_input("심박(bpm)", h_val)
    elif mode == "WEEKLY" and acts:
        v_act_w = st.text_input("제목", "WEEKLY RECAP")
        # 위클리 데이터 로직은 생략 (기존과 동일)

with col3:
    st.header("🎨 DESIGN")
    show_box = st.checkbox("로그 박스 표시", value=True)
    # 구글 스포츠 폰트 목록으로 교체
    sel_font = st.selectbox("폰트 선택", ["Tourney", "Racing Sans One", "Playball", "Audiowide", "Oswald", "Montserrat", "League Spartan"])
    m_color = COLOR_OPTIONS[st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()))]
    sub_color = COLOR_OPTIONS[st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)]
    
    # 요청하신 고정 크기 (90, 30, 60)
    t_sz, d_sz, n_sz, l_sz = 90, 30, 60, 20
    
    if mode == "DAILY":
        rx, ry = st.number_input("X 위치", 0, 1080, 70), st.number_input("Y 위치", 0, 1920, 1350)
        rw, rh = st.number_input("박스 너비", 100, 1080, 500), st.number_input("박스 높이", 100, 1920, 500)
        box_alpha, map_size = st.slider("박스 투명도", 0, 255, 100), st.slider("지도 크기", 50, 400, 160)

# --- [6. 렌더링 엔진] ---
if bg_files:
    try:
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        if mode == "DAILY":
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920))
            overlay = Image.new("RGBA", (1080, 1920), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            if show_box:
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
                # 지도 및 텍스트 렌더링 (소문자 km, bpm 적용)
                items = [("distance", f"{v_dist} km"), ("time", t_val), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
                draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
                draw.text((rx+40, ry+30+t_sz+10), v_date, font=f_d, fill=sub_color)
                y_c = ry + t_sz + d_sz + 80
                for lab, val in items:
                    draw.text((rx+40, y_c), lab, font=f_l, fill="#AAAAAA")
                    draw.text((rx+40, y_c+l_sz+5), val, font=f_n, fill=sub_color); y_c += (n_sz + l_sz + 35)
            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "result.jpg", use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")
