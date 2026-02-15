import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# --- [1. 기본 설정] ---
API_CFG = {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'}
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"
st.set_page_config(page_title="TITAN BOY", layout="wide")

def logout():
    st.cache_data.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

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
        cur_cols = n % cols if (r == rows-1 and n % cols != 0) else cols
        x0, x1 = int((i%cols)*tw/cur_cols), int(((i%cols)+1)*tw/cur_cols)
        y0, y1 = int(r*th/rows), int((r+1)*th/rows)
        canvas.paste(ImageOps.fit(img, (x1-x0, y1-y0)), (x0, y0))
    return canvas

# --- [2. 통계 로직 복구] ---
def get_weekly_stats(acts, target_date_str):
    td = datetime.strptime(target_date_str, "%Y-%m-%d")
    start = td - timedelta(days=td.weekday())
    end = start + timedelta(days=6)
    dists = [0.0]*7; t_dist, t_time, h_s, h_c = 0.0, 0, 0, 0
    for a in acts:
        if a.get('type') == 'Run':
            ad = datetime.strptime(a['start_date_local'][:10], "%Y-%m-%d")
            if start <= ad <= end:
                d = a['distance']/1000; dists[ad.weekday()] += d
                t_dist += d; t_time += a['moving_time']
                if a.get('average_heartrate'): h_s += a['average_heartrate']; h_c += 1
    p_s = t_time/t_dist if t_dist > 0 else 0
    return {"dists": dists, "total_dist": f"{t_dist:.2f}", "total_time": f"{t_time//3600:02d}:{(t_time%3600)//60:02d}:{t_time%60:02d}", "avg_pace": f"{int(p_s//60)}'{int(p_s%60):02d}\"", "avg_hr": str(int(h_s/h_c)) if h_c > 0 else "0", "range": f"{start.strftime('%m.%d')} - {end.strftime('%m.%d')}"}

# --- [3. 데이터 연동 & 인증] ---
if 'access_token' not in st.session_state: st.session_state.access_token = None
qp = st.query_params
if "code" in qp and not st.session_state.access_token:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": API_CFG["ID"], "client_secret": API_CFG["SECRET"], "code": qp["code"], "grant_type": "authorization_code"}).json()
    st.session_state.access_token = res.get('access_token'); st.query_params.clear(); st.rerun()

acts = []
if st.session_state.access_token:
    r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers={'Authorization': f"Bearer {st.session_state.access_token}"})
    acts = r.json() if r.status_code == 200 else []

# --- [4. UI 구성] ---
col_main, col_design = st.columns([1.6, 1], gap="medium")

with col_main:
    st.title("TITAN BOY")
    v = {"act": "RUNNING", "date": "2026-02-15", "dist": "0.00", "time": "00:00:00", "pace": "0'00\"", "hr": "0"}
    a_sel, w_data = None, None

    if not st.session_state.access_token:
        st.link_button("🚀 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={API_CFG['ID']}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        st.button("🔓 로그아웃", on_click=logout)
        bg_files = st.file_uploader("📸 배경 사진", accept_multiple_files=True)
        log_file = st.file_uploader("🔘 로고")
        mode = st.radio("모드", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)
        
        if acts:
            if mode == "DAILY":
                sel = st.selectbox("🏃 활동 선택", [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts])
                a_sel = acts[[f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts].index(sel)]
                d_km = a_sel['distance']/1000; m_s = a_sel['moving_time']
                v.update({"act": a_sel['name'], "date": a_sel['start_date_local'][:10], "dist": f"{d_km:.2f}", "time": f"{m_s//3600:02d}:{(m_s%3600)//60:02d}:{m_s%60:02d}", "pace": f"{int((m_s/d_km)//60)}'{int((m_s/d_km)%60):02d}\"", "hr": str(int(a_sel.get('average_heartrate', 0)))})
            elif mode == "WEEKLY":
                weeks = sorted(list(set([(datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d") - timedelta(days=datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d").weekday())).strftime('%Y-%m-%d') for ac in acts])), reverse=True)
                sel_w = st.selectbox("📅 주차 선택", weeks)
                w_data = get_weekly_stats(acts, sel_w)
                wn = datetime.strptime(sel_w, "%Y-%m-%d").isocalendar()[1]
                v.update({"act": f"{wn}TH WEEK", "date": w_data['range'], "dist": w_data['total_dist'], "time": w_data['total_time'], "pace": w_data['avg_pace'], "hr": w_data['avg_hr']})

with col_design:
    st.header("🎨 DESIGN")
    v["act"] = st.text_input("활동명", v["act"]); v["date"] = st.text_input("날짜", v["date"])
    v["dist"] = st.text_input("거리 km", v["dist"]); v["pace"] = st.text_input("페이스", v["pace"])
    v["hr"] = st.text_input("심박 bpm", v["hr"])
    
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    show_vis = st.toggle("지도/그래프 표시", True)
    m_col = st.selectbox("포인트 컬러", ["#FFD700", "#FFFFFF", "#000000", "#FF4500"])
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Sunflower", "KirangHaerang", "JollyLodger", "Lacquer", "Orbit"])
    
    rx, ry = st.number_input("X", 0, 1080, 70), st.number_input("Y", 0, 1920, 1250)
    rw, rh = st.number_input("너비", 100, 1080, 450 if box_orient=="Vertical" else 1000), st.number_input("높이", 100, 1080, 600 if box_orient=="Vertical" else 350)
    vis_sz = st.slider("지도 크기", 50, 800, 200)

# --- [5. 렌더링] ---
with col_main:
    if st.session_state.access_token:
        CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
        f_t, f_d, f_n, f_l = [load_font(sel_font, s) for s in [90, 30, 60, 23]]
        canvas = make_smart_collage(bg_files, (CW, CH))
        overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)

        # 데이터 박스 렌더링
        draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0,0,0,110))
        if box_orient == "Vertical":
            draw.text((rx+40, ry+30), v["act"], font=f_t, fill=m_col)
            draw.text((rx+40, ry+135), v["date"], font=f_d, fill="#AAAAAA")
            items = [("distance", f"{v['dist']} km"), ("time", v["time"]), ("pace", v["pace"]), ("avg bpm", f"{v['hr']} bpm")]
            for i, (lab, val) in enumerate(items):
                draw.text((rx+40, ry+200+i*100), lab.lower(), font=f_l, fill="#AAAAAA")
                draw.text((rx+40, ry+235+i*100), val.lower(), font=f_n, fill="#FFFFFF")
        else:
            draw.text((rx+40, ry+30), v["act"], font=f_t, fill=m_col)
            draw.text((rx+40, ry+135), v["date"], font=f_d, fill="#AAAAAA")
            for i, (lab, val) in enumerate([("dist", f"{v['dist']} km"), ("time", v["time"]), ("pace", v["pace"]), ("bpm", f"{v['hr']} bpm")]):
                draw.text((rx+40+i*240, ry+200), lab.lower(), font=f_l, fill="#AAAAAA")
                draw.text((rx+40+i*240, ry+235), val.lower(), font=f_n, fill="#FFFFFF")

        if show_vis and mode == "DAILY" and a_sel and a_sel.get('map', {}).get('summary_polyline'):
            pts = polyline.decode(a_sel['map']['summary_polyline']); lats, lons = zip(*pts)
            vis_l = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); d_m = ImageDraw.Draw(vis_l)
            def tr(la, lo): return 10+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-20), (vis_sz-10)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-20)
            d_m.line([tr(la, lo) for la, lo in pts], fill=m_col, width=5)
            overlay.paste(vis_l, (rx, ry-vis_sz-20), vis_l)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        st.image(final, width=350)
