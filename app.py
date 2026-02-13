import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline
from datetime import datetime, timedelta

# --- [1. 기본 설정] ---
CLIENT_ID = '202275'
CLIENT_SECRET = '41f311299a14de733155c6c6e71505d3063fc31c'
# 🌟 슬래시(/) 없는 순수 도메인 주소
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# --- [2. 유틸리티 함수] ---
@st.cache_resource
def load_custom_font(font_type, size):
    fonts = {
        "Impact(BlackHan)": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Gothic(DoHyeon)": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf",
        "Stylish(Jua)": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "Clean(Noto)": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"
    }
    font_url = fonts.get(font_type, fonts["Clean(Noto)"])
    font_path = f"{font_type.split('(')[0]}.ttf"
    if not os.path.exists(font_path):
        res = requests.get(font_url)
        with open(font_path, "wb") as f: f.write(res.content)
    return ImageFont.truetype(font_path, int(size))

def get_circle_logo(img_file, size=(130, 130)):
    img = Image.open(img_file).convert("RGBA")
    img = ImageOps.fit(img, size, centering=(0.5, 0.5))
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    img.putalpha(mask)
    return img

def create_collage(image_files, target_size=(1080, 1080)):
    imgs = [ImageOps.exif_transpose(Image.open(f).convert("RGB")) for f in image_files]
    if not imgs: return None
    cols = 2 if len(imgs) <= 4 else 3
    rows = (len(imgs) + cols - 1) // cols
    cell_w, cell_h = target_size[0] // cols, target_size[1] // rows
    collage = Image.new("RGB", target_size, (255, 255, 255))
    for i, img in enumerate(imgs):
        img = ImageOps.fit(img, (cell_w, cell_h), centering=(0.5, 0.5))
        collage.paste(img, ((i % cols) * cell_w, (i // cols) * cell_h))
    return collage

# --- [3. 스트라바 연동] ---
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# URL 파라미터에서 인증 코드 추출
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
    # 🌟 redirect_uri 끝에 슬래시를 제거하여 API 설정과 일치시킴
    auth_url = (
        f"https://www.strava.com/oauth/authorize?"
        f"client_id={CLIENT_ID}&response_type=code&"
        f"redirect_uri={ACTUAL_URL}&scope=activity:read_all&approval_prompt=force"
    )
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [4. 공통 사이드바 (사용자 지침 반영)] ---
with st.sidebar:
    app_mode = st.radio("🚀 작업 모드", ["DAILY", "WEEKLY"])
    st.markdown("---")
    st.header("📸 사진 확인 (상시)")
    check_img = st.file_uploader("참고용 사진 업로드", type=['jpg', 'png'], key="side_check")
    if check_img:
        st.image(check_img, use_container_width=True, caption="상시 확인창")
    
    st.markdown("---")
    st.header("⚙️ 커스텀 설정")
    selected_font = st.selectbox("폰트 선택", ["Impact(BlackHan)", "Gothic(DoHyeon)", "Stylish(Jua)", "Clean(Noto)"])
    
    # [지침] 활동명 90, 날짜 30, 숫자 60
    t_sz = st.slider("활동명 크기", 10, 200, 90)
    d_sz = st.slider("날짜 크기", 10, 100, 30)
    n_sz = st.slider("숫자 크기", 10, 150, 60)
    l_sz = st.slider("라벨 크기", 10, 80, 25)
    
    rx = st.slider("박스 좌우", 0, 1080, 70)
    ry = st.slider("박스 상하", 0, 1920, 1250)
    alpha = st.slider("투명도", 0, 255, 50)

# --- [5. DAILY 모드] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
if app_mode == "DAILY":
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=5", headers=headers)
    if act_res.status_code == 200:
        acts = act_res.json()
        sel = st.selectbox("기록 선택", [f"{a['start_date_local']} - {a['name']}" for a in acts])
        a = acts[[f"{x['start_date_local']} - {x['name']}" for x in acts].index(sel)]
        
        # 날짜 안전하게 처리
        raw_date = a.get('start_date_local', "2026-01-01T00:00:00Z")
        date_v = raw_date.replace("T", " ").replace("Z", "")[:16]
        
        dist_v = f"{a.get('distance', 0) / 1000:.2f}"
        sec = a.get('moving_time', 0)
        pace_v = "0:00"
        if a.get('distance', 0) > 0:
            pace_raw = sec / (a.get('distance') / 1000)
            pace_v = f"{int(pace_raw//60)}:{int(pace_raw%60):02d}"
        hr_v = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        poly = a.get('map', {}).get('summary_polyline', "")

        bg_file = st.file_uploader("1. 배경 사진 선택", type=['jpg', 'jpeg', 'png'])
        log_file = st.file_uploader("2. 로고 아이콘 선택 (옵션)", type=['jpg', 'jpeg', 'png'])

        if bg_file:
            col_img, col_info = st.columns([2, 1])
            with col_info:
                v_act = st.text_input("활동명", "RUNNING")
                v_date = st.text_input("날짜", date_v)
                v_dist = st.text_input("거리", dist_v)
                v_pace = st.text_input("페이스", pace_v)
                v_hr = st.text_input("심박", hr_v)

            canvas = ImageOps.fit(Image.open(bg_file).convert("RGBA"), (1080, 1920))
            overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            f_t, f_d, f_n, f_l = load_custom_font(selected_font, t_sz), load_custom_font(selected_font, d_sz), load_custom_font(selected_font, n_sz), load_custom_font(selected_font, l_sz)

            draw.rectangle([rx, ry, rx + 450, ry + 560], fill=(0, 0, 0, alpha))
            draw.text((rx + 50, ry + 40), v_act, font=f_t, fill="#FFD700")
            line_y = ry + t_sz + 80
            draw.text((rx + 400, line_y - d_sz - 10), v_date, font=f_d, fill="white", anchor="ra")
            
            # [지침] km, bpm 소문자 고정
            items = [("DISTANCE", f"{v_dist} km"), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
            for i, (lab, val) in enumerate(items):
                py = line_y + 30 + (i * 125)
                draw.text((rx + 60, py), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx + 60, py + l_sz + 5), val, font=f_n, fill="white")

            if log_file:
                logo = get_circle_logo(log_file)
                canvas.paste(logo, (900, 60), logo)

            if poly:
                try:
                    pts = polyline.decode(poly)
                    lats, lons = [p[0] for p in pts], [p[1] for p in pts]
                    mi_la, ma_la, mi_lo, ma_lo = min(lats), max(lats), min(lons), max(lons)
                    r_img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
                    dr_r = ImageDraw.Draw(r_img)
                    def sc(p):
                        x = (p[1] - mi_lo) / (ma_lo - mi_lo + 1e-9) * 260 + 20
                        y = 260 - ((p[0] - mi_la) / (ma_la - mi_la + 1e-9) * 260) + 20
                        return (x, y)
                    dr_r.line([sc(p) for p in pts], fill="white", width=6)
                    canvas.paste(r_img, (rx + 50, ry - 320), r_img)
                except: pass

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            with col_img:
                st.image(final, use_container_width=True)
                buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
                st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_final.jpg")

# --- [6. WEEKLY 모드] ---
elif app_mode == "WEEKLY":
    st.title("📅 이번 주 운동 요약")
    after_ts = int((datetime.now() - timedelta(days=7)).timestamp())
    act_res = requests.get(f"https://www.strava.com/api/v3/athlete/activities?after={after_ts}", headers=headers)
    if act_res.status_code == 200:
        acts = act_res.json()
        total_dist = sum(a.get('distance', 0) for a in acts) / 1000
        total_time = sum(a.get('moving_time', 0) for a in acts)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 거리", f"{total_dist:.2f} km")
        c2.metric("평균 페이스", f"{int((total_time/total_dist)//60)}:{int((total_time/total_dist)%60):02d} /km" if total_dist > 0 else "0:00")
        c3.metric("활동 횟수", f"{len(acts)} 회")
        st.markdown("---")
        files = st.file_uploader("사진들을 선택하세요", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
        if files:
            collage = create_collage(files)
            if collage:
                st.image(collage, use_container_width=True)
                buf = io.BytesIO(); collage.save(buf, format="JPEG", quality=95)
                st.download_button("📸 콜라주 저장", buf.getvalue(), "weekly_collage.jpg")
