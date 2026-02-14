import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 시스템 설정] ---
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
    f_path = f"font_{font_type}_{int(size)}.ttf"
    try:
        if not os.path.exists(f_path):
            r = requests.get(f_url, timeout=10)
            with open(f_path, "wb") as f: f.write(r.content)
        return ImageFont.truetype(f_path, int(size))
    except:
        return ImageFont.load_default()

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return rgb + (alpha,)

# --- [2. Strava 인증] ---
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
    except: st.error("인증 처리 중 오류가 발생했습니다.")

if not st.session_state['access_token']:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [3. 데이터 로드] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
try:
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers, timeout=15)
    acts = act_res.json() if act_res.status_code == 200 else []
except:
    acts = []
    st.warning("활동 데이터를 불러오지 못했습니다.")

# --- [4. UI 구성] ---
col1, col2, col3 = st.columns([1, 2, 1], gap="medium")
COLOR_OPTIONS = {"Garmin Yellow": "#FFD700", "Pure White": "#FFFFFF", "Neon Orange": "#FF4500", "Electric Blue": "#00BFFF", "Soft Grey": "#AAAAAA"}

with col2:
    mode = st.radio("작업 모드", ["DAILY", "WEEKLY"], horizontal=True)
    if mode == "DAILY" and acts:
        sel_str = st.selectbox("기록 선택", [f"{a.get('start_date_local','')[:10]} - {a.get('name','')}" for a in acts])
        idx = [f"{x.get('start_date_local','')[:10]} - {x.get('name','')}" for x in acts].index(sel_str)
        a = acts[idx]
        d_km = a.get('distance', 0) / 1000
        m_sec = a.get('moving_time', 0)
        p_str = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
        h_val = str(int(a.get('average_heartrate', 0)))
    elif mode == "WEEKLY" and acts:
        w_acts = acts[:7]
        t_dist = sum([x.get('distance', 0) for x in w_acts]) / 1000
        t_time = sum([x.get('moving_time', 0) for x in w_acts])
        avg_p_str = f"{int((t_time/t_dist)//60)}'{int((t_time/t_dist)%60):02d}\"" if t_dist > 0 else "0'00\""
        t_hrs = [x.get('average_heartrate', 0) for x in w_acts if x.get('average_heartrate')]
        avg_hr = int(sum(t_hrs)/len(t_hrs)) if t_hrs else 0

with col1:
    st.header("📸 DATA")
    bg_files = st.file_uploader("사진 선택", type=['jpg','jpeg','png'], accept_multiple_files=True)
    if mode == "DAILY" and acts:
        v_act = st.text_input("활동명", a.get('name',''))
        v_date = st.text_input("날짜", a.get('start_date_local','')[:10])
        v_dist = st.text_input("거리(km)", f"{d_km:.2f}")
        v_pace = st.text_input("페이스(분/km)", p_str)
        v_hr = st.text_input("심박(bpm)", h_val)
    elif mode == "WEEKLY":
        v_act_w = st.text_input("주간 제목", "WEEKLY RECAP")
        v_dist_w = st.text_input("총 거리", f"{t_dist:.2f} km")
        v_pace_w = st.text_input("평균 페이스", avg_p_str)
        v_hr_w = st.text_input("평균 심박", f"{avg_hr} bpm")

with col3:
    st.header("🎨 DESIGN")
    show_box = st.checkbox("로그 박스 표시", value=True)
    sel_font = st.selectbox("폰트 선택", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    sel_m_color = st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()), index=0)
    sel_sub_color = st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)
    m_color, sub_color = COLOR_OPTIONS[sel_m_color], COLOR_OPTIONS[sel_sub_color]
    
    t_sz, d_sz, n_sz, l_sz = st.slider("활동명(90)", 10, 200, 90), st.slider("날짜(30)", 5, 100, 30), st.slider("숫자(60)", 10, 200, 60), st.slider("라벨", 5, 80, 20)
    
    if mode == "DAILY":
        box_mode = st.radio("정렬", ["Vertical", "Horizontal"])
        rx, ry = st.slider("X", 0, 1080, 70), st.slider("Y", 0, 1920, 1150)
        rw, rh = st.slider("박스 너비", 100, 1080, 600), st.slider("박스 높이", 100, 1500, 650)
        box_alpha = st.slider("박스 투명도", 0, 255, 110)
        map_size, map_alpha = st.slider("지도 크기", 50, 400, 150), st.slider("지도 투명도", 0, 255, 255)

