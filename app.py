import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, requests, polyline, math, os
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# --- [1. 기본 설정 및 유틸리티] ---
st.set_page_config(page_title="TITAN BOY", layout="wide")
plt.switch_backend('Agg')
CLIENT_ID, CLIENT_SECRET = '202274', '63f6a7007ebe6b405763fc3104e17bb53b468ad0'
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    # RGB 값 추출
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    # 반드시 (R, G, B, A) 4개의 요소를 가진 튜플 반환
    return (rgb[0], rgb[1], rgb[2], int(alpha))

@st.cache_resource
def load_font_cached(name, size):
    urls = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "KirangHaerang": "https://github.com/google/fonts/raw/main/ofl/kiranghaerang/KirangHaerang-Regular.ttf",
        "JollyLodger": "https://github.com/google/fonts/raw/main/ofl/jollylodger/JollyLodger-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf"
    }
    path = f"font_{name}.ttf"
    if not os.path.exists(path) and name in urls:
        try:
            with open(path, "wb") as f: f.write(requests.get(urls[name]).content)
        except: pass
    try: return ImageFont.truetype(path, int(size))
    except: return ImageFont.load_default()

def draw_text(draw, pos, text, font, fill, shadow=True):
    if shadow: draw.text((pos[0]+2, pos[1]+2), text, font=font, fill=(0,0,0,220))
    draw.text(pos, text, font=font, fill=fill)

# --- [2. 데이터 수집 및 세션] ---
if 'token' not in st.session_state: st.session_state.token = None
if 'acts' not in st.session_state: st.session_state.acts = []
qp = st.query_params

if "token" in qp: st.session_state.token = qp["token"]
elif "code" in qp and not st.session_state.token:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": qp["code"], "grant_type": "authorization_code"}).json()
    if 'access_token' in res:
        st.session_state.token = res['access_token']; st.query_params.clear(); st.query_params["token"] = res['access_token']; st.rerun()

if st.session_state.token and not st.session_state.acts:
    st.session_state.acts = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers={'Authorization': f"Bearer {st.session_state.token}"}).json()

# --- [3. 레이아웃: 메인 & 스타일] ---
col_main, col_style = st.columns([1.5, 1], gap="medium")

