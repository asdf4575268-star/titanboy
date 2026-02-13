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
    """OSError 방지를 위한 강화된 폰트 로더"""
    fonts = {
        "Pretendard(Bold)": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf", # 대체 경로
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf",
        "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf"
    }
    font_url = fonts.get(font_type, fonts["Jua"])
    font_path = f"font_{font_type}.ttf"
    
    # 파일이 없으면 다운로드 시도
    if not os.path.exists(font_path) or os.path.getsize(font_path) < 100:
        try:
            r = requests.get(font_url, timeout=10)
            with open(font_path, "wb") as f:
                f.write(r.content)
            time.sleep(0.5) # 파일 시스템 기록 대기
        except:
            return ImageFont.load_default() # 실패 시 기본 폰트 사용

    try:
        return ImageFont.truetype(font_path, int(size))
    except OSError:
        return ImageFont.load_default()

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

# --- [4. 공통 사이드바] ---
with st.sidebar:
    app_mode = st.radio("🚀 작업 모드", ["DAILY", "WEEKLY"])
    st.markdown("---")
    st.header("🎨 디자인/폰트")
    selected_font = st.selectbox("폰트 선택", ["BlackHanSans", "NanumBrush", "Jua", "Pretendard(Bold)"])
    main_color = st.color_picker("활동명 색상", "#FFD700")
    num_color = st.color_picker("숫자/정보 색상", "#FFFFFF")
    route_color = st.selectbox("지도 경로 색상", ["Yellow", "Black"])
    
    st.markdown("---")
    st.header("⚙️ 크기/위치 조절")
    t_sz = st.slider("활동명 크기", 10, 200, 90)
    d_sz = st.slider("날짜 크기", 10, 100, 30)
    n_sz = st.slider("숫자 크기", 10, 150, 60)
    l_sz = st.slider("라벨 크기", 10, 80, 25)
    rx = st.slider("박스 좌측 위치", 0, 1080, 70)
    ry = st.slider("박스 상단 위치", 0, 1920, 1250)
    alpha = st.slider("박스 투명도", 0, 255, 50)

# --- [5. DAILY 모드] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
if app_mode == "DAILY":
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=5", headers=headers)
    if act_res.status_code == 200:
        acts = act_res.json()
        sel = st.selectbox("기록 선택", [f"{a['start_date_local']} - {a['name']}" for a in acts])
        a = acts[[f"{x['start_date_local']} - {x['name']}" for x in acts].index(sel)]
        
        date_v = a.get('start_date_local', "2026-01-01T00:00:00Z").replace("T", " ").replace("Z", "")[:16]
        dist_raw, sec = a.get('distance', 0), a.get('moving_time', 0)
        dist_v = f"{dist_raw / 1000:.2f}"
        pace_v = f"{int((sec/(dist_raw/1000))//60)}:{int((sec/(dist_raw/1000))%60):02d}" if dist_raw > 0 else "0:00"
        hr_v = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        poly = a.get('map', {}).get('summary_polyline', "")

        bg_file = st.file_uploader("1. 배경 사진 선택", type=['jpg', 'jpeg', 'png'])
        log_file = st.file_uploader("2. 로고 아이콘 선택", type=['jpg', 'jpeg', 'png'])

        if bg_file:
            canvas = ImageOps.fit(Image.open(bg_file).convert("RGBA"), (1080, 1920))
            overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            f_t, f_d, f_n, f_l = load_custom_font(selected_font, t_sz), load_custom_font(selected_font, d_sz), load_custom_font(selected_font, n_sz), load_custom_font(selected_font, l_sz)

            # 로그박스 배경 및 텍스트
            draw.rectangle([rx, ry, rx + 450, ry + 560], fill=(0, 0, 0, alpha))
            draw.text((rx + 50, ry + 40), a['name'], font=f_t, fill=main_color)
            line_y = ry + t_sz + 80
            draw.text((rx + 400, line_y - d_sz - 10), date_v, font=f_d, fill=num_color, anchor="ra")
            
            items = [("DISTANCE", f"{dist_v} km"), ("AVG PACE", f"{pace_v} /km"), ("AVG HR", f"{hr_v} bpm")]
            for i, (lab, val) in enumerate(items):
                py = line_y + 30 + (i * 125)
                draw.text((rx + 60, py), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx + 60, py + l_sz + 5), val, font=f_n, fill=num_color)

            # 지도 (로그박스 왼쪽 위 고정)
            if poly:
                try:
                    pts = polyline.decode(poly)
                    lats, lons = [p[0] for p in pts], [p[1] for p in pts]
                    mi_la, ma_la, mi_lo, ma_lo = min(lats), max(lats), min(lons), max(lons)
                    r_img = Image.new("RGBA", (350, 350), (0, 0, 0, 0))
                    dr_r = ImageDraw.Draw(r_img)
                    def sc(p):
                        x = (p[1] - mi_lo) / (ma_lo - mi_lo + 1e-9) * 280 + 35
                        y = 280 - ((p[0] - mi_la) / (ma_la - mi_la + 1e-9) * 280) + 35
                        return (x, y)
                    r_f = "#FFD700" if route_color == "Yellow" else "#000000"
                    dr_r.line([sc(p) for p in pts], fill=r_f, width=10)
                    canvas.paste(r_img, (rx - 20, ry - 380), r_img)
                except: pass

            if log_file:
                logo = get_circle_logo(log_file)
                canvas.paste(logo, (900, 60), logo)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_final.jpg")

elif app_mode == "WEEKLY":
    st.title("📅 Weekly Collage")
    after_ts = int((datetime.now() - timedelta(days=7)).timestamp())
    act_res = requests.get(f"https://www.strava.com/api/v3/athlete/activities?after={after_ts}", headers=headers)
    if act_res.status_code == 200:
        st.metric("이번 주 거리", f"{sum(a.get('distance', 0) for a in act_res.json()) / 1000:.2f} km")
        files = st.file_uploader("콜라주 사진 선택", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
        if files:
            collage = create_collage(files)
            if collage:
                st.image(collage, use_container_width=True)
                buf = io.BytesIO(); collage.save(buf, format="JPEG", quality=95)
                st.download_button("📸 저장", buf.getvalue(), "weekly.jpg")
