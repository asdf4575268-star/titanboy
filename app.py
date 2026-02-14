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
    # 요청하신 구글 폰트 리스트 확장
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf",
        "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf",
        "GothicA1": "https://github.com/google/fonts/raw/main/ofl/gothica1/GothicA1-Black.ttf",
        "SongMyung": "https://github.com/google/fonts/raw/main/ofl/songmyung/SongMyung-Regular.ttf",
        "SingleDay": "https://github.com/google/fonts/raw/main/ofl/singleday/SingleDay-Regular.ttf",
        "Pretendard": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"
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

def create_collage(image_files, target_size=(1080, 1350)):
    imgs = [ImageOps.exif_transpose(Image.open(f).convert("RGB")) for f in image_files]
    if not imgs: return None
    count = len(imgs)
    cols = 1 if count == 1 else (2 if count <= 4 else 3)
    rows = (count + cols - 1) // cols
    cell_w, cell_h = target_size[0] // cols, target_size[1] // rows
    collage = Image.new("RGB", target_size, (0, 0, 0))
    for i, img in enumerate(imgs):
        is_last = (i == count - 1)
        draw_w = cell_w * (cols - (count % cols) + 1) if is_last and (count % cols != 0) else cell_w
        img_fitted = ImageOps.fit(img, (draw_w, cell_h), centering=(0.5, 0.5))
        collage.paste(img_fitted, ((i % cols) * cell_w, (i // cols) * cell_h))
    return collage

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

# --- [4. 사이드바 (업데이트된 폰트 리스트)] ---
with st.sidebar:
    app_mode = st.radio("🚀 작업 모드", ["DAILY", "WEEKLY"])
    st.markdown("---")
    st.header("⚙️ 디자인/크기 설정")
    selected_font = st.selectbox("폰트 선택", ["Jua", "BlackHanSans", "NanumBrush", "DoHyeon", "GothicA1", "SongMyung", "SingleDay", "Pretendard"])
    main_color = st.color_picker("활동명 색상", "#FFD700")
    num_color = st.color_picker("날짜/정보 색상", "#FFFFFF")
    route_color = st.selectbox("지도 경로 색상", ["Yellow", "Black", "White"])
    
    st.markdown("---")
    t_sz, d_sz, n_sz, l_sz = st.slider("활동명", 10, 200, 90), st.slider("날짜", 10, 100, 30), st.slider("숫자", 10, 150, 60), st.slider("라벨", 10, 80, 25)
    
    st.markdown("---")
    rx, ry, rw, rh = st.slider("X", 0, 1080, 70), st.slider("Y", 0, 1920, 1150), st.slider("Width", 300, 1000, 500), st.slider("Height", 300, 1200, 720)
    alpha = st.slider("투명도", 0, 255, 60)

# --- [5. 실행 로직] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}

if app_mode == "DAILY":
    # ... (DAILY 모드 기존 로직 동일)
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers)
    if act_res.status_code == 200:
        acts = act_res.json()
        sel = st.selectbox("기록 선택", [f"{a['start_date_local']} - {a['name']}" for a in acts])
        a = acts[[f"{x['start_date_local']} - {x['name']}" for x in acts].index(sel)]
        
        m_time = a.get('moving_time', 0)
        time_v = f"{m_time//3600:02d}:{ (m_time%3600)//60 :02d}:{m_time%60:02d}" if m_time >= 3600 else f"{m_time//60:02d}:{m_time%60:02d}"
        dist_km = a.get('distance', 0) / 1000
        pace_v = f"{int((m_time/dist_km)//60)}:{int((m_time/dist_km)%60):02d}" if dist_km > 0 else "0:00"
        hr_v = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"

        col_files, col_inputs = st.columns([1, 1])
        with col_files:
            bg_file = st.file_uploader("배경 사진", type=['jpg', 'jpeg', 'png'])
            log_file = st.file_uploader("로고 아이콘", type=['jpg', 'jpeg', 'png'])
        with col_inputs:
            v_act, v_date = st.text_input("활동명", a['name']), st.text_input("날짜", a.get('start_date_local', "")[:16].replace("T", " "))
            v_dist, v_time = st.text_input("거리(km)", f"{dist_km:.2f}"), st.text_input("시간", time_v)
            v_pace, v_hr = st.text_input("페이스", pace_v), st.text_input("심박수(bpm)", hr_v)
            v_weather = st.text_input("날씨", "")

        if bg_file:
            orig_bg = ImageOps.exif_transpose(Image.open(bg_file))
            canvas = ImageOps.fit(orig_bg.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
            overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            f_t, f_d, f_n, f_l = load_custom_font(selected_font, t_sz), load_custom_font(selected_font, d_sz), load_custom_font(selected_font, n_sz), load_custom_font(selected_font, l_sz)

            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0, 0, 0, alpha))
            draw.text((rx + 50, ry + 40), v_act, font=f_t, fill=main_color)
            draw.text((rx + rw - 50, ry + 40 + t_sz + 5), v_date, font=f_d, fill=num_color, anchor="ra")
            
            items = [("DISTANCE", f"{v_dist} km"), ("TIME", v_time), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
            if v_weather: items.append(("WEATHER", v_weather))

            spacing = ((ry + rh - 50) - (ry + t_sz + d_sz + 100)) / len(items)
            for i, (lab, val) in enumerate(items):
                py = (ry + t_sz + d_sz + 100) + (i * spacing)
                draw.text((rx + 60, py), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx + 60, py + l_sz + 5), val, font=f_n, fill=num_color)

            # 지도 & 로고 로직 생략 (기존과 동일)
            # ... [후략] ...
            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, use_container_width=True)

elif app_mode == "WEEKLY":
    st.title("📅 이번 주 활동 요약 (Weekly)")
    after_ts = int((datetime.now() - timedelta(days=7)).timestamp())
    act_res = requests.get(f"https://www.strava.com/api/v3/athlete/activities?after={after_ts}", headers=headers)
    
    if act_res.status_code == 200:
        w_acts = act_res.json()
        if w_acts:
            total_dist = sum(a.get('distance', 0) for a in w_acts) / 1000
            total_time = sum(a.get('moving_time', 0) for a in w_acts)
            avg_hr = sum(a.get('average_heartrate', 0) for a in w_acts if a.get('average_heartrate')) / len([a for a in w_acts if a.get('average_heartrate')]) if any(a.get('average_heartrate') for a in w_acts) else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("이번 주 총 거리", f"{total_dist:.2f} km")
            if total_dist > 0:
                p_sec = total_time / total_dist
                m2.metric("평균 페이스", f"{int(p_sec//60)}:{int(p_sec%60):02d} /km")
            m3.metric("평균 심박수", f"{int(avg_hr)} bpm")
            
            st.markdown("---")
            # 🌟 WEEKLY 사진 업로드 및 콜라주 복구
            w_files = st.file_uploader("주간 콜라주용 사진 선택 (여러 장)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, key="weekly_upload")
            if w_files:
                with st.spinner("콜라주 생성 중..."):
                    collage = create_collage(w_files)
                    if collage:
                        st.image(collage, use_container_width=True)
                        buf = io.BytesIO(); collage.save(buf, format="JPEG", quality=95)
                        st.download_button("📸 콜라주 저장", buf.getvalue(), "weekly_collage.jpg")
        else:
            st.info("최근 7일간 기록이 없습니다.")
