import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, time
from datetime import datetime, timedelta

# --- [1. 기본 설정] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# --- [2. 유틸리티 함수] ---
@st.cache_resource
def load_custom_font(font_type, size):
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf",
        "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "Pretendard(Bold)": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"
    }
    font_url = fonts.get(font_type, fonts["Jua"])
    font_path = f"font_{font_type}.ttf"
    if not os.path.exists(font_path):
        try:
            r = requests.get(font_url, timeout=10)
            with open(font_path, "wb") as f: f.write(r.content)
            time.sleep(0.5)
        except: return ImageFont.load_default()
    try: return ImageFont.truetype(font_path, int(size))
    except: return ImageFont.load_default()

def get_circle_logo(img_file, size=(130, 130)):
    img = Image.open(img_file).convert("RGBA")
    img = ImageOps.fit(img, size, centering=(0.5, 0.5))
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    img.putalpha(mask)
    return img

# --- [3. 스트라바 연동] ---
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

if "code" in st.query_params and not st.session_state['access_token']:
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": st.query_params["code"], "grant_type": "authorization_code"
    })
    if res.status_code == 200:
        st.session_state['access_token'] = res.json()['access_token']
        st.rerun()

if not st.session_state['access_token']:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [4. 사이드바] ---
with st.sidebar:
    app_mode = st.radio("🚀 작업 모드", ["DAILY", "WEEKLY"])
    st.markdown("---")
    st.header("⚙️ 디자인/크기 설정")
    selected_font = st.selectbox("폰트 선택", ["BlackHanSans", "NanumBrush", "Jua", "Pretendard(Bold)"])
    main_color = st.color_picker("활동명 색상", "#FFD700")
    num_color = st.color_picker("날짜/정보 색상", "#FFFFFF")
    route_color = st.selectbox("지도 경로 색상", ["Yellow", "Black", "White"])
    
    st.markdown("---")
    t_sz = st.slider("활동명 크기", 10, 200, 90)
    d_sz = st.slider("날짜 크기", 10, 100, 30)
    n_sz = st.slider("숫자 크기", 10, 150, 60)
    l_sz = st.slider("라벨 크기", 10, 80, 25)
    
    st.markdown("---")
    st.subheader("로그 박스 커스텀")
    rx = st.slider("좌측 위치(X)", 0, 1080, 70)
    ry = st.slider("상단 위치(Y)", 0, 1920, 1150)
    rw = st.slider("박스 너비(Width)", 300, 1000, 500)
    rh = st.slider("박스 높이(Height)", 300, 1200, 720)
    alpha = st.slider("박스 투명도", 0, 255, 60)

# --- [5. DAILY 실행] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}

if app_mode == "DAILY":
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers)
    if act_res.status_code == 200:
        acts = act_res.json()
        sel = st.selectbox("기록 선택", [f"{a['start_date_local']} - {a['name']}" for a in acts])
        a = acts[[f"{x['start_date_local']} - {x['name']}" for x in acts].index(sel)]
        
        # 데이터 파싱
        m_time = a.get('moving_time', 0)
        time_v = f"{m_time//3600:02d}:{ (m_time%3600)//60 :02d}:{m_time%60:02d}" if m_time >= 3600 else f"{m_time//60:02d}:{m_time%60:02d}"
        dist_km = a.get('distance', 0) / 1000
        pace_v = f"{int((m_time/dist_km)//60)}:{int((m_time/dist_km)%60):02d}" if dist_km > 0 else "0:00"
        hr_v = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"

        col_files, col_inputs = st.columns([1, 1])
        with col_files:
            bg_file = st.file_uploader("1. 배경 사진 선택", type=['jpg', 'jpeg', 'png'])
            log_file = st.file_uploader("2. 로고 아이콘 선택", type=['jpg', 'jpeg', 'png'])
        with col_inputs:
            v_act = st.text_input("활동명", a['name'])
            v_date = st.text_input("날짜", a.get('start_date_local', "")[:16].replace("T", " "))
            v_dist = st.text_input("거리(km)", f"{dist_km:.2f}")
            v_time = st.text_input("시간", time_v)
            v_pace = st.text_input("페이스", pace_v)
            v_hr = st.text_input("심박수(bpm)", hr_v)
            v_weather = st.text_input("날씨/기온(직접 입력)", "")

        if bg_file:
            orig_bg = ImageOps.exif_transpose(Image.open(bg_file))
            canvas = ImageOps.fit(orig_bg.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
            overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            f_t, f_d, f_n, f_l = load_custom_font(selected_font, t_sz), load_custom_font(selected_font, d_sz), load_custom_font(selected_font, n_sz), load_custom_font(selected_font, l_sz)

            # 1. 로그박스 그리기
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0, 0, 0, alpha))
            
            # 2. 상단 헤더 (활동명 & 날짜)
            draw.text((rx + 50, ry + 40), v_act, font=f_t, fill=main_color)
            draw.text((rx + rw - 50, ry + 40 + t_sz + 5), v_date, font=f_d, fill=num_color, anchor="ra")
            
            # 3. 🌟 데이터 항목 자동 간격 계산
            items = [("DISTANCE", f"{v_dist} km"), ("TIME", v_time), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
            if v_weather: items.append(("WEATHER", v_weather))

            # 텍스트가 시작될 Y축 시작점
            line_y_start = ry + t_sz + d_sz + 100
            # 박스 하단 여백(50)을 제외한 가용 높이
            available_h = (ry + rh - 50) - line_y_start
            # 항목 간 간격 계산 (가용 높이를 항목 수로 나눔)
            spacing = available_h / len(items)

            for i, (lab, val) in enumerate(items):
                py = line_y_start + (i * spacing)
                draw.text((rx + 60, py), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx + 60, py + l_sz + 5), val, font=f_n, fill=num_color)

            # 지도 & 로고
            poly = a.get('map', {}).get('summary_polyline', "")
            if poly:
                try:
                    pts = polyline.decode(poly)
                    lats, lons = [p[0] for p in pts], [p[1] for p in pts]
                    mi_la, ma_la, mi_lo, ma_lo = min(lats), max(lats), min(lons), max(lons)
                    r_img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
                    dr_r = ImageDraw.Draw(r_img)
                    def sc(p):
                        x = (p[1] - mi_lo) / (ma_lo - mi_lo + 1e-9) * 320 + 40
                        y = 320 - ((p[0] - mi_la) / (ma_la - mi_la + 1e-9) * 320) + 40
                        return (x, y)
                    r_f = {"Yellow": "#FFD700", "Black": "#000000", "White": "#FFFFFF"}.get(route_color, "#FFD700")
                    dr_r.line([sc(p) for p in pts], fill=r_f, width=12)
                    canvas.paste(r_img, (rx - 40, ry - 420), r_img)
                except: pass

            if log_file:
                logo = get_circle_logo(log_file)
                canvas.paste(logo, (900, 60), logo)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_final.jpg")
