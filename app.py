import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, math

# --- [1. 기본 설정] ---
CLIENT_ID = '202275'
CLIENT_SECRET = '969201cab488e4eaf1398b106de1d4e520dc564c'
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

@st.cache_resource
def load_font(font_type, size):
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf"
    }
    f_url = fonts.get(font_type, fonts["BlackHanSans"])
    f_path = f"font_{font_type}_{int(size)}.ttf"
    if not os.path.exists(f_path):
        r = requests.get(f_url); open(f_path, "wb").write(r.content)
    return ImageFont.truetype(f_path, int(size))

# --- [2. 사이드바: 활동 정보 확인 & 커스텀 설정] ---
with st.sidebar:
    st.header("📊 ACTIVITY INFO")
    # Strava 연동 및 활동 선택
    if 'access_token' not in st.session_state: st.session_state['access_token'] = None
    
    if not st.session_state['access_token']:
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force"
        st.link_button("🚀 Strava 연동하기", auth_url)
    else:
        headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
        act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers)
        if act_res.status_code == 200:
            acts = act_res.json()
            act_options = [f"{a['start_date_local'][:10]} - {a['name']}" for a in acts]
            sel_idx = st.selectbox("불러올 활동 선택", range(len(act_options)), format_func=lambda x: act_options[x])
            curr_a = acts[sel_idx]
            
            # 활동 정보 표시 (사용자가 확인할 수 있도록)
            st.info(f"📍 활동명: {curr_a['name']}\n\n"
                    f"📅 날짜: {curr_a['start_date_local'][:10]}\n\n"
                    f"🏃 거리: {curr_a['distance']/1000:.2f} km\n\n"
                    f"⏱️ 시간: {curr_a['moving_time']//60}분 {curr_a['moving_time']%60}초\n\n"
                    f"💓 평균심박: {int(curr_a.get('average_heartrate', 0))} bpm")

    st.divider()
    st.header("⚙️ CUSTOM SETTING")
    insta_mode = st.selectbox("캔버스 비율", ["1:1 (Square)", "4:5 (Portrait)"])
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon"])
    
    # 블랙 컬러 추가된 색상 선택기
    m_color = st.selectbox("폰트 색상", ["#FFD700", "#FFFFFF", "#000000", "#FF4500"], format_func=lambda x: {"#FFD700":"Yellow", "#FFFFFF":"White", "#000000":"Black", "#FF4500":"Orange"}[x])
    box_alpha = st.slider("박스 투명도", 0, 255, 110)

# --- [3. 메인 화면: 데이터 입력 및 미리보기] ---
col_in, col_pre = st.columns([1, 1.5], gap="large")

with col_in:
    st.header("📸 DATA INPUT")
    bg_files = st.file_uploader("사진 업로드 (Weekly는 여러 장)", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("원형 로고", type=['jpg','jpeg','png'])
    
    # 기본값 설정
    v_act, v_date, v_dist, v_hr = "RUNNING", "2026.02.14", "10.00", "150"
    if st.session_state['access_token'] and 'curr_a' in locals():
        v_act, v_date = curr_a['name'], curr_a['start_date_local'][:10]
        v_dist = f"{curr_a['distance']/1000:.2f}"
        v_hr = str(int(curr_a.get('average_heartrate', 0)))

    v_act = st.text_input("활동명 (Title)", v_act)
    v_date = st.text_input("날짜 (Date)", v_date)
    v_dist = st.text_input("거리 (km)", v_dist)
    v_hr = st.text_input("심박 (bpm)", v_hr)

with col_pre:
    st.header("🖼️ INSTA PREVIEW")
    if bg_files:
        try:
            # 폰트 고정 크기 (90, 30, 60)
            f_t, f_d, f_n, f_l = load_font(sel_font, 90), load_font(sel_font, 30), load_font(sel_font, 60), load_font(sel_font, 22)
            CW, CH = (1080, 1080) if insta_mode == "1:1 (Square)" else (1080, 1350)
            canvas = Image.new("RGBA", (CW, CH), (0,0,0,255))
            
            # --- 여백 제거 로직 ---
            num_pics = len(bg_files)
            if num_pics == 1:
                img = ImageOps.fit(ImageOps.exif_transpose(Image.open(bg_files[0])).convert("RGBA"), (CW, CH))
                canvas.paste(img, (0,0))
            else:
                cols = 2; rows = math.ceil(num_pics / cols)
                w_u, h_u = CW // cols, CH // rows
                for i, f in enumerate(bg_files):
                    img = ImageOps.fit(ImageOps.exif_transpose(Image.open(f)).convert("RGBA"), (w_u, h_u))
                    canvas.paste(img, ((i % cols) * w_u, (i // cols) * h_u))

            overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            
            # 박스 & 텍스트 렌더링
            bw, bh = (940, 280) if box_orient == "Horizontal" else (480, 620)
            bx, by = (CW - bw) // 2, CH - bh - 60
            draw.rectangle([bx, by, bx + bw, by + bh], fill=(0,0,0,box_alpha))
            
            # 소문자 단위 강제 적용
            items = [("distance", f"{v_dist} km"), ("avg bpm", f"{v_hr} bpm")]
            
            if box_orient == "Horizontal":
                draw.text((bx + (bw//2) - (draw.textlength(v_act, f_t)//2), by + 30), v_act, font=f_t, fill=m_color)
                draw.text((bx + (bw//2) - (draw.textlength(v_date, f_d)//2), by + 130), v_date, font=f_d, fill="#AAAAAA")
                for i, (lab, val) in enumerate(items):
                    ix = bx + (i * (bw//2)) + (bw//4)
                    draw.text((ix - (draw.textlength(lab, f_l)//2), by + 180), lab, font=f_l, fill="#AAAAAA")
                    draw.text((ix - (draw.textlength(val, f_n)//2), by + 210), val, font=f_n, fill="#FFFFFF")
            else:
                draw.text((bx+40, by+40), v_act, font=f_t, fill=m_color)
                draw.text((bx+40, by+140), v_date, font=f_d, fill="#AAAAAA")
                curr_y = by + 210
                for lab, val in items:
                    draw.text((bx+40, curr_y), lab, font=f_l, fill="#AAAAAA")
                    draw.text((bx+40, curr_y+30), val, font=f_n, fill="#FFFFFF")
                    curr_y += 120

            if log_file:
                l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (100, 100))
                overlay.paste(l_img, (bx + bw - 120, by + 20), l_img)

            st.image(Image.alpha_composite(canvas, overlay).convert("RGB"), use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")
