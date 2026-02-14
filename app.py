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

# --- [4. 데이터 로드 및 레이아웃] ---
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
            t_val = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"
        else:
            w_acts = acts[:7]
            t_dist = sum([x.get('distance', 0) for x in w_acts]) / 1000
            t_time = sum([x.get('moving_time', 0) for x in w_acts])
            w_hrs = [x.get('average_heartrate', 0) for x in w_acts if x.get('average_heartrate')]
            avg_h = int(sum(w_hrs)/len(w_hrs)) if w_hrs else 0
            p_val = f"{int((t_time/t_dist)//60)}:{int((t_time/t_dist)%60):02d}" if t_dist > 0 else "0:00"
            t_val = f"{int(t_time//3600)}h {int((t_time%3600)//60)}m"

    with col1:
        st.header("📸 DATA")
        bg_files = st.file_uploader("사진 업로드", type=['jpg','jpeg','png'], accept_multiple_files=True)
        log_file = st.file_uploader("로고 업로드", type=['jpg','jpeg','png'])
        st.markdown("---")
        if mode == "DAILY":
            v_act, v_date = st.text_input("활동명", a['name']), st.text_input("날짜", a['start_date_local'][:10])
            v_dist, v_pace, v_hr = st.text_input("거리(km)", f"{d_km:.2f}"), st.text_input("페이스(/km)", p_val), st.text_input("심박(bpm)", h_val)
        else:
            v_act, v_date = st.text_input("제목", "WEEKLY RECAP"), st.text_input("기간", f"{acts[6]['start_date_local'][:10]} ~ {acts[0]['start_date_local'][:10]}")
            v_dist, v_pace, v_hr = st.text_input("총 거리(km)", f"{t_dist:.2f}"), st.text_input("평균 페이스", p_val), st.text_input("평균 심박", str(avg_h))

    with col3:
        st.header("🎨 DESIGN")
        sel_font = st.selectbox("폰트 선택", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
        t_color_sel = st.radio("테마 색상", ["Yellow (#FFD700)", "Black (#000000)"], horizontal=True)
        m_color = "#FFD700" if "Yellow" in t_color_sel else "#000000"
        
        # 제목 제거 및 슬라이더 유지
        t_sz = st.slider("활동명 크기", 10, 200, 70)
        d_sz = st.slider("날짜 크기", 5, 100, 20)
        n_sz = st.slider("숫자 크기", 10, 200, 40)
        l_sz = st.slider("라벨 크기", 5, 80, 20)
        
        st.markdown("---")
        box_mode = st.radio("박스 정렬", ["Vertical", "Horizontal"])
        rx = st.slider("X 위치", 0, 1080, 70)
        ry = st.slider("Y 위치", 0, 1920, 1150)
        # 너비/높이 수동 슬라이더 제거 (자동 계산으로 대체)
        box_alpha = st.slider("박스 투명도", 0, 255, 120)
        map_alpha = st.slider("지도 투명도", 0, 255, 80) # 기본값 80으로 변경

    # --- [5. 이미지 렌더링] ---
    if bg_files:
        if mode == "DAILY":
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
        else:
            canvas = Image.new("RGBA", (1080, 1920), (0,0,0,255))
            n = len(bg_files)
            rows = math.ceil(n / 2) if n > 1 else 1
            h_p = 1920 // rows
            for i, f in enumerate(bg_files):
                w_p = 1080 // (2 if n > 1 else 1)
                p_i = ImageOps.fit(Image.open(f).convert("RGBA"), (w_p, h_p))
                canvas.paste(p_i, ((i % 2) * w_p if n > 1 else 0, (i // 2) * h_p))

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)

        items = [("DISTANCE", f"{v_dist} km"), ("TIME", t_val), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]

        # --- [핵심] 박스 크기 자동 계산 로직 ---
        if box_mode == "Vertical":
            actual_rw = 580 # 세로 모드 고정 너비
            # 높이 = 상단여백 + 활동명 + 날짜 + 여백 + (아이템수 * 아이템높이) + 하단여백
            actual_rh = t_sz + d_sz + (len(items) * (n_sz + l_sz + 35)) + 150
        else:
            actual_rw = 1020 # 가로 모드 고정 너비
            # 높이 = 상단여백 + 활동명 + 날짜 + 중간여백 + 라벨 + 숫자 + 하단여백
            actual_rh = t_sz + d_sz + n_sz + l_sz + 200

        # 박스 그리기 (계산된 크기 적용)
        draw.rectangle([rx, ry, rx + actual_rw, ry + actual_rh], fill=(0, 0, 0, box_alpha))

        # 지도 오버레이 (계산된 크기 적용)
        p_line = a['map']['summary_polyline'] if mode == "DAILY" and 'map' in a and a['map'].get('summary_polyline') else None
        if p_line:
            pts = polyline.decode(p_line)
            if pts:
                lats, lons = zip(*pts)
                mi_la, ma_la, mi_lo, ma_lo = min(lats), max(lats), min(lons), max(lons)
                # 지도 레이어 크기도 자동 계산된 박스 크기에 맞춤
                map_layer = Image.new("RGBA", (actual_rw, actual_rh), (0,0,0,0))
                m_draw = ImageDraw.Draw(map_layer)
                def transform(la, lo):
                    tx = 30 + (lo - mi_lo) / (ma_lo - mi_lo + 0.00001) * (actual_rw - 60)
                    ty = (actual_rh - 30) - (la - mi_la) / (ma_la - mi_la + 0.00001) * (actual_rh - 60)
                    return tx, ty
                m_pts = [transform(la, lo) for la, lo in pts]
                m_draw.line(m_pts, fill=m_color + f"{map_alpha:02x}"[2:], width=7)
                overlay.paste(map_layer, (rx, ry), map_layer)

        # 텍스트 배치 (계산된 크기 적용)
        if box_mode == "Vertical":
            draw.text((rx+35, ry+30), v_act, font=f_t, fill=m_color)
            draw.text((rx+35, ry+30+t_sz+10), v_date, font=f_d, fill="#FFFFFF")
            y_c = ry + t_sz + d_sz + 80
            for lab, val in items:
                draw.text((rx+35, y_c), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx+35, y_c+l_sz+5), val, font=f_n, fill="#FFFFFF")
                y_c += (n_sz + l_sz + 40)
        else:
            draw.text((rx+actual_rw//2, ry+40), v_act, font=f_t, fill=m_color, anchor="ms")
            draw.text((rx+actual_rw//2, ry+40+t_sz), v_date, font=f_d, fill="#FFFFFF", anchor="ms")
            x_s = actual_rw // (len(items) + 1)
            for i, (lab, val) in enumerate(items):
                # 하단 위치 자동 계산
                draw.text((rx + x_s*(i+1), ry + actual_rh - n_sz - l_sz - 30), lab, font=f_l, fill="#AAAAAA", anchor="ms")
                draw.text((rx + x_s*(i+1), ry + actual_rh - n_sz - 10), val, font=f_n, fill="#FFFFFF", anchor="ms")

        if log_file:
            logo = get_circle_logo(log_file)
            canvas.paste(logo, (900, 50), logo)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin.jpg", use_container_width=True)
