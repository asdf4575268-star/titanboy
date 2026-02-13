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

# --- [4. 사이드바] ---
with st.sidebar:
    app_mode = st.radio("🚀 작업 모드", ["DAILY", "WEEKLY"])
    st.markdown("---")
    st.header("⚙️ 디자인 설정")
    selected_font = st.selectbox("폰트 선택", ["BlackHanSans", "NanumBrush", "Jua", "Pretendard(Bold)"])
    main_color = st.color_picker("활동명 색상", "#FFD700")
    num_color = st.color_picker("날짜/정보 색상", "#FFFFFF")
    route_color = st.selectbox("지도 경로 색상", ["Yellow", "Black", "White"])
    
    st.markdown("---")
    t_sz = st.slider("활동명 크기", 10, 200, 90)
    d_sz = st.slider("날짜 크기", 10, 100, 30)
    n_sz = st.slider("숫자 크기", 10, 150, 60)
    l_sz = st.slider("라벨 크기", 10, 80, 25)
    rx = st.slider("박스 좌측 위치", 0, 1080, 70)
    ry = st.slider("박스 상단 위치", 0, 1920, 1250)
    alpha = st.slider("박스 투명도", 0, 255, 50)

# --- [5. 실행 로직] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}

if app_mode == "DAILY":
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers)
    if act_res.status_code == 200:
        acts = act_res.json()
        sel = st.selectbox("기록 선택", [f"{a['start_date_local']} - {a['name']}" for a in acts])
        a = acts[[f"{x['start_date_local']} - {x['name']}" for x in acts].index(sel)]
        
        # 데이터 파싱
        date_def = a.get('start_date_local', "2026-02-14T00:00").replace("T", " ")[:16]
        dist_km = a.get('distance', 0) / 1000
        pace_v = f"{int((a.get('moving_time',0)/dist_km)//60)}:{int((a.get('moving_time',0)/dist_km)%60):02d}" if dist_km > 0 else "0:00"
        hr_v = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"

        col_files, col_inputs = st.columns([1, 1])
        with col_files:
            bg_file = st.file_uploader("1. 배경 사진 선택", type=['jpg', 'jpeg', 'png'])
            log_file = st.file_uploader("2. 로고 아이콘 선택", type=['jpg', 'jpeg', 'png'])
        with col_inputs:
            v_act = st.text_input("활동명 수정", a['name'])
            v_date = st.text_input("날짜 수정", date_def)
            v_dist = st.text_input("거리(km) 수정", f"{dist_km:.2f}")
            v_pace = st.text_input("페이스 수정", pace_v)
            v_hr = st.text_input("심박수 수정", hr_v)

        if bg_file:
            canvas = ImageOps.fit(Image.open(bg_file).convert("RGBA"), (1080, 1920))
            overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            f_t, f_d, f_n, f_l = load_custom_font(selected_font, t_sz), load_custom_font(selected_font, d_sz), load_custom_font(selected_font, n_sz), load_custom_font(selected_font, l_sz)

            draw.rectangle([rx, ry, rx + 450, ry + 560], fill=(0, 0, 0, alpha))
            draw.text((rx + 50, ry + 40), v_date, font=f_d, fill=num_color)
            draw.text((rx + 50, ry + 40 + d_sz + 10), v_act, font=f_t, fill=main_color)
            
            line_y = ry + d_sz + t_sz + 80
            items = [("DISTANCE", f"{v_dist} km"), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
            for i, (lab, val) in enumerate(items):
                py = line_y + (i * 125)
                draw.text((rx + 60, py), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx + 60, py + l_sz + 5), val, font=f_n, fill=num_color)

            # 지도 및 로고
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
            
            # 평균 페이스 계산
            if total_dist > 0:
                avg_pace_sec = total_time / total_dist
                pace_m, pace_s = int(avg_pace_sec // 60), int(avg_pace_sec % 60)
                avg_pace_str = f"{pace_m}:{pace_s:02d}"
            else:
                avg_pace_str = "0:00"

            # 🌟 수치 표시 레이아웃
            m1, m2, m3 = st.columns(3)
            m1.metric("이번 주 총 거리", f"{total_dist:.2f} km")
            m2.metric("평균 페이스", f"{avg_pace_str} /km")
            m3.metric("평균 심박수", f"{int(avg_hr)} bpm")
            
            st.markdown("---")
            files = st.file_uploader("콜라주용 사진 선택 (여러 장)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
            if files:
                collage = create_collage(files)
                if collage:
                    st.image(collage, use_container_width=True)
                    buf = io.BytesIO(); collage.save(buf, format="JPEG", quality=95)
                    st.download_button("📸 콜라주 저장", buf.getvalue(), "weekly_collage.jpg")
        else:
            st.info("최근 7일간 기록된 활동이 없습니다.")
