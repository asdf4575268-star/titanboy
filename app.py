import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 기본 설정 및 초기화] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

def logout_and_clear():
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()

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

# --- [3. 유틸리티 함수] ---
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
    m_col, l_col = st.columns([3, 1])
    with m_col: mode = st.radio("모드", ["DAILY", "WEEKLY"], horizontal=True, label_visibility="collapsed")
    with l_col: st.button("🔓 초기화", on_click=logout_and_clear, use_container_width=True)
    
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

with col3:
    st.header("🎨 DESIGN")
    show_box = st.checkbox("로그 박스 표시", value=True)
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color = COLOR_OPTIONS[st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()))]
    sub_color = COLOR_OPTIONS[st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)]
    
    t_sz, d_sz, n_sz, l_sz = 70, 20, 40, 20
    
    if mode == "DAILY":
        if box_orient == "Vertical": d_rx, d_ry, d_rw, d_rh = 70, 1250, 480, 600
        else: d_rx, d_ry, d_rw, d_rh = 70, 1600, 940, 260
        rx, ry = st.number_input("X 위치", 0, 1080, d_rx), st.number_input("Y 위치", 0, 1920, d_ry)
        rw, rh = st.number_input("박스 너비", 100, 1080, d_rw), st.number_input("박스 높이", 100, 1920, d_rh)
        box_alpha, map_size = st.slider("박스 투명도", 0, 255, 110), st.slider("지도 크기", 50, 400, 110)

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
                items = [("distance", f"{v_dist} km"), ("time", t_val), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
                
                # --- [세로 모드 레이아웃] ---
                if box_orient == "Vertical":
                    draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
                    draw.text((rx+40, ry+30+t_sz+10), v_date, font=f_d, fill=sub_color)
                    y_c = ry + t_sz + d_sz + 90
                    for lab, val in items:
                        draw.text((rx+40, y_c), lab, font=f_l, fill="#AAAAAA")
                        draw.text((rx+40, y_c+l_sz+5), val, font=f_n, fill=sub_color); y_c += (n_sz + l_sz + 35)
                    # 지도는 우측 상단 고정
                    if acts and 'a' in locals():
                        p_line = a.get('map', {}).get('summary_polyline')
                        if p_line:
                            pts = polyline.decode(p_line); lats, lons = zip(*pts)
                            m_layer = Image.new("RGBA", (map_size, map_size), (0,0,0,0)); m_draw = ImageDraw.Draw(m_layer)
                            def trans(la, lo):
                                tx = 10 + (lo - min(lons)) / (max(lons) - min(lons) + 0.00001) * (map_size - 20)
                                ty = (map_size - 10) - (la - min(lats)) / (max(lats) - min(lats) + 0.00001) * (map_size - 20)
                                return tx, ty
                            m_draw.line([trans(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, 255), width=4)
                            overlay.paste(m_layer, (rx + rw - map_size - 20, ry + 20), m_layer)
                    # 로고는 우측 하단 고정
                    if log_file:
                        l_sz_v = 100
                        l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (l_sz_v, l_sz_v))
                        mask = Image.new('L', (l_sz_v, l_sz_v), 0); ImageDraw.Draw(mask).ellipse((0, 0, l_sz_v, l_sz_v), fill=255); l_img.putalpha(mask)
                        overlay.paste(l_img, (rx + rw - l_sz_v - 20, ry + rh - l_sz_v - 20), l_img)

                # --- [가로 모드 레이아웃] ---
                else: 
                    # 제목 쓰기
                    title_w = draw.textlength(v_act, font=f_t)
                    draw.text((rx+40, ry+25), v_act, font=f_t, fill=m_color)
                    
                    # 제목 바로 옆에 지도 배치
                    if acts and 'a' in locals():
                        p_line = a.get('map', {}).get('summary_polyline')
                        if p_line:
                            pts = polyline.decode(p_line); lats, lons = zip(*pts)
                            m_layer = Image.new("RGBA", (map_size, map_size), (0,0,0,0)); m_draw = ImageDraw.Draw(m_layer)
                            def trans(la, lo):
                                tx = 10 + (lo - min(lons)) / (max(lons) - min(lons) + 0.00001) * (map_size - 20)
                                ty = (map_size - 10) - (la - min(lats)) / (max(lats) - min(lats) + 0.00001) * (map_size - 20)
                                return tx, ty
                            m_draw.line([trans(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, 255), width=4)
                            # 제목 끝나는 좌표 + 여백 30px 자리에 지도 배치
                            overlay.paste(m_layer, (int(rx + 40 + title_w + 30), int(ry + 20)), m_layer)
                    
                    # 날짜 (제목 아래)
                    draw.text((rx+40, ry+25+t_sz+5), v_date, font=f_d, fill="#AAAAAA")
                    
                    # 로고 (박스 오른쪽 상단)
                    if log_file:
                        l_sz_h = 80
                        l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (l_sz_h, l_sz_h))
                        mask = Image.new('L', (l_sz_h, l_sz_h), 0); ImageDraw.Draw(mask).ellipse((0, 0, l_sz_h, l_sz_h), fill=255); l_img.putalpha(mask)
                        overlay.paste(l_img, (rx + rw - l_sz_h - 20, ry + 20), l_img)

                    # 하단 데이터 열 배치 (4등분)
                    data_y, sec_w = ry + t_sz + d_sz + 50, (rw - 80) // 4
                    for i, (lab, val) in enumerate(items):
                        item_x = rx + 40 + (i * sec_w)
                        draw.text((item_x, data_y), lab, font=f_l, fill="#AAAAAA")
                        draw.text((item_x, data_y + l_sz + 5), val, font=f_n, fill=sub_color)
            
            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            with col2:
                st.image(final, use_container_width=True)
                buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
                st.download_button("📸 DOWNLOAD", buf.getvalue(), "result.jpg", use_container_width=True)
                
    except Exception as e:
        st.error(f"Error: {e}")
