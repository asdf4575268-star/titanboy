import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 기본 설정] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# --- [2. 스포츠 폰트 5종 로드] ---
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

# --- [3. 인증 로직] ---
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

# --- [4. 데이터 로드 및 3분할] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)

if act_res.status_code == 200:
    acts = act_res.json()
    col1, col2, col3 = st.columns([1, 2, 1], gap="medium")

    with col2:
        mode = st.radio("작업 모드", ["DAILY", "WEEKLY"], horizontal=True)
        if mode == "DAILY":
            sel_str = st.selectbox("기록 선택", [f"{a['start_date_local'][:10]} - {a['name']}" for a in acts])
            a = acts[[f"{x['start_date_local'][:10]} - {x['name']}" for x in acts].index(sel_str)]
            d_km, m_sec = a.get('distance', 0)/1000, a.get('moving_time', 0)
            p_val = f"{int((m_sec/d_km)//60)}:{int((m_sec/d_km)%60):02d}" if d_km > 0 else "0:00"
            h_val = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        else:
            # WEEKLY 데이터 합산 (최근 7일)
            w_acts = acts[:7]
            total_dist = sum([x.get('distance', 0) for x in w_acts]) / 1000
            total_time = sum([x.get('moving_time', 0) for x in w_acts])
            w_hr = [x.get('average_heartrate', 0) for x in w_acts if x.get('average_heartrate')]
            avg_hr = int(sum(w_hr)/len(w_hr)) if w_hr else 0
            p_val = f"{int((total_time/total_dist)//60)}:{int((total_time/total_dist)%60):02d}" if total_dist > 0 else "0:00"

    with col1:
        st.header("📸 DATA")
        bg_files = st.file_uploader("사진 선택", type=['jpg','jpeg','png'], accept_multiple_files=True)
        log_file = st.file_uploader("로고 업로드", type=['jpg','jpeg','png'])
        st.markdown("---")
        if mode == "DAILY":
            v_act, v_date = st.text_input("활동명", a['name']), st.text_input("날짜", a['start_date_local'][:10])
            v_dist, v_pace, v_hr = st.text_input("거리(km)", f"{d_km:.2f}"), st.text_input("페이스(/km)", p_val), st.text_input("심박(bpm)", h_val)
        else:
            v_act, v_date = st.text_input("제목", "WEEKLY RECAP"), st.text_input("날짜", f"{acts[6]['start_date_local'][:10]} ~ {acts[0]['start_date_local'][:10]}")
            v_dist, v_pace, v_hr = st.text_input("총 거리(km)", f"{total_dist:.2f}"), st.text_input("평균 페이스", p_val), st.text_input("평균 심박", str(avg_hr))

    with col3:
        st.header("🎨 DESIGN")
        sel_font = st.selectbox("스포츠 폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
        theme_color = st.radio("테마 색상", ["Yellow (#FFD700)", "Black (#000000)"], horizontal=True)
        m_color = "#FFD700" if "Yellow" in theme_color else "#000000"
        
        # 폰트 수치 고정 (70, 20, 40, 20)
        t_sz, d_sz, n_sz, l_sz = 70, 20, 40, 20
        st.caption(f"고정: 활동명{t_sz}, 날짜{d_sz}, 숫자{n_sz}, 라벨{l_sz}")
        
        st.markdown("---")
        box_mode = st.radio("로그박스 정렬", ["Vertical", "Horizontal"])
        rx = st.slider("박스 X", 0, 1080, 70)
        ry = st.slider("박스 Y", 0, 1920, 1150)
        rw_adj = st.slider("박스 너비 조절", 300, 1000, 500)
        rh_adj = st.slider("박스 높이 조절", 200, 1000, 450)
        box_alpha = st.slider("박스 투명도", 0, 255, 120)
        map_alpha = st.slider("지도 투명도", 0, 255, 150)

    # --- [5. 이미지 생성 엔진] ---
    if bg_files:
        if mode == "DAILY":
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
        else:
            canvas = Image.new("RGBA", (1080, 1920), (0,0,0,255))
            n = len(bg_files)
            rows = math.ceil(n / 2) if n > 1 else 1
            h_pic = 1920 // rows
            for i, f in enumerate(bg_files):
                w_pic = 1080 // (2 if n > 1 else 1)
                p_img = ImageOps.fit(Image.open(f).convert("RGBA"), (w_pic, h_pic))
                canvas.paste(p_img, ((i % 2) * w_pic if n > 1 else 0, (i // 2) * h_pic))

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)

        # 1. 로그박스 그리기
        draw.rectangle([rx, ry, rx+rw_adj, ry+rh_adj], fill=(0, 0, 0, box_alpha))

        # 2. 지도 배경 오버레이 (박스 안으로)
        current_polyline = a['map']['summary_polyline'] if mode == "DAILY" and 'map' in a and a['map'].get('summary_polyline') else None
        if current_polyline:
            pts = polyline.decode(current_polyline)
            if pts:
                lats, lons = zip(*pts)
                mi_la, ma_la, mi_lo, ma_lo = min(lats), max(lats), min(lons), max(lons)
                map_layer = Image.new("RGBA", (rw_adj, rh_adj), (0,0,0,0))
                m_draw = ImageDraw.Draw(map_layer)
                def t_map(la, lo):
                    x = 20 + (lo - mi_lo) / (ma_lo - mi_lo + 0.00001) * (rw_adj - 40)
                    y = (rh_adj - 20) - (la - mi_la) / (ma_la - mi_la + 0.00001) * (rh_adj - 40)
                    return x, y
                t_pts = [t_map(la, lo) for la, lo in pts]
                m_draw.line(t_pts, fill=m_color + f"{map_alpha:02x}"[2:], width=6)
                overlay.paste(map_layer, (rx, ry), map_layer)

        # 3. 텍스트 그리기
        items = [("DISTANCE", f"{v_dist} km"), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
        if box_mode == "Vertical":
            # 세로모드: 가장자리 왼쪽 정렬
            draw.text((rx+30, ry+30), v_act, font=f_t, fill=m_color)
            draw.text((rx+30, ry+30+t_sz+5), v_date, font=f_d, fill="#FFFFFF")
            y_cur = ry + t_sz + d_sz + 60
            for lab, val in items:
                draw.text((rx+30, y_cur), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx+30, y_cur+l_sz+2), val, font=f_n, fill="#FFFFFF")
                y_cur += (n_sz + l_sz + 35)
        else:
            # 가로모드: 가운데 정렬
            draw.text((rx+rw_adj//2, ry+40), v_act, font=f_t, fill=m_color, anchor="ms")
            draw.text((rx+rw_adj//2, ry+40+t_sz), v_date, font=f_d, fill="#FFFFFF", anchor="ms")
            x_step = rw_adj // (len(items) + 1)
            for i, (lab, val) in enumerate(items):
                draw.text((rx + x_step*(i+1), ry+rh_adj-100), lab, font=f_l, fill="#AAAAAA", anchor="ms")
                draw.text((rx + x_step*(i+1), ry+rh_adj-50), val, font=f_n, fill="#FFFFFF", anchor="ms")

        if log_file:
            logo = get_circle_logo(log_file)
            canvas.paste(logo, (900, 50), logo)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_result.jpg", use_container_width=True)
