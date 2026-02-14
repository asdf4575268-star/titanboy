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

# --- [2. 인증 로직 (타임아웃 및 예외처리 강화)] ---
params = st.query_params
if "code" in params and st.session_state['access_token'] is None:
    current_code = params["code"]
    if st.session_state['auth_code_used'] != current_code:
        st.session_state['auth_code_used'] = current_code
        try:
            # timeout을 15초로 늘려 안정성 확보
            res = requests.post("https://www.strava.com/oauth/token", data={
                "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                "code": current_code, "grant_type": "authorization_code"
            }, timeout=15)
            
            if res.status_code == 200:
                st.session_state['access_token'] = res.json()['access_token']
                st.query_params.clear()
                st.rerun()
            else:
                st.error(f"인증 실패 메시지: {res.text}")
                st.session_state['auth_code_used'] = None
        except requests.exceptions.RequestException as e:
            st.error(f"연결 오류 상세: {e}")
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

# --- [4. 상단 영역: 활동 선택 및 결과물 미리보기] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
try:
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers, timeout=15)
    if act_res.status_code == 200:
        acts = act_res.json()
        
        # UI: 상단 중앙 집중
        _, center_col, _ = st.columns([0.5, 3, 0.5])
        with center_col:
            st.subheader("🎯 활동 선택 및 실시간 미리보기")
            sel_act = st.selectbox("불러올 활동을 선택하세요", [f"{a['start_date_local']} - {a['name']}" for a in acts])
            a = acts[[f"{x['start_date_local']} - {x['name']}" for x in acts].index(sel_act)]
            
            # 데이터 파싱
            dist_km = a.get('distance', 0) / 1000
            m_sec = a.get('moving_time', 0)
            time_str = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"
            pace_str = f"{int((m_sec/dist_km)//60)}:{int((m_sec/dist_km)%60):02d}" if dist_km > 0 else "0:00"
            hr_str = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"

        st.markdown("---")

        # --- [5. 하단 영역: 설정 섹션] ---
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            st.markdown("### 📸 사진 & 텍스트")
            bg_file = st.file_uploader("배경 사진 (세로 자동 크롭)", type=['jpg', 'jpeg', 'png'])
            log_file = st.file_uploader("로고 아이콘", type=['jpg', 'jpeg', 'png'])
            v_act = st.text_input("활동명", a['name'])
            v_date = st.text_input("날짜", a['start_date_local'][:10])
            v_dist = st.text_input("거리(km)", f"{dist_km:.2f}")
            v_pace = st.text_input("페이스(/km)", pace_str)
            v_hr = st.text_input("심박(bpm)", hr_str)

        with c2:
            st.markdown("### 🎨 디자인 설정")
            sel_font = st.selectbox("폰트", ["Jua", "BlackHanSans", "DoHyeon"])
            m_color = st.color_picker("활동명 색상", "#FFD700")
            n_color = st.color_picker("데이터 색상", "#FFFFFF")
            t_sz = st.slider("활동명 크기 (90)", 10, 200, 90)
            d_sz = st.slider("날짜 크기 (30)", 5, 100, 30)
            n_sz = st.slider("숫자 크기 (60)", 10, 300, 60)
            l_sz = st.slider("라벨 크기", 10, 80, 25)

        with c3:
            st.markdown("### 📍 레이아웃 조절")
            rx = st.slider("가로 위치 (X)", 0, 1080, 70)
            ry = st.slider("세로 위치 (Y)", 0, 1920, 1150)
            rw = st.slider("박스 너비", 300, 1000, 500)
            rh = st.slider("박스 높이", 300, 1200, 720)
            box_alpha = st.slider("박스 투명도", 0, 255, 60)
            if st.button("🔌 연동 해제 및 초기화"):
                st.session_state.clear()
                st.rerun()

        # --- [6. 렌더링 및 미리보기 출력] ---
        if bg_file:
            orig = ImageOps.exif_transpose(Image.open(bg_file))
            canvas = ImageOps.fit(orig.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
            overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)

            draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0, 0, 0, box_alpha))
            draw.text((rx+50, ry+40), v_act, font=f_t, fill=m_color)
            draw.text((rx+rw-50, ry+40+t_sz+10), v_date, font=f_d, fill=n_color, anchor="ra")
            
            items = [("DISTANCE", f"{v_dist} km"), ("TIME", time_str), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
            y_cursor = ry + t_sz + d_sz + 80
            for lab, val in items:
                draw.text((rx+60, y_cursor), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx+60, y_cursor + l_sz + 5), val, font=f_n, fill=n_color)
                y_cursor += (n_sz + l_sz + 30)

            if log_file:
                logo = get_circle_logo(log_file)
                canvas.paste(logo, (900, 50), logo)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            with center_col:
                st.image(final, use_container_width=True)
                buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
                st.download_button("📸 최종 이미지 다운로드", buf.getvalue(), "garmin_run.jpg", use_container_width=True)
        else:
            with center_col:
                st.info("👇 하단 '사진 & 텍스트' 섹션에서 배경 사진을 올려주세요.")

    else:
        st.error(f"데이터 로드 실패: {act_res.status_code}")
except Exception as e:
    st.error(f"예상치 못한 오류: {e}")
