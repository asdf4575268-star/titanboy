import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math

# --- [1. 기본 설정 및 초기화] ---
CLIENT_ID = '202275'
CLIENT_SECRET = '969201cab488e4eaf1398b106de1d4e520dc564c'
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

def logout_and_clear():
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()

if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# --- [2. 인증 로직] ---
query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": query_params["code"], "grant_type": "authorization_code"
        }, timeout=15)
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            st.query_params.clear()
            st.rerun()
    except: pass

# --- [3. 유틸리티 함수] ---
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
    if not os.path.exists(f_path):
        r = requests.get(f_url); open(f_path, "wb").write(r.content)
    return ImageFont.truetype(f_path, int(size))

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return rgb + (alpha,)

# --- [4. 데이터 로드 (Strava)] ---
acts = []
if st.session_state['access_token']:
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
    try:
        act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers, timeout=15)
        if act_res.status_code == 200: acts = act_res.json()
    except: pass

# --- [5. UI 레이아웃] ---
col1, col2, col3 = st.columns([1.2, 2, 1], gap="medium")
COLOR_OPTIONS = {"Garmin Yellow": "#FFD700", "Pure White": "#FFFFFF", "Neon Orange": "#FF4500", "Electric Blue": "#00BFFF", "Soft Grey": "#AAAAAA"}

with col2:
    m_col, l_col = st.columns([3, 1])
    with m_col: mode = st.radio("모드", ["DAILY", "WEEKLY"], horizontal=True, label_visibility="collapsed")
    with l_col: 
        if st.session_state['access_token']:
            st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)
        else:
            auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
                        f"&response_type=code&redirect_uri={ACTUAL_URL}"
                        f"&scope=read,activity:read_all&approval_prompt=force")
            st.link_button("🚀 Strava 연동", auth_url, use_container_width=True)

    v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", "2026-02-14", "0.00", "00:00:00", "0'00\"", "0"
    a = None

    if mode == "DAILY" and acts:
        act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
        sel_str = st.selectbox("기록 선택 (Strava)", act_options)
        a = acts[act_options.index(sel_str)]
        d_km = a.get('distance', 0)/1000
        m_sec = a.get('moving_time', 0)
        v_act, v_date = a['name'], a['start_date_local'][:10]
        v_dist, v_time = f"{d_km:.2f}", f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}"
        v_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
        v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
    elif mode == "WEEKLY" and acts:
        st.info("업로드한 사진 개수에 따라 콜라주가 자동으로 생성됩니다.")

