import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# --- [1. 기본 설정 및 유틸리티] ---
API_CFG = {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'}
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"
st.set_page_config(page_title="TITAN BOY", layout="wide")

@st.cache_resource
def load_font(font_type, size):
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Regular.ttf",
        "KirangHaerang": "https://github.com/google/fonts/raw/main/ofl/kiranghaerang/KirangHaerang-Regular.ttf",
        "JollyLodger": "https://github.com/google/fonts/raw/main/ofl/jollylodger/JollyLodger-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf",
        "Orbit": "https://github.com/google/fonts/raw/main/ofl/orbit/Orbit-Regular.ttf"
    }
    try:
        r = requests.get(fonts.get(font_type, fonts["BlackHanSans"]), timeout=10)
        return ImageFont.truetype(io.BytesIO(r.content), int(size))
    except: return ImageFont.load_default()

def make_smart_collage(files, target_size):
    tw, th = target_size
    imgs = [ImageOps.exif_transpose(Image.open(f).convert("RGBA")) for f in files]
    if not imgs: return Image.new("RGBA", (tw, th), (30, 30, 30, 255))
    n = len(imgs)
    if n == 1: return ImageOps.fit(imgs[0], (tw, th))
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        # 마지막 줄 너비 자동 조정 (여백 방지)
        cur_cols = n % cols if (r == rows-1 and n % cols != 0) else cols
        x0, x1 = int((i%cols)*tw/cur_cols), int(((i%cols)+1)*tw/cur_cols)
        y0, y1 = int(r*th/rows), int((r+1)*th/rows)
        canvas.paste(ImageOps.fit(img, (x1-x0, y1-y0)), (x0, y0))
    return canvas

def create_bar_chart(data, color, labels):
    fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    ax.bar(range(len(labels)), data, color=color, width=0.6)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, color='white', fontsize=12)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='y', left=False, labelleft=False)
    buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); plt.close(fig)
    return Image.open(buf)

# --- [2. 데이터 연동] ---
if 'access_token' not in st.session_state: st.session_state.access_token = None
if "code" in st.query_params and not st.session_state.access_token:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": API_CFG["ID"], "client_secret": API_CFG["SECRET"], "code": st.query_params["code"], "grant_type": "authorization_code"}).json()
    st.session_state.access_token = res.get('access_token'); st.query_params.clear(); st.rerun()

acts = []
if st.session_state.access_token:
    r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers={'Authorization': f"Bearer {st.session_state.access_token}"})
    acts = r.json() if r.status_code == 200 else []

# --- [3. UI 레이아웃] ---
col_main, col_design = st.columns([1.6, 1], gap="medium")

with col_main:
    st.title("TITAN BOY")
    v = {"act": "RUNNING", "date": "2026-02-15", "dist": "0.00", "time": "00:00:00", "pace": "0'00\"", "hr": "0"}
    a_data, chart_info = None, None

    if not st.session_state.access_token:
        st.link_button("🚀 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={API_CFG['ID']}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        bg_files = st.file_uploader("📸 배경 사진", accept_multiple_files=True)
        log_file = st.file_uploader("🔘 로고")
        mode = st.radio("모드", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)
        
        if acts:
            if mode == "DAILY":
                sel = st.selectbox("🏃 활동 선택", [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts])
                a_data = acts[[f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts].index(sel)]
                d_km = a_data['distance']/1000; m_s = a_data['moving_time']
                v.update({"act": a_data['name'], "date": a_data['start_date_local'][:10], "dist": f"{d_km:.2f}", "time": f"{m_s//3600:02d}:{(m_s%3600)//60:02d}:{m_s%60:02d}", "pace": f"{int((m_s/d_km)//60)}'{int((m_s/d_km)%60):02d}\"", "hr": str(int(a_data.get('average_heartrate', 0)))})
            # (WEEKLY/MONTHLY 로직 생략 - 필요시 추가 가능)

with col_design:
    st.header("🎨 DESIGN")
    with st.expander("✍️ 텍스트 & 스타일", expanded=True):
        v["act"] = st.text_input("활동명", v["act"]); v["date"] = st.text_input("날짜", v["date"])
        v["dist"] = st.text_input("거리 km", v["dist"]); v["pace"] = st.text_input("페이스", v["pace"])
        v["hr"] = st.text_input("심박 bpm", v["hr"])
        show_vis = st.toggle("지도/그래프 표시", True); show_box = st.toggle("데이터 박스 표시", True)
        m_col = st.selectbox("포인트 컬러", ["#FFD700", "#FFFFFF", "#000000", "#FF4500"])
        sel_font = st.selectbox("폰트", ["BlackHanSans", "Sunflower", "KirangHaerang", "JollyLodger", "Lacquer", "Orbit"])
    
    with st.expander("📍 위치/크기 조절"):
        rx, ry = st.number_input("박스 X", 0, 1080, 70), st.number_input("박스 Y", 0, 1920, 1250)
        rw, rh = st.number_input("너비", 100, 1000, 450), st.number_input("높이", 100, 1000, 600)
        vis_sz = st.slider("지도/그래프 크기", 50, 1000, 180)

# --- [4. 렌더링] ---
with col_main:
    if st.session_state.access_token:
        CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
        f_t, f_d, f_n, f_l = [load_font(sel_font, s) for s in [90, 30, 60, 23]]
        canvas = make_smart_collage(bg_files, (CW, CH))
        overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)

        if show_box:
            draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0,0,0,110))
            draw.text((rx+40, ry+30), v["act"], font=f_t, fill=m_col)
            draw.text((rx+40, ry+140), v["date"], font=f_d, fill="#AAAAAA")
            items = [("distance", f"{v['dist']} km"), ("time", v["time"]), ("pace", v["pace"]), ("avg bpm", f"{v['hr']} bpm")]
            for i, (lab, val) in enumerate(items):
                draw.text((rx+40, ry+210+i*100), lab.lower(), font=f_l, fill="#AAAAAA")
                draw.text((rx+40, ry+245+i*100), val.lower(), font=f_n, fill="#FFFFFF")

        if show_vis:
            if mode == "DAILY" and a_data and a_data.get('map', {}).get('summary_polyline'):
                pts = polyline.decode(a_data['map']['summary_polyline'])
                lats, lons = zip(*pts)
                vis_l = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); d_m = ImageDraw.Draw(vis_l)
                def tr(la, lo): return 10+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-20), (vis_sz-10)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-20)
                d_m.line([tr(la, lo) for la, lo in pts], fill=m_col, width=5)
                overlay.paste(vis_l, (rx, ry-vis_sz-20), vis_l)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        st.image(final, width=350)
        buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
        st.download_button("📸 DOWNLOAD", buf.getvalue(), "titan_boy.jpg", use_container_width=True)
