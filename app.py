import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 기본 설정 및 초기화] ---
CLIENT_ID = '202275'
CLIENT_SECRET = '969201cab488e4eaf1398b106de1d4e520dc564c'

# ⚠️ [중요] 반드시 Strava 설정의 '인증 콜백 도메인'과 100% 일치해야 함
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# 세션 초기화 및 로그아웃 함수
if 'access_token' not in st.session_state: st.session_state['access_token'] = None
def logout():
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()

# --- [2. 인증 로직] ---
if "code" in st.query_params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": st.query_params["code"], "grant_type": "authorization_code"
        }, timeout=15)
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            st.query_params.clear()
            st.rerun()
    except: pass

# --- [3. 유틸리티 & 폰트 로드] ---
@st.cache_resource
def load_font(font_type, size):
    fonts = {"BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf", "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf", "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf", "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf", "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Bold.ttf"}
    f_url = fonts.get(font_type, fonts["BlackHanSans"])
    f_path = f"font_{font_type}_{int(size)}.ttf"
    if not os.path.exists(f_path): r = requests.get(f_url); open(f_path, "wb").write(r.content)
    return ImageFont.truetype(f_path, int(size))

# --- [4. UI 및 데이터 입력] ---
col1, col2, col3 = st.columns([1.2, 2, 1], gap="medium")

with col2:
    # 연동/로그아웃 버튼을 상단에 배치
    if st.session_state['access_token']:
        st.button("🔓 Strava 로그아웃", on_click=logout, use_container_width=True)
    else:
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force"
        st.link_button("🚀 Strava 연동하기", auth_url, use_container_width=True)

    # 기본값 설정 (수동 입력용)
    v_act, v_date, v_dist, v_time, v_pace, v_hr = "MORNING RUN", "2026.02.14", "5.00", "00:25:00", "5'00\"", "150"
    a = None

    # Strava 연동 시 데이터 덮어쓰기
    if st.session_state['access_token']:
        try:
            headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
            act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=5", headers=headers, timeout=10)
            if act_res.status_code == 200:
                acts = act_res.json()
                act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
                sel_str = st.selectbox("Strava 활동 선택", act_options)
                a = acts[act_options.index(sel_str)]
                d_km = a.get('distance', 0)/1000
                m_sec = a.get('moving_time', 0)
                v_act, v_date = a['name'], a['start_date_local'][:10].replace('-', '.')
                v_dist = f"{d_km:.2f}"
                v_time = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"
                v_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
                v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        except: st.warning("Strava 데이터를 불러오지 못했습니다. 수동 입력을 사용하세요.")

with col1:
    st.header("📸 DATA INPUT")
    bg_files = st.file_uploader("배경 사진", type=['jpg','jpeg','png'])
    log_file = st.file_uploader("원형 로고", type=['jpg','jpeg','png'])
    st.divider()
    # 수동 입력 칸 상시 개방
    v_act = st.text_input("활동명", v_act)
    v_date = st.text_input("날짜", v_date)
    v_dist = st.text_input("거리(km)", v_dist)
    v_time = st.text_input("시간", v_time)
    v_pace = st.text_input("페이스(분/km)", v_pace)
    v_hr = st.text_input("심박(bpm)", v_hr)

with col3:
    st.header("🎨 DESIGN")
    show_box = st.checkbox("로그 박스 표시", value=True)
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color = st.color_picker("활동명 색상", "#FFD700")
    
    # [활동명 90, 날짜 30, 숫자 60 고정]
    t_sz, d_sz, n_sz, l_sz = 70, 20, 45, 22
    
    d_rx, d_ry, d_rw, d_rh = (70, 1250, 480, 600) if box_orient == "Vertical" else (70, 1600, 940, 260)
    rx = st.number_input("X 위치", 0, 1080, d_rx)
    ry = st.number_input("Y 위치", 0, 1920, d_ry)
    rw, rh = st.number_input("너비", 100, 1080, d_rw), st.number_input("높이", 100, 1920, d_rh)
    box_alpha = st.slider("투명도", 0, 255, 110)

# --- [5. 렌더링 엔진] ---
if bg_files:
    try:
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        img = ImageOps.exif_transpose(Image.open(bg_files))
        canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920))
        overlay = Image.new("RGBA", (1080, 1920), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
        
        if show_box:
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
            # [km, bpm 소문자 적용]
            items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
            
            if box_orient == "Vertical":
                draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
                draw.text((rx+40, ry+30+t_sz+10), v_date, font=f_d, fill="#AAAAAA")
                y_c = ry + t_sz + d_sz + 90
                for lab, val in items:
                    draw.text((rx+40, y_c), lab, font=f_l, fill="#AAAAAA")
                    draw.text((rx+40, y_c+l_sz+5), val, font=f_n, fill="#FFFFFF"); y_c += (n_sz + l_sz + 40)
            else:
                tw = draw.textlength(v_act, font=f_t)
                draw.text((rx+(rw//2)-(tw//2), ry+25), v_act, font=f_t, fill=m_color)
                dw = draw.textlength(v_date, font=f_d)
                draw.text((rx+(rw//2)-(dw//2), ry+25+t_sz+5), v_date, font=f_d, fill="#AAAAAA")
                sec_w = (rw - 80) // 4
                for i, (lab, val) in enumerate(items):
                    ix = rx + 40 + (i * sec_w)
                    draw.text((ix, ry+t_sz+d_sz+50), lab, font=f_l, fill="#AAAAAA")
                    draw.text((ix, ry+t_sz+d_sz+50+l_sz+5), val, font=f_n, fill="#FFFFFF")

            if log_file:
                l_sz_i = 100
                l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (l_sz_i, l_sz_i))
                mask = Image.new('L', (l_sz_i, l_sz_i), 0); ImageDraw.Draw(mask).ellipse((0, 0, l_sz_i, l_sz_i), fill=255); l_img.putalpha(mask)
                overlay.paste(l_img, (rx + rw - 130, ry + 30), l_img)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "result.jpg", use_container_width=True)
    except Exception as e: st.error(f"렌더링 에러: {e}")



