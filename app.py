import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 설정 및 상태 유지] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# 세션이 초기화되지 않도록 체크
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

def logout_and_clear():
    st.session_state['access_token'] = None
    st.cache_data.clear()
    st.rerun()

# --- [2. Strava OAuth 로직] ---
query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": query_params["code"], "grant_type": "authorization_code"
    })
    if res.status_code == 200:
        st.session_state['access_token'] = res.json()['access_token']
        st.query_params.clear() # 코드 사용 후 파라미터 제거하여 루프 방지
        st.rerun()

if st.session_state['access_token'] is None:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
                f"&response_type=code&redirect_uri={ACTUAL_URL}"
                f"&scope=read,activity:read_all&approval_prompt=auto")
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [3. 폰트 및 데이터 로드] ---
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

@st.cache_data(ttl=600) # 10분간 데이터 유지 (자주 끊김 방지)
def get_activities(token):
    headers = {'Authorization': f"Bearer {token}"}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)
    return res.json() if res.status_code == 200 else []

acts = get_activities(st.session_state['access_token'])

# --- [4. UI 구성] ---
col1, col2, col3 = st.columns([1.2, 2, 1], gap="medium")
COLOR_OPTIONS = {"Garmin Yellow": "#FFD700", "Pure White": "#FFFFFF", "Neon Orange": "#FF4500", "Electric Blue": "#00BFFF", "Soft Grey": "#AAAAAA"}

with col2:
    m_col, l_col = st.columns([3, 1])
    with m_col: mode = st.radio("모드", ["DAILY", "WEEKLY"], horizontal=True, label_visibility="collapsed")
    with l_col: st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)
    
    if mode == "DAILY" and acts:
        act_options = [f"{a['start_date_local'][:10]} - {a['name']}" for a in acts]
        sel_str = st.selectbox("활동 선택", act_options)
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
        v_dist, v_pace, v_hr = st.text_input("거리(km)", f"{d_km:.2f}"), st.text_input("페이스", p_val), st.text_input("심박", h_val)

with col3:
    st.header("🎨 DESIGN")
    show_box = st.checkbox("로그 박스 표시", value=True)
    box_orient = st.radio("방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", list(load_font.__wrapped__.__defaults__[-1] if hasattr(load_font, '__wrapped__') else ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"]))
    m_color = COLOR_OPTIONS[st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()))]
    sub_color = COLOR_OPTIONS[st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)]
    
    t_sz, d_sz, n_sz, l_sz = 90, 30, 60, 20
    
    if mode == "DAILY":
        if box_orient == "Vertical": d_rx, d_ry, d_rw, d_rh = 70, 1320, 480, 520
        else: d_rx, d_ry, d_rw, d_rh = 70, 1600, 940, 260
        rx, ry = st.number_input("X 위치", 0, 1080, d_rx), st.number_input("Y 위치", 0, 1920, d_ry)
        rw, rh = st.number_input("박스 너비", 100, 1080, d_rw), st.number_input("박스 높이", 100, 1920, d_rh)
        box_alpha, map_size = st.slider("투명도", 0, 255, 110), st.slider("지도 크기", 50, 400, 100)

# --- [5. 이미지 합성 엔진] ---
if bg_files:
    try:
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        if mode == "DAILY":
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920))
            ovl = Image.new("RGBA", (1080, 1920), (0,0,0,0)); draw = ImageDraw.Draw(ovl)
            
            if show_box:
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
                items = [("distance", f"{v_dist} km"), ("time", t_val), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
                
                # 가로 모드: 좌지도 - 중제목 - 우로고
                if box_orient == "Horizontal":
                    # 1. 왼쪽 지도
                    if 'a' in locals() and a.get('map', {}).get('summary_polyline'):
                        pts = polyline.decode(a['map']['summary_polyline'])
                        lats, lons = zip(*pts)
                        m_lyr = Image.new("RGBA", (map_size, map_size), (0,0,0,0)); m_draw = ImageDraw.Draw(m_lyr)
                        def tr(la, lo):
                            tx = 10 + (lo - min(lons)) / (max(lons) - min(lons) + 0.00001) * (map_size - 20)
                            ty = (map_size - 10) - (la - min(lats)) / (max(lats) - min(lats) + 0.00001) * (map_size - 20)
                            return tx, ty
                        m_draw.line([tr(la, lo) for la, lo in pts], fill=m_color, width=4)
                        ovl.paste(m_lyr, (rx + 30, ry + 25), m_lyr)

                    # 2. 중앙 제목 & 날짜
                    tw = draw.textlength(v_act, font=f_t)
                    draw.text((rx + (rw//2) - (tw//2), ry + 25), v_act, font=f_t, fill=m_color)
                    dw = draw.textlength(v_date, font=f_d)
                    draw.text((rx + (rw//2) - (dw//2), ry + 25 + t_sz + 5), v_date, font=f_d, fill="#AAAAAA")
                    
                    # 3. 오른쪽 로고
                    if log_file:
                        l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (80, 80))
                        mask = Image.new('L', (80, 80), 0); ImageDraw.Draw(mask).ellipse((0, 0, 80, 80), fill=255); l_img.putalpha(mask)
                        ovl.paste(l_img, (rx + rw - 110, ry + 30), l_img)

                    # 4. 하단 기록 (1열)
                    sw = (rw - 80) // 4
                    for i, (lb, vl) in enumerate(items):
                        draw.text((rx + 40 + i*sw, ry + t_sz + d_sz + 50), lb, font=f_l, fill="#AAAAAA")
                        draw.text((rx + 40 + i*sw, ry + t_sz + d_sz + 50 + l_sz + 5), vl, font=f_n, fill=sub_color)

                else: # 세로 모드 (기존 유지)
                    draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
                    draw.text((rx+40, ry+30+t_sz+10), v_date, font=f_d, fill=sub_color)
                    y_c = ry + t_sz + d_sz + 90
                    for lb, vl in items:
                        draw.text((rx+40, y_c), lb, font=f_l, fill="#AAAAAA")
                        draw.text((rx+40, y_c+l_sz+5), vl, font=f_n, fill=sub_color); y_c += (n_sz + l_sz + 35)
                    if log_file:
                        l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (100, 100))
                        mask = Image.new('L', (100, 100), 0); ImageDraw.Draw(mask).ellipse((0, 0, 100, 100), fill=255); l_img.putalpha(mask)
                        ovl.paste(l_img, (rx + rw - 120, ry + rh - 120), l_img)
            
            final = Image.alpha_composite(canvas, ovl).convert("RGB")
            with col2:
                st.image(final, use_container_width=True)
                buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
                st.download_button("📸 DOWNLOAD", buf.getvalue(), "result.jpg", use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")
