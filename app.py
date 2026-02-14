import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
from datetime import datetime, timedelta

# --- [1. Strava API 설정] ---
# 상황에 따라 아래 두 세트 중 선택해서 활성화할 수 있도록 구성
API_CONFIGS = {
    "PRIMARY": {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'},
    "SECONDARY": {"ID": '202274', "SECRET": '63f6a7007ebe6b405763fc3104e17bb53b468ad0'}
}

# 현재 활성화할 설정 (필요 시 SECONDARY로 변경)
CURRENT_CFG = API_CONFIGS["PRIMARY"] 
CLIENT_ID = CURRENT_CFG["ID"]
CLIENT_SECRET = CURRENT_CFG["SECRET"]
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# --- [2. 세션 및 인증] ---
if 'access_token' not in st.session_state: st.session_state['access_token'] = None

def logout_and_clear():
    st.cache_data.clear(); st.cache_resource.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": query_params["code"], "grant_type": "authorization_code"
        }, timeout=15)
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            st.query_params.clear(); st.rerun()
    except: pass

# --- [3. 유틸리티] ---
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

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

# --- [4. 데이터 로드] ---
acts = []
if st.session_state['access_token']:
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
    try:
        act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers, timeout=15)
        if act_res.status_code == 200: acts = act_res.json()
    except: pass

# --- [5. UI 레이아웃] ---
col1, col2, col3 = st.columns([1.2, 2, 1], gap="medium")
COLOR_OPTIONS = {"Garmin Yellow": "#FFD700", "Pure White": "#FFFFFF", "Neon Orange": "#FF4500", "Electric Blue": "#00BFFF", "Soft Grey": "#AAAAAA"}

with col2:
    m_col, l_col = st.columns([3, 1])
    with m_col: mode = st.radio("모드", ["DAILY", "WEEKLY"], horizontal=True, label_visibility="collapsed")
    with l_col: 
        if st.session_state['access_token']:
            st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)
        else:
            auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
                        f"&response_type=code&redirect_uri={ACTUAL_URL}"
                        f"&scope=read,activity:read_all&approval_prompt=force")
            st.link_button("🚀 Strava 연동", auth_url, use_container_width=True)

    v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", "2026-02-14", "0.00", "00:00:00", "0'00\"", "0"
    a = None

    if acts:
        act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
        sel_str = st.selectbox("기록 선택 (Strava)", act_options)
        a = acts[act_options.index(sel_str)]
        d_km = a.get('distance', 0)/1000
        m_sec = a.get('moving_time', 0)
        v_act, v_date = a['name'], a['start_date_local'][:10]
        v_dist = f"{d_km:.2f}"
        v_time = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"
        v_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
        v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"

with col1:
    st.header("📸 DATA INPUT")
    bg_files = st.file_uploader("배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("원형 로고", type=['jpg','jpeg','png'])
    st.divider()
    v_act = st.text_input("활동명", v_act)
    v_date = st.text_input("날짜", v_date)
    v_dist = st.text_input("거리(km)", v_dist)
    v_time = st.text_input("시간", v_time)
    v_pace = st.text_input("페이스(분/km)", v_pace)
    v_hr = st.text_input("심박(bpm)", v_hr)

with col3:
    st.header("🎨 DESIGN")
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color = COLOR_OPTIONS[st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()))]
    sub_color = COLOR_OPTIONS[st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)]
    
    # 설정값
    t_sz, d_sz, n_sz, l_sz = 90, 30, 60, 20
    d_rx, d_ry, d_rw, d_rh = (70, 1250, 480, 600) if box_orient == "Vertical" else (70, 1600, 940, 260)
    rx = st.number_input("X 위치", 0, 1080, d_rx)
    ry = st.number_input("Y 위치", 0, 1920, d_ry)
    rw = st.number_input("박스 너비", 100, 1080, d_rw)
    rh = st.number_input("박스 높이", 100, 1920, d_rh)
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    map_size = st.slider("지도 크기", 50, 400, 180)
    map_alpha = st.slider("지도 투명도", 0, 255, 80)

# --- [6. 렌더링 엔진] ---
if bg_files:
    try:
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        img = ImageOps.exif_transpose(Image.open(bg_files[0]))
        canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920))
        overlay = Image.new("RGBA", (1080, 1920), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
        
        # 1. 로그박스
        draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
        items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
        
        # 2. 지도 (흐릿하고 작게 조절 가능)
        if a and a.get('map', {}).get('summary_polyline'):
            pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
            m_layer = Image.new("RGBA", (map_size, map_size), (0,0,0,0)); m_draw = ImageDraw.Draw(m_layer)
            def trans(la, lo):
                tx = 15 + (lo - min(lons)) / (max(lons) - min(lons) + 0.00001) * (map_size - 30)
                ty = (map_size - 15) - (la - min(lats)) / (max(lats) - min(lats) + 0.00001) * (map_size - 30)
                return tx, ty
            m_draw.line([trans(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, map_alpha), width=4)
            
            if box_orient == "Vertical":
                overlay.paste(m_layer, (rx + rw - map_size - 20, ry + 20), m_layer)
            else:
                overlay.paste(m_layer, (rx + 20, ry + (rh - map_size)//2), m_layer)

        # 3. 텍스트 배치
        if box_orient == "Vertical":
            draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
            draw.text((rx+40, ry+130), v_date, font=f_d, fill="#AAAAAA")
            y_c = ry + 210
            for lab, val in items:
                draw.text((rx+40, y_c), lab.lower(), font=f_l, fill="#AAAAAA")
                draw.text((rx+40, y_c+25), val.lower() if "bpm" in val or "km" in val else val, font=f_n, fill=sub_color)
                y_c += 110
        else:
            # 가로모드 간격 최적화 (겹침 방지)
            text_x_off = map_size + 40 if a else 40
            draw.text((rx + text_x_off, ry + 40), v_act, font=f_t, fill=m_color)
            draw.text((rx + text_x_off, ry + 130), v_date, font=f_d, fill="#AAAAAA")
            usable_w = rw - text_x_off - 150
            sec_w = usable_w // 4
            for i, (lab, val) in enumerate(items):
                item_x = rx + text_x_off + (i * sec_w)
                draw.text((item_x, ry + 180), lab.lower(), font=f_l, fill="#AAAAAA")
                draw.text((item_x, ry + 205), val.lower() if "bpm" in val or "km" in val else val, font=f_n, fill=sub_color)

        # 4. 로고 배치 (위치 가변)
        if log_file:
            ls = 100; l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (ls, ls))
            mask = Image.new('L', (ls, ls), 0); ImageDraw.Draw(mask).ellipse((0, 0, ls, ls), fill=255); l_img.putalpha(mask)
            log_pos = (rx + rw - ls - 25, ry + rh - ls - 25) if box_orient == "Vertical" else (rx + rw - ls - 25, ry + 25)
            overlay.paste(l_img, log_pos, l_img)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "result.jpg", use_container_width=True)
                
    except Exception as e:
        st.error(f"Error: {e}")
