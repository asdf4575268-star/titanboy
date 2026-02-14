import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 기본 설정] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# --- [2. 유틸리티 함수] ---
@st.cache_resource
def load_font(font_type, size):
    fonts = {
        "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf"
    }
    f_url = fonts.get(font_type, fonts["Jua"])
    f_path = f"font_{font_type}_{size}.ttf"
    if not os.path.exists(f_path):
        r = requests.get(f_url); f = open(f_path, "wb"); f.write(r.content); f.close()
    return ImageFont.truetype(f_path, int(size))

def get_circle_logo(img_file, size=(130, 130)):
    img = Image.open(img_file).convert("RGBA")
    img = ImageOps.fit(img, size, centering=(0.5, 0.5))
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    img.putalpha(mask)
    return img

# --- [3. 인증 로직] ---
params = st.query_params
if "code" in params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": params["code"], "grant_type": "authorization_code"
        }, timeout=15)
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            st.query_params.clear()
            st.rerun()
    except: pass

if not st.session_state['access_token']:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [4. 데이터 로드 및 3분할 구성] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)

if act_res.status_code == 200:
    acts = act_res.json()
    
    col1, col2, col3 = st.columns([1, 2, 1], gap="medium")

    # --- [중앙: 모드 선택 & 미리보기] ---
    with col2:
        mode = st.radio("작업 모드", ["DAILY", "WEEKLY"], horizontal=True)
        if mode == "DAILY":
            sel_str = st.selectbox("기록 선택", [f"{a['start_date_local'][:10]} - {a['name']}" for a in acts])
            a = acts[[f"{x['start_date_local'][:10]} - {x['name']}" for x in acts].index(sel_str)]
            d_km, m_sec = a.get('distance', 0)/1000, a.get('moving_time', 0)
            p_val = f"{int((m_sec/d_km)//60)}:{int((m_sec/d_km)%60):02d}" if d_km > 0 else "0:00"
            h_val = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
            t_val = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"
        else:
            st.info("선택한 사진들을 기반으로 WEEKLY 콜라주를 만듭니다.")

    # --- [좌측: 📸 DATA] ---
    with col1:
        st.header("📸 DATA")
        bg_files = st.file_uploader("사진 업로드 (여러 장 가능)", type=['jpg','jpeg','png'], accept_multiple_files=True)
        log_file = st.file_uploader("로고 아이콘", type=['jpg','jpeg','png'])
        st.markdown("---")
        if mode == "DAILY":
            v_act = st.text_input("활동명", a['name'])
            v_date = st.text_input("날짜", a['start_date_local'][:10])
            v_dist = st.text_input("거리(km)", f"{d_km:.2f}")
            v_pace = st.text_input("페이스(/km)", p_val)
            v_hr = st.text_input("심박(bpm)", h_val)
        else:
            v_act = st.text_input("제목", "WEEKLY RECAP")
            v_date = st.text_input("부제목", "Last 7 Days")

    # --- [우측: 🎨 DESIGN] ---
    with col3:
        st.header("🎨 DESIGN")
        sel_font = st.selectbox("폰트", ["Jua", "BlackHanSans"])
        m_color = st.color_picker("메인 색상", "#FFD700")
        n_color = st.color_picker("텍스트 색상", "#FFFFFF")
        
        # 가이드 수치 고정 (90, 30, 60, 25)
        t_sz = st.slider("활동명(90)", 10, 200, 90)
        d_sz = st.slider("날짜(30)", 5, 100, 30)
        n_sz = st.slider("숫자(60)", 10, 300, 60)
        l_sz = st.slider("라벨(25)", 10, 80, 25)
        
        st.markdown("---")
        box_mode = st.radio("로그박스 정렬", ["Vertical", "Horizontal"])
        rx = st.slider("X 위치", 0, 1080, 70)
        ry = st.slider("Y 위치", 0, 1920, 1150)
        box_alpha = st.slider("투명도", 0, 255, 60)
        
        if st.button("🔌 초기화"):
            st.session_state.clear()
            st.rerun()

    # --- [5. 이미지 생성 및 렌더링] ---
    if bg_files:
        if mode == "DAILY":
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
        else:
            canvas = Image.new("RGBA", (1080, 1920), (0,0,0,255))
            n = len(bg_files)
            rows = math.ceil(n / 2) if n > 1 else 1
            h_pic = 1920 // rows
            for i, f in enumerate(bg_files):
                w_pic = 1080 // (2 if n > 1 else 1)
                p_img = ImageOps.fit(Image.open(f).convert("RGBA"), (w_pic, h_pic))
                canvas.paste(p_img, ((i % 2) * w_pic if n > 1 else 0, (i // 2) * h_pic))

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)

        items = [("DISTANCE", f"{v_dist} km"), ("TIME", t_val), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")] if mode == "DAILY" else []
        
        # 가변 박스 계산
        if box_mode == "Vertical":
            b_w = 600
            b_h = t_sz + d_sz + (len(items) * (n_sz + l_sz + 40)) + 120
        else:
            b_w = 1000
            b_h = t_sz + d_sz + n_sz + 180

        draw.rectangle([rx, ry, rx+b_w, ry+b_h], fill=(0, 0, 0, box_alpha))
        draw.text((rx+50, ry+40), v_act, font=f_t, fill=m_color)
        draw.text((rx+50, ry+40+t_sz+5), v_date, font=f_d, fill=n_color)

        y_cur = ry + t_sz + d_sz + 85
        if box_mode == "Vertical":
            for lab, val in items:
                draw.text((rx+55, y_cur), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx+55, y_cur + l_sz + 5), val, font=f_n, fill=n_color)
                y_cur += (n_sz + l_sz + 40)
        else:
            x_cur = rx + 55
            for lab, val in items:
                draw.text((x_cur, y_cur), lab, font=f_l, fill="#AAAAAA")
                draw.text((x_cur, y_cur + l_sz + 5), val, font=f_n, fill=n_color)
                x_cur += (b_w // 4)

        if log_file:
            logo = get_circle_logo(log_file)
            canvas.paste(logo, (900, 50), logo)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin.jpg", use_container_width=True)
else:
    st.error("데이터 로드 실패.")
