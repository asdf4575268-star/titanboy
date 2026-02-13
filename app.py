import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline
from datetime import datetime, timedelta

# --- [1. 기본 설정] ---
CLIENT_ID = '202275'
CLIENT_SECRET = '41f311299a14de733155c6c6e71505d3063fc31c'
# 🌟 사용자님의 새 도메인 주소
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
    # 🌟 ACTUAL_URL을 사용하여 redirect_uri 에러 방지
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}/&scope=activity:read_all&approval_prompt=force"
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
        
        # 데이터 정리
        dist_v = f"{a.get('distance', 0) / 1000:.2f}"
        sec = a.get('moving_time', 0)
        pace_v = f"{int((sec/(a.get('distance',1)/1000))//60)}:{int((sec/(a.get('distance',1)/1000))%60):02d}"
        hr_v = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        date_v = datetime.strptime(a['start_date_local'], "%Y-%m-%dT%H:%M