# --- [5. 렌더링] ---
if bg_files:
    try:
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        
        if mode == "DAILY":
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920))
            overlay = Image.new("RGBA", (1080, 1920), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            
            if show_box:
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
                # 지도 렌더링
                p_line = a.get('map', {}).get('summary_polyline')
                if p_line:
                    pts = polyline.decode(p_line); lats, lons = zip(*pts)
                    m_layer = Image.new("RGBA", (map_size, map_size), (0,0,0,0)); m_draw = ImageDraw.Draw(m_layer)
                    def trans(la, lo):
                        tx = 10 + (lo - min(lons)) / (max(lons) - min(lons) + 0.00001) * (map_size - 20)
                        ty = (map_size - 10) - (la - min(lats)) / (max(lats) - min(lats) + 0.00001) * (map_size - 20)
                        return tx, ty
                    m_draw.line([trans(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, map_alpha), width=4)
                    overlay.paste(m_layer, (rx + rw - map_size - 20, ry + 20), m_layer)
                # 텍스트
                items = [("distance", f"{v_dist} km"), ("time", t_val), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
                draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
                draw.text((rx+40, ry+30+t_sz+5), v_date, font=f_d, fill=sub_color)
                y_c = ry + t_sz + d_sz + 60
                for lab, val in items:
                    draw.text((rx+40, y_c), lab, font=f_l, fill="#AAAAAA")
                    draw.text((rx+40, y_c+l_sz+2), val, font=f_n, fill=sub_color); y_c += (n_sz + l_sz + 30)
            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            
        else: # WEEKLY
            canvas = Image.new("RGBA", (1080, 1080), (0,0,0,255)); n = len(bg_files)
            cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
            bh = 880 if show_box else 1080
            iw, ih = 1080 // cols, bh // rows
            for i, f in enumerate(bg_files):
                x, y = (i % cols) * iw, (i // cols) * ih
                cw, ch = (iw if (i+1)%cols != 0 else 1080-x), (ih if (i+cols) < n else bh-y)
                canvas.paste(ImageOps.fit(Image.open(f).convert("RGBA"), (cw, ch)), (x, y))
            if show_box:
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([0, 880, 1080, 1080], fill=(15,15,15,255))
                draw.text((40, 900), v_act_w, font=load_font(sel_font, 45), fill=m_color)
                w_items = [("dist", v_dist_w), ("pace", v_pace_w), ("bpm", v_hr_w)]
                for i, (lab, val) in enumerate(w_items):
                    draw.text((40+i*340, 970), lab, font=f_l, fill="#AAAAAA")
                    draw.text((40+i*340, 995), val, font=f_n, fill=sub_color)
            final = canvas.convert("RGB")

        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=90)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_result.jpg", use_container_width=True)
    except Exception as e:
        st.error(f"이미지 생성 중 오류가 발생했습니다: {e}")

st.sidebar.button("🔓 로그아웃", on_click=logout)import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 시스템 설정] ---
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
    f_path = f"font_{font_type}_{int(size)}.ttf"
    try:
        if not os.path.exists(f_path):
            r = requests.get(f_url, timeout=10)
            with open(f_path, "wb") as f: f.write(r.content)
        return ImageFont.truetype(f_path, int(size))
    except:
        return ImageFont.load_default()

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return rgb + (alpha,)

# --- [2. Strava 인증] ---
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
    except: st.error("인증 처리 중 오류가 발생했습니다.")

if not st.session_state['access_token']:
    st.title("🏃 Garmin Photo Dashboard")
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url)
    st.stop()

# --- [3. 데이터 로드] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
try:
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers, timeout=15)
    acts = act_res.json() if act_res.status_code == 200 else []
except:
    acts = []
    st.warning("활동 데이터를 불러오지 못했습니다.")

# --- [4. UI 구성] ---
col1, col2, col3 = st.columns([1, 2, 1], gap="medium")
COLOR_OPTIONS = {"Garmin Yellow": "#FFD700", "Pure White": "#FFFFFF", "Neon Orange": "#FF4500", "Electric Blue": "#00BFFF", "Soft Grey": "#AAAAAA"}

with col2:
    mode = st.radio("작업 모드", ["DAILY", "WEEKLY"], horizontal=True)
    if mode == "DAILY" and acts:
        sel_str = st.selectbox("기록 선택", [f"{a.get('start_date_local','')[:10]} - {a.get('name','')}" for a in acts])
        idx = [f"{x.get('start_date_local','')[:10]} - {x.get('name','')}" for x in acts].index(sel_str)
        a = acts[idx]
        d_km = a.get('distance', 0) / 1000
        m_sec = a.get('moving_time', 0)
        p_str = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
        h_val = str(int(a.get('average_heartrate', 0)))
    elif mode == "WEEKLY" and acts:
        w_acts = acts[:7]
        t_dist = sum([x.get('distance', 0) for x in w_acts]) / 1000
        t_time = sum([x.get('moving_time', 0) for x in w_acts])
        avg_p_str = f"{int((t_time/t_dist)//60)}'{int((t_time/t_dist)%60):02d}\"" if t_dist > 0 else "0'00\""
        t_hrs = [x.get('average_heartrate', 0) for x in w_acts if x.get('average_heartrate')]
        avg_hr = int(sum(t_hrs)/len(t_hrs)) if t_hrs else 0

