import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline
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

def create_collage(image_files, target_size=(1080, 1350)):
    """여백을 절대 허용하지 않는 인스타그램용 콜라주"""
    imgs = [ImageOps.exif_transpose(Image.open(f).convert("RGB")) for f in image_files]
    if not imgs: return None
    
    count = len(imgs)
    # 사진 수에 따라 열(cols) 결정
    if count == 1: cols = 1
    elif count <= 4: cols = 2
    else: cols = 3
    
    rows = (count + cols - 1) // cols
    
    # 픽셀 오차 방지를 위해 정밀하게 셀 크기 계산
    cell_w = target_size[0] // cols
    cell_h = target_size[1] // rows
    
    # 검은색 배경으로 생성 (여백 발생 시 눈에 띄게 확인용, 실제론 꽉 채움)
    collage = Image.new("RGB", target_size, (0, 0, 0))
    
    for i, img in enumerate(imgs):
        # 🌟 ImageOps.fit으로 해당 셀 크기에 맞게 강제로 꽉 채움
        img_fitted = ImageOps.fit(img, (cell_w, cell_h), Image.LANCZOS, centering=(0.5, 0.5))
        
        x = (i % cols) * cell_w
        y = (i // cols) * cell_h
        
        # 마지막 줄 사진이 열 개수보다 부족할 경우, 마지막 사진을 옆으로 확장하여 여백 제거
        if i == count - 1 and count % cols != 0:
            remaining_cols = cols - (count % cols) + 1
            new_w = cell_w * remaining_cols
            img_fitted = ImageOps.fit(img, (new_w, cell_h), Image.LANCZOS, centering=(0.5, 0.5))
        
        collage.paste(img_fitted, (x, y))
        
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
    st.header("📸 사진 확인 (상시)")
    check_img = st.file_uploader("참고용 사진 업로드", type=['jpg', 'png'], key="side_check")
    if check_img:
        st.image(check_img, use_container_width=True)
    
    st.markdown("---")
    st.header("⚙️ 커스텀 설정")
    selected_font = st.selectbox("폰트 선택", ["Impact(BlackHan)", "Gothic(DoHyeon)", "Stylish(Jua)", "Clean(Noto)"])
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
        
        raw_date = a.get('start_date_local', "2026-01-01T00:00:00Z")
        date_v = raw_date.replace("T", " ").replace("Z", "")[:16]
        dist_v = f"{a.get('distance', 0) / 1000:.2f}"
        sec = a.get('moving_time', 0)
        pace_v = f"{int((sec/(a.get('distance',1)/1000))//60)}:{int((sec/(a.get('distance',1)/1000))%60):02d}"
        hr_v = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        
        bg_file = st.file_uploader("1. 배경 사진 선택", type=['jpg', 'jpeg', 'png'])
        if bg_file:
            col_img, col_info = st.columns([2, 1])
            with col_info:
                v_act = st.text_input("활동명", "RUNNING")
                v_date = st.text_input("날짜", date_v)
                v_dist, v_pace, v_hr = st.text_input("거리", dist_v), st.text_input("페이스", pace_v), st.text_input("심박", hr_v)

            canvas = ImageOps.fit(Image.open(bg_file).convert("RGBA"), (1080, 1920))
            overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            f_t, f_d, f_n, f_l = load_custom_font(selected_font, t_sz), load_custom_font(selected_font, d_sz), load_custom_font(selected_font, n_sz), load_custom_font(selected_font, l_sz)

            draw.rectangle([rx, ry, rx + 450, ry + 560], fill=(0, 0, 0, alpha))
            draw.text((rx + 50, ry + 40), v_act, font=f_t, fill="#FFD700")
            line_y = ry + t_sz + 80
            draw.text((rx + 400, line_y - d_sz - 10), v_date, font=f_d, fill="white", anchor="ra")
            
            items = [("DISTANCE", f"{v_dist} km"), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
            for i, (lab, val) in enumerate(items):
                py = line_y + 30 + (i * 125)
                draw.text((rx + 60, py), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx + 60, py + l_sz + 5), val, font=f_n, fill="white")

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_final.jpg")

# --- [6. WEEKLY 모드] ---
elif app_mode == "WEEKLY":
    st.title("📅 Weekly Collage")
    after_ts = int((datetime.now() - timedelta(days=7)).timestamp())
    act_res = requests.get(f"https://www.strava.com/api/v3/athlete/activities?after={after_ts}", headers=headers)
    
    if act_res.status_code == 200:
        acts = act_res.json()
        st.metric("이번 주 총 거리", f"{sum(a.get('distance', 0) for a in acts) / 1000:.2f} km")

        files = st.file_uploader("콜라주용 사진 선택", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
        if files:
            # 🌟 인스타그램 세로 규격 1080x1350
            collage = create_collage(files, target_size=(1080, 1350))
            if collage:
                st.image(collage, use_container_width=True)
                buf = io.BytesIO(); collage.save(buf, format="JPEG", quality=95)
                st.download_button("📸 콜라주 저장", buf.getvalue(), "weekly_no_margin.jpg")