with col1:
    st.header("📸 DATA INPUT")
    bg_files = st.file_uploader("사진 업로드 (Weekly는 여러 장)", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("원형 로고", type=['jpg','jpeg','png'])
    
    st.divider()
    v_act = st.text_input("활동명", v_act)
    v_date = st.text_input("날짜/기간", v_date)
    v_dist = st.text_input("거리(km)", v_dist)
    v_time = st.text_input("시간", v_time)
    v_pace = st.text_input("페이스(분/km)", v_pace)
    v_hr = st.text_input("심박(bpm)", v_hr)

with col3:
    st.header("🎨 DESIGN")
    insta_mode = st.selectbox("캔버스 비율", ["1:1 (Square)", "4:5 (Portrait)"])
    show_box = st.checkbox("로그 박스 표시", value=True)
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color = COLOR_OPTIONS[st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()))]
    sub_color = COLOR_OPTIONS[st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)]
    
    # [활동명 90, 날짜 30, 숫자 60 고정]
    t_sz, d_sz, n_sz, l_sz = 90, 30, 60, 22
    
    # 인스타 캔버스 크기 결정
    CW, CH = (1080, 1080) if insta_mode == "1:1 (Square)" else (1080, 1350)
    
    d_rx, d_ry = (70, CH - 330) if box_orient == "Horizontal" else (70, CH - 670)
    rx = st.number_input("X 위치", 0, CW, d_rx)
    ry = st.number_input("Y 위치", 0, CH, d_ry)
    rw = st.number_input("박스 너비", 100, CW, 940 if box_orient == "Horizontal" else 480)
    rh = st.number_input("박스 높이", 100, CH, 260 if box_orient == "Horizontal" else 600)
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    map_size = st.slider("지도 크기", 50, CW//2, 100)

# --- [6. 렌더링 엔진] ---
if bg_files:
    try:
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        
        # 1. 캔버스 생성 (여백 없이 꽉 차게)
        canvas = Image.new("RGBA", (CW, CH), (0,0,0,255))
        
        if mode == "DAILY":
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            img = ImageOps.fit(img.convert("RGBA"), (CW, CH))
            canvas.paste(img, (0,0))
        else:
            # WEEKLY 콜라주 (여백 없이 자동 분할)
            num_pics = len(bg_files)
            if num_pics == 1:
                img = ImageOps.fit(ImageOps.exif_transpose(Image.open(bg_files[0])), (CW, CH))
                canvas.paste(img, (0,0))
            else:
                cols = 2 if num_pics > 1 else 1
                rows = math.ceil(num_pics / cols)
                w_unit, h_unit = CW // cols, CH // rows
                for i, f in enumerate(bg_files):
                    img = ImageOps.fit(ImageOps.exif_transpose(Image.open(f)), (w_unit, h_unit))
                    canvas.paste(img, ((i % cols) * w_unit, (i // cols) * h_unit))

        overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
        
        if show_box:
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
            items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
            
            # 지도 렌더링
            if mode == "DAILY" and a and a.get('map', {}).get('summary_polyline'):
                pts = polyline.decode(a['map']['summary_polyline'])
                lats, lons = zip(*pts)
                m_layer = Image.new("RGBA", (map_size, map_size), (0,0,0,0)); m_draw = ImageDraw.Draw(m_layer)
                def trans(la, lo):
                    tx = 10 + (lo - min(lons)) / (max(lons) - min(lons) + 1e-7) * (map_size - 20)
                    ty = (map_size - 10) - (la - min(lats)) / (max(lats) - min(lats) + 1e-7) * (map_size - 20)
                    return tx, ty
                m_draw.line([trans(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, 255), width=4)
                overlay.paste(m_layer, (rx + (30 if box_orient=="Horizontal" else rw - map_size - 20), ry + 20), m_layer)

            # 텍스트 배치
            if box_orient == "Vertical":
                draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
                draw.text((rx+40, ry+30+t_sz+10), v_date, font=f_d, fill="#AAAAAA")
                y_c = ry + t_sz + d_sz + 90
                for lab, val in items:
                    draw.text((rx+40, y_c), lab, font=f_l, fill="#AAAAAA")
                    draw.text((rx+40, y_c+l_sz+5), val, font=f_n, fill=sub_color); y_c += (n_sz + l_sz + 35)
            else:
                title_w = draw.textlength(v_act, font=f_t)
                draw.text((rx+(rw//2)-(title_w//2), ry+25), v_act, font=f_t, fill=m_color)
                date_w = draw.textlength(v_date, font=f_d)
                draw.text((rx+(rw//2)-(date_w//2), ry+25+t_sz+5), v_date, font=f_d, fill="#AAAAAA")
                sec_w = (rw - 80) // 4
                for i, (lab, val) in enumerate(items):
                    ix = rx + 40 + (i * sec_w)
                    draw.text((ix, ry+t_sz+d_sz+50), lab, font=f_l, fill="#AAAAAA")
                    draw.text((ix, ry+t_sz+d_sz+50+l_sz+5), val, font=f_n, fill=sub_color)

            if log_file:
                l_sz_img = 100 if box_orient == "Vertical" else 80
                l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (l_sz_img, l_sz_img))
                mask = Image.new('L', (l_sz_img, l_sz_img), 0); ImageDraw.Draw(mask).ellipse((0, 0, l_sz_img, l_sz_img), fill=255); l_img.putalpha(mask)
                overlay.paste(l_img, (rx + rw - l_sz_img - 20, ry + (rh - l_sz_img - 20 if box_orient=="Vertical" else 25)), l_img)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "insta_result.jpg", use_container_width=True)
                
    except Exception as e:
        st.error(f"Error: {e}")