with col1:
    st.header("📸 DATA")
    bg_files = st.file_uploader("사진 선택", type=['jpg','jpeg','png'], accept_multiple_files=True)
    if mode == "DAILY" and acts:
        v_act = st.text_input("활동명", a.get('name',''))
        v_date = st.text_input("날짜", a.get('start_date_local','')[:10])
        v_dist = st.text_input("거리(km)", f"{d_km:.2f}")
        v_pace = st.text_input("페이스(분/km)", p_str)
        v_hr = st.text_input("심박(bpm)", h_val)
    elif mode == "WEEKLY":
        v_act_w = st.text_input("주간 제목", "WEEKLY RECAP")
        v_dist_w = st.text_input("총 거리", f"{t_dist:.2f} km")
        v_pace_w = st.text_input("평균 페이스", avg_p_str)
        v_hr_w = st.text_input("평균 심박", f"{avg_hr} bpm")

with col3:
    st.header("🎨 DESIGN")
    show_box = st.checkbox("로그 박스 표시", value=True)
    sel_font = st.selectbox("폰트 선택", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    sel_m_color = st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()), index=0)
    sel_sub_color = st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)
    m_color, sub_color = COLOR_OPTIONS[sel_m_color], COLOR_OPTIONS[sel_sub_color]
    
    t_sz, d_sz, n_sz, l_sz = st.slider("활동명(90)", 10, 200, 90), st.slider("날짜(30)", 5, 100, 30), st.slider("숫자(60)", 10, 200, 60), st.slider("라벨", 5, 80, 20)
    
    if mode == "DAILY":
        box_mode = st.radio("정렬", ["Vertical", "Horizontal"])
        rx, ry = st.slider("X", 0, 1080, 70), st.slider("Y", 0, 1920, 1150)
        rw, rh = st.slider("박스 너비", 100, 1080, 600), st.slider("박스 높이", 100, 1500, 650)
        box_alpha = st.slider("박스 투명도", 0, 255, 110)
        map_size, map_alpha = st.slider("지도 크기", 50, 400, 150), st.slider("지도 투명도", 0, 255, 255)

# --- [5. 렌더링] ---
if bg_files:
    try:
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        
        if mode == "DAILY":
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920))
            overlay = Image.new("RGBA", (1080, 1920), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            
            if show_box:
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
                # 지도 렌더링
                p_line = a.get('map', {}).get('summary_polyline')
                if p_line:
                    pts = polyline.decode(p_line); lats, lons = zip(*pts)
                    m_layer = Image.new("RGBA", (map_size, map_size), (0,0,0,0)); m_draw = ImageDraw.Draw(m_layer)
                    def trans(la, lo):
                        tx = 10 + (lo - min(lons)) / (max(lons) - min(lons) + 0.00001) * (map_size - 20)
                        ty = (map_size - 10) - (la - min(lats)) / (max(lats) - min(lats) + 0.00001) * (map_size - 20)
                        return tx, ty
                    m_draw.line([trans(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, map_alpha), width=4)
                    overlay.paste(m_layer, (rx + rw - map_size - 20, ry + 20), m_layer)
                # 텍스트
                items = [("distance", f"{v_dist} km"), ("time", t_val), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
                draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
                draw.text((rx+40, ry+30+t_sz+5), v_date, font=f_d, fill=sub_color)
                y_c = ry + t_sz + d_sz + 60
                for lab, val in items:
                    draw.text((rx+40, y_c), lab, font=f_l, fill="#AAAAAA")
                    draw.text((rx+40, y_c+l_sz+2), val, font=f_n, fill=sub_color); y_c += (n_sz + l_sz + 30)
            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            
        else: # WEEKLY
            canvas = Image.new("RGBA", (1080, 1080), (0,0,0,255)); n = len(bg_files)
            cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
            bh = 880 if show_box else 1080
            iw, ih = 1080 // cols, bh // rows
            for i, f in enumerate(bg_files):
                x, y = (i % cols) * iw, (i // cols) * ih
                cw, ch = (iw if (i+1)%cols != 0 else 1080-x), (ih if (i+cols) < n else bh-y)
                canvas.paste(ImageOps.fit(Image.open(f).convert("RGBA"), (cw, ch)), (x, y))
            if show_box:
                draw = ImageDraw.Draw(canvas)
                draw.rectangle([0, 880, 1080, 1080], fill=(15,15,15,255))
                draw.text((40, 900), v_act_w, font=load_font(sel_font, 45), fill=m_color)
                w_items = [("dist", v_dist_w), ("pace", v_pace_w), ("bpm", v_hr_w)]
                for i, (lab, val) in enumerate(w_items):
                    draw.text((40+i*340, 970), lab, font=f_l, fill="#AAAAAA")
                    draw.text((40+i*340, 995), val, font=f_n, fill=sub_color)
            final = canvas.convert("RGB")

        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=90)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_result.jpg", use_container_width=True)
    except Exception as e:
        st.error(f"이미지 생성 중 오류가 발생했습니다: {e}")

st.sidebar.button("🔓 로그아웃", on_click=logout)
