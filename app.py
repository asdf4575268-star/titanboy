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
    # 권한 설정에 activity:read_all 포함 확인
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=activity:read_all,profile:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기 (권한 모두 체크 필수)", auth_url)
    st.stop()

# --- [4. 사이드바 설정] ---
with st.sidebar:
    app_mode = st.radio("🚀 작업 모드", ["DAILY", "WEEKLY"])
    st.markdown("---")
    st.header("🎨 디자인/폰트")
    selected_font = st.selectbox("폰트 선택", ["BlackHanSans", "NanumBrush", "Jua", "Pretendard(Bold)"])
    main_color = st.color_picker("활동명 색상", "#FFD700")
    num_color = st.color_picker("숫자/정보 색상", "#FFFFFF")
    route_color = st.selectbox("지도 경로 색상", ["Yellow", "Black", "White"])
    
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
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers)
    if act_res.status_code == 200:
        acts = act_res.json()
        sel = st.selectbox("기록 선택", [f"{a['start_date_local']} - {a['name']}" for a in acts])
        a = acts[[f"{x['start_date_local']} - {x['name']}" for x in acts].index(sel)]
        
        # 지도 데이터 추출 (summary_polyline)
        poly = a.get('map', {}).get('summary_polyline', "")
        if not poly:
            st.warning("⚠️ 선택한 활동에 지도 경로 데이터가 없습니다. (야외 GPS 활동인지 확인해 주세요)")

        bg_file = st.file_uploader("1. 배경 사진 선택", type=['jpg', 'jpeg', 'png'])
        if bg_file:
            canvas = ImageOps.fit(Image.open(bg_file).convert("RGBA"), (1080, 1920))
            overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            f_t, f_d, f_n, f_l = load_custom_font(selected_font, t_sz), load_custom_font(selected_font, d_sz), load_custom_font(selected_font, n_sz), load_custom_font(selected_font, l_sz)

            # 로그박스 배경 및 텍스트
            draw.rectangle([rx, ry, rx + 450, ry + 560], fill=(0, 0, 0, alpha))
            draw.text((rx + 50, ry + 40), a['name'], font=f_t, fill=main_color)
            line_y = ry + t_sz + 80
            draw.text((rx + 400, line_y - d_sz - 10), a['start_date_local'][:16].replace("T", " "), font=f_d, fill=num_color, anchor="ra")
            
            dist_km = a.get('distance', 0) / 1000
            pace_min = int((a.get('moving_time', 0) / dist_km) // 60) if dist_km > 0 else 0
            pace_sec = int((a.get('moving_time', 0) / dist_km) % 60) if dist_km > 0 else 0
            
            items = [("DISTANCE", f"{dist_km:.2f} km"), ("AVG PACE", f"{pace_min}:{pace_sec:02d} /km"), ("AVG HR", f"{int(a.get('average_heartrate', 0))} bpm")]
            for i, (lab, val) in enumerate(items):
                py = line_y + 30 + (i * 125)
                draw.text((rx + 60, py), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx + 60, py + l_sz + 5), val, font=f_n, fill=num_color)

            # 지도 그리기 (로그박스 왼쪽 위)
            if poly:
                try:
                    pts = polyline.decode(poly)
                    lats, lons = [p[0] for p in pts], [p[1] for p in pts]
                    mi_la, ma_la, mi_lo, ma_lo = min(lats), max(lats), min(lons), max(lons)
                    
                    # 지도 전용 캔버스
                    r_img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
                    dr_r = ImageDraw.Draw(r_img)
                    def sc(p):
                        x = (p[1] - mi_lo) / (ma_lo - mi_lo + 1e-9) * 320 + 40
                        y = 320 - ((p[0] - mi_la) / (ma_la - mi_la + 1e-9) * 320) + 40
                        return (x, y)
                    
                    r_f = {"Yellow": "#FFD700", "Black": "#000000", "White": "#FFFFFF"}.get(route_color, "#FFD700")
                    dr_r.line([sc(p) for p in pts], fill=r_f, width=12)
                    
                    # 🌟 지도 위치: 로그박스(rx, ry)를 기준으로 왼쪽 위에 배치
                    canvas.paste(r_img, (rx - 40, ry - 420), r_img)
                except Exception as e:
                    st.error(f"지도 생성 중 오류: {e}")

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_final.jpg")
