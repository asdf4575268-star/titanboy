import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, time

# --- [1. 기본 설정] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None
if 'auth_code_used' not in st.session_state:
    st.session_state['auth_code_used'] = None

# --- [2. 인증 로직] ---
params = st.query_params
if "code" in params and st.session_state['access_token'] is None:
    current_code = params["code"]
    if st.session_state['auth_code_used'] != current_code:
        st.session_state['auth_code_used'] = current_code
        try:
            res = requests.post("https://www.strava.com/oauth/token", data={
                "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                "code": current_code, "grant_type": "authorization_code"
            }, timeout=15)
            if res.status_code == 200:
                st.session_state['access_token'] = res.json()['access_token']
                st.query_params.clear()
                st.rerun()
        except:
            st.session_state['auth_code_used'] = None

if not st.session_state['access_token']:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [3. 유틸리티 함수] ---
@st.cache_resource
def load_font(font_type, size):
    fonts = {
        "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf"
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

# --- [4. 데이터 로드 및 3분할 레이아웃] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers, timeout=15)

if act_res.status_code == 200:
    acts = act_res.json()
    
    col1, col2, col3 = st.columns([1, 2, 1], gap="large")

    # 🎯 [중앙: 활동 선택] - 데이터를 먼저 결정해야 왼쪽 입력창에 뿌릴 수 있음
    with col2:
        st.header("🎯 기록 선택 및 미리보기")
        sel_act_str = st.selectbox("불러올 활동을 선택하세요", [f"{a['start_date_local']} - {a['name']}" for a in acts])
        selected_act = acts[[f"{x['start_date_local']} - {x['name']}" for x in acts].index(sel_act_str)]
        
        # 선택된 활동 기반 자동 계산 데이터
        d_km = selected_act.get('distance', 0) / 1000
        m_sec = selected_act.get('moving_time', 0)
        p_val = f"{int((m_sec/d_km)//60)}:{int((m_sec/d_km)%60):02d}" if d_km > 0 else "0:00"
        h_val = str(int(selected_act.get('average_heartrate', 0))) if selected_act.get('average_heartrate') else "0"
        t_val = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"

    # 📸 [좌측: 사진 & 데이터 수정]
    with col1:
        st.header("📸 데이터 수정")
        bg_file = st.file_uploader("배경 사진 (1080x1920 자동)", type=['jpg', 'jpeg', 'png'])
        log_file = st.file_uploader("로고 아이콘", type=['jpg', 'jpeg', 'png'])
        st.markdown("---")
        # 중앙에서 선택한 활동 데이터가 기본값으로 들어감
        v_act = st.text_input("활동명", selected_act['name'])
        v_date = st.text_input("날짜", selected_act['start_date_local'][:10])
        v_dist = st.text_input("거리(km)", f"{d_km:.2f}")
        v_pace = st.text_input("페이스(/km)", p_val)
        v_hr = st.text_input("심박(bpm)", h_val)

    # 🎨 [우측: 디자인 설정]
    with col3:
        st.header("🎨 디자인 조절")
        sel_font = st.selectbox("폰트", ["Jua", "BlackHanSans", "DoHyeon"])
        m_color = st.color_picker("활동명 색상", "#FFD700")
        n_color = st.color_picker("텍스트 색상", "#FFFFFF")
        
        t_sz = st.slider("활동명 (90)", 10, 200, 90)
        d_sz = st.slider("날짜 (30)", 5, 100, 30)
        n_sz = st.slider("숫자 (60)", 10, 300, 60)
        l_sz = st.slider("라벨", 10, 80, 25)
        
        rx = st.slider("X 위치", 0, 1080, 70)
        ry = st.slider("Y 위치", 0, 1920, 1150)
        rw = st.slider("너비", 300, 1000, 500)
        rh = st.slider("높이", 300, 1200, 720)
        box_alpha = st.slider("투명도", 0, 255, 60)
        
        if st.button("🔌 로그아웃", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # 🖼️ [이미지 생성 및 중앙 출력]
    if bg_file:
        orig = ImageOps.exif_transpose(Image.open(bg_file))
        canvas = ImageOps.fit(orig.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0, 0, 0, box_alpha))
        
        # 텍스트 렌더링 (사용자가 수정한 v_act, v_dist 등을 사용)
        draw.text((rx+50, ry+40), v_act, font=f_t, fill=m_color)
        draw.text((rx+rw-50, ry+40+t_sz+10), v_date, font=f_d, fill=n_color, anchor="ra")
        
        # 항목들 (km, bpm 소문자)
        items = [("DISTANCE", f"{v_dist} km"), ("TIME", t_val), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
        y_cursor = ry + t_sz + d_sz + 80
        for lab, val in items:
            draw.text((rx+60, y_cursor), lab, font=f_l, fill="#AAAAAA")
            draw.text((rx+60, y_cursor + l_sz + 5), val, font=f_n, fill=n_color)
            y_cursor += (n_sz + l_sz + 30)

        if log_file:
            logo = get_circle_logo(log_file)
            canvas.paste(logo, (900, 50), logo)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 사진 다운로드", buf.getvalue(), "garmin_story.jpg", use_container_width=True)
    else:
        with col2:
            st.info("👈 왼쪽에서 배경 사진을 올려주세요.")