with col_main:
    st.title("TITAN BOY")
    bg_files = st.file_uploader("📸 배경 사진 (여러 장 가능)", type=['jpg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("🔘 로고 업로드", type=['jpg','png'])
    
    v_act, v_date, v_dist, v_time, v_pace, v_hr, a = "RUNNING", "2026.02.16 12:00 PM", "0.00", "00:00:00", "0'00\"", "0", None
    
    if not st.session_state.token:
        st.link_button("🚀 Strava 연동하기", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)
        if st.session_state.acts and mode == "DAILY":
            acts_list = [f"{x['start_date_local'][:10]} - {x['name']}" for x in st.session_state.acts]
            sel = st.selectbox("활동 선택", acts_list)
            a = st.session_state.acts[acts_list.index(sel)]
            v_act = a['name'].upper()
            # 시간 파싱 (AM/PM 포함)
            dt_obj = datetime.strptime(a['start_date_local'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=9) # KST
            v_date = dt_obj.strftime("%Y.%m.%d %I:%M %p")
            d, t = a.get('distance',0)/1000, a.get('moving_time',0)
            v_dist, v_time = f"{d:.2f}", f"{t//3600:02d}:{(t%3600)//60:02d}:{t%60:02d}"
            v_pace = f"{int((t/d)//60)}'{int((t/d)%60):02d}\"" if d > 0 else "0'00\""
            v_hr = str(int(a.get('average_heartrate', 0)))

# --- [4. 오른쪽 사이드바: 수기 입력 (비상용)] ---
with st.sidebar:
    st.header("⚙️ SYSTEM")
    if st.button("🔓 로그아웃", use_container_width=True):
        st.session_state.clear(); st.query_params.clear(); st.rerun()
    
    with st.expander("📝 OCR / 수기 수정 (비상용)"):
        v_act = st.text_input("활동명 커스텀", v_act)
        v_date = st.text_input("날짜/시간 커스텀", v_date)
        v_dist = st.text_input("거리 km", v_dist)
        v_time = st.text_input("시간", v_time)
        v_pace = st.text_input("페이스", v_pace)
        v_hr = st.text_input("심박 bpm", v_hr)

# --- [5. 오른쪽 디자인 통합 창] ---
with col_style:
    st.header("🎨 STYLE")
    
    with st.container(border=True):
        st.subheader("폰트 및 컬러")
        f_name = st.selectbox("폰트 선택", ["KirangHaerang", "JollyLodger", "Lacquer", "BlackHanSans"])
        C_MAP = {"Yellow":"#FFD700", "White":"#FFFFFF", "Black":"#000000", "Orange":"#FF4500", "Blue":"#00BFFF"}
        col1, col2 = st.columns(2)
        m_col = C_MAP[col1.selectbox("포인트 컬러", list(C_MAP.keys()), 0)]
        s_col = C_MAP[col2.selectbox("서브 컬러", list(C_MAP.keys()), 1)]
    
    with st.container(border=True):
        st.subheader("박스 설정")
        orient = st.radio("정렬 방향", ["Vertical", "Horizontal"], horizontal=True)
        col1, col2 = st.columns(2)
        sw_vis = col1.toggle("지도/그래프", True)
        sw_box = col2.toggle("배경 박스", True)
        sw_shadow = col1.toggle("글자 그림자", True)
        b_thick = st.slider("테두리 두께", 0, 50, 0)
        box_al = st.slider("박스 투명도", 0, 255, 0)

    with st.expander("📍 세부 위치 조절"):
        rx = st.number_input("박스 X", 0, 1080, 80)
        ry = st.number_input("박스 Y", 0, 1920, 1200)
        rw = st.number_input("박스 가로", 100, 1080, 450 if orient=="Vertical" else 1000)
        rh = st.number_input("박스 세로", 100, 1920, 600 if orient=="Vertical" else 350)
        vis_sz = st.slider("시각화 크기", 50, 1080, 200)

# --- [6. 미리보기 렌더링 (메인 하단)] ---
with col_main:
    st.divider()
    if bg_files:
        try:
            CW, CH = (1080, 1920) if (mode=="DAILY" if 'mode' in locals() else True) else (1080, 1350)
            # 글자 크기 가이드: 활동명 90, 날짜 30, 숫자 60
            f_t = load_font_cached(f_name, 90)
            f_d = load_font_cached(f_name, 30)
            f_n = load_font_cached(f_name, 60)
            f_l = load_font_cached(f_name, 25)

            # 콜라주 생성
            from PIL import ImageFilter
            imgs = [ImageOps.exif_transpose(Image.open(f)).convert("RGBA") for f in bg_files]
            if len(imgs) == 1: canvas = ImageOps.fit(imgs[0], (CW, CH))
            else:
                cols = math.ceil(math.sqrt(len(imgs))); rows = math.ceil(len(imgs)/cols)
                canvas = Image.new("RGBA", (CW, CH))
                for i, img in enumerate(imgs):
                    r, c = divmod(i, cols)
                    canvas.paste(ImageOps.fit(img, (CW//cols, CH//rows)), (c*(CW//cols), r*(CH//rows)))
            
            overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            
            # 테두리
            if b_thick > 0: draw.rectangle([(0,0), (CW-1, CH-1)], outline=m_col, width=b_thick)

            # 데이터 박스
            if sw_box:
                draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0,0,0, box_al))
                # 소문자 단위 설정 (km, bpm)
                items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
                
                if orient == "Vertical":
                    draw_text(draw, (rx+40, ry+30), v_act, f_t, m_col, sw_shadow)
                    draw_text(draw, (rx+44, ry+125), v_date, f_d, "#AAAAAA", sw_shadow)
                    yc = ry+200
                    for l, v in items:
                        draw_text(draw, (rx+40, yc), l.lower(), f_l, "#AAAAAA", sw_shadow)
                        draw_text(draw, (rx+40, yc+35), v.lower(), f_n, s_col, sw_shadow); yc+=110
                else:
                    draw_text(draw, (rx+(rw-draw.textlength(v_act,f_t))//2, ry+35), v_act, f_t, m_col, sw_shadow)
                    draw_text(draw, (rx+(rw-draw.textlength(v_date,f_d))//2, ry+135), v_date, f_d, "#AAAAAA", sw_shadow)
                    sw = rw//4
                    for i, (l, v) in enumerate(items):
                        cx = rx + i*sw + sw//2
                        draw_text(draw, (cx-draw.textlength(l.lower(),f_l)//2, ry+210), l.lower(), f_l, "#AAAAAA", sw_shadow)
                        draw_text(draw, (cx-draw.textlength(v.lower(),f_n)//2, ry+255), v.lower(), f_n, s_col, sw_shadow)

            # 지도 시각화
            if sw_vis and a and a.get('map', {}).get('summary_polyline'):
                pts = polyline.decode(a['map']['summary_polyline'])
                lats, lons = zip(*pts)
                v_lyr = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0))
                md = ImageDraw.Draw(v_lyr)
    
            def tr(la, lo): 
                return (10 + (lo - min(lons)) / (max(lons) - min(lons) + 1e-5) * (vis_sz - 20), 
                (vis_sz - 10) - (la - min(lats)) / (max(lats) - min(lats) + 1e-5) * (vis_sz - 20))

            if log_file:
                li = ImageOps.fit(Image.open(log_file).convert("RGBA"), (120, 120))
                overlay.paste(li, (CW-160, 40), li)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, caption="PREVIEW (300px)", width=450)
            
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 사진 저장하기", buf.getvalue(), "titan_run.jpg", use_container_width=True)
        except Exception as e: st.error(f"렌더링 에러: {e}")
    else:
        st.info("💡 배경 사진을 업로드하면 미리보기가 생성됩니다.")

