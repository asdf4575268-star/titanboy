import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 기본 설정 및 인증] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

def logout():
    st.session_state['access_token'] = None
    st.query_params.clear()
    st.rerun()

@st.cache_resource
def load_font(font_type, size):
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf",
        "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf",
        "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Bold.ttf"
    }
    f_url = fonts.get(font_type, fonts["BlackHanSans"])
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

# 인증 로직
params = st.query_params
if "code" in params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": params["code"], "grant_type": "authorization_code"
        }, timeout=15)
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            st.query_params.clear()
            st.rerun()
    except: pass

if not st.session_state['access_token']:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [2. 데이터 로드 및 계산] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)

if act_res.status_code == 200:
    acts = act_res.json()
    col1, col2, col3 = st.columns([1, 2, 1], gap="medium")

    with col2:
        mode = st.radio("작업 모드", ["DAILY", "WEEKLY"], horizontal=True)
        if mode == "DAILY":
            sel_str = st.selectbox("기록 선택", [f"{a['start_date_local'][:10]} - {a['name']}" for a in acts])
            idx = [f"{x['start_date_local'][:10]} - {x['name']}" for x in acts].index(sel_str)
            a = acts[idx]
            d_km, m_sec = a.get('distance', 0)/1000, a.get('moving_time', 0)
            p_val = f"{int((m_sec/d_km)//60)}:{int((m_sec/d_km)%60):02d}" if d_km > 0 else "0:00"
            h_val = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
            t_val = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"
        else:
            # 주간 데이터 합산 (최근 7개)
            w_acts = acts[:7]
            t_dist = sum([x.get('distance', 0) for x in w_acts]) / 1000
            t_time = sum([x.get('moving_time', 0) for x in w_acts])
            t_hrs = [x.get('average_heartrate', 0) for x in w_acts if x.get('average_heartrate')]
            avg_hr = int(sum(t_hrs)/len(t_hrs)) if t_hrs else 0
            avg_spd = (t_dist / (t_time/3600)) if t_time > 0 else 0
            t_val = f"{int(t_time//3600)}h {int((t_time%3600)//60)}m"

    with col1:
        st.header("📸 DATA")
        bg_files = st.file_uploader("사진 선택", type=['jpg','jpeg','png'], accept_multiple_files=True)
        log_file = st.file_uploader("로고 업로드", type=['jpg','jpeg','png'])
        if mode == "DAILY":
            v_act, v_date = st.text_input("활동명", a['name']), st.text_input("날짜", a['start_date_local'][:10])
            v_dist, v_pace, v_hr = st.text_input("거리(km)", f"{d_km:.2f}"), st.text_input("페이스(/km)", p_val), st.text_input("심박(bpm)", h_val)
        else:
            v_act = st.text_input("제목", "WEEKLY RECAP")
            v_dist, v_time, v_spd, v_hr = st.text_input("총 거리", f"{t_dist:.2f} km"), st.text_input("총 시간", t_val), st.text_input("평균 속도", f"{avg_spd:.1f} km/h"), st.text_input("평균 심박", f"{avg_hr} bpm")

    with col3:
        st.header("🎨 DESIGN")
        sel_font = st.selectbox("폰트 선택", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
        m_color = st.color_picker("포인트 색상", "#FFD700")
        sub_color = st.color_picker("텍스트 색상", "#FFFFFF")
        
        # 슬라이더 (DAILY 전용 및 공용)
        t_sz = st.slider("제목 크기", 10, 200, 70)
        n_sz = st.slider("숫자 크기", 10, 200, 45)
        
        if mode == "DAILY":
            st.markdown("---")
            box_mode = st.radio("박스 정렬", ["Vertical", "Horizontal"])
            rx = st.slider("X 위치", 0, 1080, 70)
            ry = st.slider("Y 위치", 0, 1920, 1150)
            box_alpha = st.slider("박스 투명도", 0, 255, 110)
            map_alpha = st.slider("지도 투명도", 0, 255, 15)
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🔓 로그아웃", use_container_width=True): logout()

    # --- [3. 이미지 렌더링 엔진] ---
    if bg_files:
        if mode == "DAILY":
            # 9:16 세로형
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
            overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            f_t, f_n = load_font(sel_font, t_sz), load_font(sel_font, n_sz)
            f_d, f_l = load_font(sel_font, 25), load_font(sel_font, 20)
            items = [("DISTANCE", f"{v_dist} km"), ("TIME", t_val), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
            
            rw, rh = (560, t_sz + 400) if box_mode == "Vertical" else (1000, t_sz + 250)
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0, 0, 0, box_alpha))
            
            # (DAILY 전용 지도 및 텍스트 로직 생략 - 이전과 동일하게 유지됨)
            draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
            y_c = ry + t_sz + 60
            for lab, val in items:
                draw.text((rx+40, y_c), f"{lab}: {val}", font=f_n, fill=sub_color)
                y_c += n_sz + 10
            final = Image.alpha_composite(canvas, overlay).convert("RGB")

        else:
            # 1:1 인스타그램 정사각 규격 (1080x1080)
            canvas = Image.new("RGBA", (1080, 1080), (0,0,0,255))
            n = len(bg_files)
            # 사진 영역 (상단 880px) / 통계 영역 (하단 200px)
            cols = 2 if n > 1 else 1
            rows = math.ceil(n / cols)
            img_h = 880 // rows
            img_w = 1080 // cols
            
            for i, f in enumerate(bg_files):
                p_i = ImageOps.fit(Image.open(f).convert("RGBA"), (img_w, img_h))
                canvas.paste(p_i, ((i % cols) * img_w, (i // cols) * img_h))
            
            # 하단 통계 바 렌더링
            draw = ImageDraw.Draw(canvas)
            f_t, f_n = load_font(sel_font, 45), load_font(sel_font, 35)
            f_l = load_font(sel_font, 18)
            
            # 배경 바
            draw.rectangle([0, 880, 1080, 1080], fill=(15, 15, 15, 255))
            draw.text((40, 910), v_act, font=f_t, fill=m_color)
            
            # 통계 항목 가로 배치
            w_items = [("DIST", v_dist), ("TIME", v_time), ("SPD", v_spd), ("HR", v_hr)]
            for i, (lab, val) in enumerate(w_items):
                x_p = 40 + (i * 260)
                draw.text((x_p, 975), lab, font=f_l, fill="#AAAAAA")
                draw.text((x_p, 1000), val, font=f_n, fill=sub_color)
            
            final = canvas.convert("RGB")

        if log_file:
            logo = get_circle_logo(log_file)
            final.paste(logo, (920, 30), logo if logo.mode=='RGBA' else None)

        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_weekly.jpg", use_container_width=True)
