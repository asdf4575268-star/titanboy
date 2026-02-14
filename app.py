import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline

# --- [1. 기본 설정] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# 세션 초기화
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# --- [2. No-op 에러 방지용 리셋 로직] ---
# 콜백 함수 대신 버튼의 리턴값을 활용해 리셋을 처리합니다.
reset_app = st.sidebar.button("🔄 앱 초기화 및 로그아웃")
if reset_app:
    st.session_state.clear()
    st.cache_data.clear()
    st.query_params.clear()
    st.rerun() # 여기서 호출하는 rerun은 정상 작동합니다.

# --- [3. Strava OAuth 인증] ---
q_params = st.query_params
if "code" in q_params and st.session_state['access_token'] is None:
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": q_params["code"], "grant_type": "authorization_code"
    })
    if res.status_code == 200:
        st.session_state['access_token'] = res.json().get('access_token')
        st.query_params.clear()
        st.rerun()

# 로그인 화면
if not st.session_state['access_token']:
    st.title("🏃 Garmin Photo Dashboard")
    st.warning("먼저 Strava 계정과 연동해주세요.")
    auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
                f"&response_type=code&redirect_uri={ACTUAL_URL}"
                f"&scope=read,activity:read_all&approval_prompt=force")
    st.link_button("🚀 Strava 연동하기", auth_url, type="primary")
    st.stop()

# --- [4. 데이터 로드 및 디자인 설정] ---
FONT_LIST = ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"]

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
        r = requests.get(f_url); open(f_path, "wb").write(r.content)
    return ImageFont.truetype(f_path, int(size))

@st.cache_data(ttl=300)
def get_activities(token):
    headers = {'Authorization': f"Bearer {token}"}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)
    return res.json() if res.status_code == 200 else []

acts = get_activities(st.session_state['access_token'])

# --- [5. UI 레이아웃] ---
col1, col2, col3 = st.columns([1.2, 2, 1], gap="medium")

with col2:
    if acts:
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
    if acts:
        v_act = st.text_input("활동명", a['name'])
        v_date = st.text_input("날짜", a['start_date_local'][:10])
        # km, bpm 소문자 준수
        v_dist = st.text_input("거리(km)", f"{d_km:.2f}")
        v_pace = st.text_input("페이스", p_val)
        v_hr = st.text_input("심박(bpm)", h_val)

with col3:
    st.header("🎨 DESIGN")
    box_orient = st.radio("방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", FONT_LIST)
    
    # 요청하신 글자 크기 강제 적용
    t_sz, d_sz, n_sz, l_sz = 90, 30, 60, 20
    
    # 박스 좌표 및 설정 (가로모드 최적화)
    d_rx, d_ry, d_rw, d_rh = (70, 1600, 940, 260) if box_orient == "Horizontal" else (70, 1320, 480, 520)
    rx = st.number_input("X 위치", 0, 1080, d_rx)
    ry = st.number_input("Y 위치", 0, 1920, d_ry)
    rw = st.number_input("박스 너비", 100, 1080, d_rw)
    rh = st.number_input("박스 높이", 100, 1920, d_rh)
    box_alpha = st.slider("투명도", 0, 255, 110)
    map_size = st.slider("지도 크기", 50, 400, 100)

# --- [6. 이미지 렌더링] ---
if bg_files:
    try:
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        img = ImageOps.exif_transpose(Image.open(bg_files[0]))
        canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920))
        ovl = Image.new("RGBA", (1080, 1920), (0,0,0,0)); draw = ImageDraw.Draw(ovl)
        
        draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
        items = [("distance", f"{v_dist} km"), ("time", t_val), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
        
        if box_orient == "Horizontal":
            # 가로모드: 지도(좌) - 제목(중) - 로고(우)
            if 'a' in locals() and a.get('map', {}).get('summary_polyline'):
                pts = polyline.decode(a['map']['summary_polyline'])
                lats, lons = zip(*pts); m_lyr = Image.new("RGBA", (map_size, map_size), (0,0,0,0)); m_draw = ImageDraw.Draw(m_lyr)
                def tr(la, lo):
                    tx = 10 + (lo - min(lons)) / (max(lons) - min(lons) + 0.00001) * (map_size - 20)
                    ty = (map_size - 10) - (la - min(lats)) / (max(lats) - min(lats) + 0.00001) * (map_size - 20)
                    return tx, ty
                m_draw.line([tr(la, lo) for la, lo in pts], fill="#FFD700", width=4)
                ovl.paste(m_lyr, (rx + 30, ry + 25), m_lyr)
            
            tw = draw.textlength(v_act, font=f_t); draw.text((rx + (rw//2) - (tw//2), ry + 25), v_act, font=f_t, fill="#FFD700")
            dw = draw.textlength(v_date, font=f_d); draw.text((rx + (rw//2) - (dw//2), ry + 25 + t_sz + 5), v_date, font=f_d, fill="#FFFFFF")
            
            sw = (rw - 80) // 4
            for i, (lb, vl) in enumerate(items):
                draw.text((rx + 40 + i*sw, ry + t_sz + d_sz + 50), lb, font=f_l, fill="#AAAAAA")
                draw.text((rx + 40 + i*sw, ry + t_sz + d_sz + 50 + l_sz + 5), vl, font=f_n, fill="#FFFFFF")
        
        final = Image.alpha_composite(canvas, ovl).convert("RGB")
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "result.jpg", use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")
