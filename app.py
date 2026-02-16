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
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (rgb[0], rgb[1], rgb[2], int(alpha))

@st.cache_resource
def load_font_cached(name, size):
    urls = {
        "KirangHaerang": "https://github.com/google/fonts/raw/main/ofl/kiranghaerang/KirangHaerang-Regular.ttf",
        "JollyLodger": "https://github.com/google/fonts/raw/main/ofl/jollylodger/JollyLodger-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf",
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf"
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

# --- [2. 통계 계산 로직 (9시간 보정 포함)] ---
def get_stats(acts, mode, target):
    try:
        t_date = datetime.strptime(target, "%Y-%m-%d")
        if mode == "WEEKLY":
            s_date = t_date - timedelta(days=t_date.weekday())
            e_date = s_date + timedelta(days=6)
            days = 7; range_str = f"{s_date.strftime('%m.%d')} - {e_date.strftime('%m.%d')}"
        else: # MONTHLY
            s_date = t_date.replace(day=1)
            e_date = (s_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            days = e_date.day; range_str = s_date.strftime('%Y.%m')
        
        dists = [0.0] * days; tot_d, tot_t, hr_s, hr_c = 0, 0, 0, 0
        
        for a in acts:
            if a.get('type') != 'Run': continue
            # 9시간 시차 보정
            raw_date = a['start_date_local'].replace('Z', '')
            ad = datetime.fromisoformat(raw_date) + timedelta(hours=9)
            ad_only_date = ad.replace(hour=0, minute=0, second=0, microsecond=0)
            
            if s_date <= ad_only_date <= e_date:
                idx = ad.weekday() if mode == "WEEKLY" else ad.day - 1
                d = a.get('distance', 0)/1000
                dists[idx] += d; tot_d += d; tot_t += a.get('moving_time', 0)
                if a.get('average_heartrate'): hr_s += a['average_heartrate']; hr_c += 1
        
        return {"dists": dists, "total_dist": f"{tot_d:.2f}", "time": f"{tot_t//3600:02d}:{(tot_t%3600)//60:02d}:{tot_t%60:02d}", 
                "pace": f"{int((tot_t/tot_d)//60)}'{int((tot_t/tot_d)%60):02d}\"" if tot_d else "0'00\"", 
                "hr": str(int(hr_s/hr_c)) if hr_c else "0", "range": range_str, "labels": [str(i+1) for i in range(days)] if mode=="MONTHLY" else None}
    except: return None

# --- [3. 세션 및 인증] ---
if 'token' not in st.session_state: st.session_state.token = None
if 'acts' not in st.session_state: st.session_state.acts = []
qp = st.query_params

if "token" in qp: st.session_state.token = qp["token"]
elif "code" in qp and not st.session_state.token:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": qp["code"], "grant_type": "authorization_code"}).json()
    if 'access_token' in res:
        st.session_state.token = res['access_token']; st.query_params.clear(); st.query_params["token"] = res['access_token']; st.rerun()

if st.session_state.token and not st.session_state.acts:
    st.session_state.acts = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=100", headers={'Authorization': f"Bearer {st.session_state.token}"}).json()

# --- [4. 레이아웃 구성] ---
col_main, col_style = st.columns([1.5, 1], gap="medium")

with col_main:
    st.title("TITAN BOY")
    bg_files = st.file_uploader("📸 배경 사진 업로드", type=['jpg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("🔘 로고 업로드", type=['jpg','png'])
    
    v_act, v_date, v_dist, v_time, v_pace, v_hr, a, w_data, m_data = "RUNNING", "2026.02.16 12:00 PM", "0.00", "00:00:00", "0'00\"", "0", None, None, None
    
    if not st.session_state.token:
        st.link_button("🚀 Strava Login", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        mode = st.radio("모드", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)
        if st.session_state.acts:
            if mode == "DAILY":
                acts_list = [f"{(datetime.fromisoformat(x['start_date_local'].replace('Z',''))+timedelta(hours=9)).strftime('%Y.%m.%d')} - {x['name']}" for x in st.session_state.acts]
                sel = st.selectbox("활동 선택", acts_list)
                a = st.session_state.acts[acts_list.index(sel)]
                dt_obj = datetime.fromisoformat(a['start_date_local'].replace('Z','')) + timedelta(hours=9)
                v_act, v_date = a['name'].upper(), dt_obj.strftime("%Y.%m.%d %I:%M %p")
                d, t = a.get('distance',0)/1000, a.get('moving_time',0)
                v_dist, v_time = f"{d:.2f}", f"{t//3600:02d}:{(t%3600)//60:02d}:{t%60:02d}"
                v_pace = f"{int((t/d)//60)}'{int((t/d)%60):02d}\"" if d > 0 else "0'00\""
                v_hr = str(int(a.get('average_heartrate', 0)))
            else:
                # 9시간 보정된 날짜 리스트 생성
                dates = sorted(list(set([(datetime.fromisoformat(x['start_date_local'].replace('Z',''))+timedelta(hours=9)).strftime('%Y-%m-%d') for x in st.session_state.acts])), reverse=True)
                if mode == "WEEKLY":
                    weeks = sorted(list(set([(datetime.strptime(d, "%Y-%m-%d") - timedelta(days=datetime.strptime(d, "%Y-%m-%d").weekday())).strftime('%Y-%m-%d') for d in dates])), reverse=True)
                    sel_w = st.selectbox("주차 선택", weeks)
                    w_data = get_stats(st.session_state.acts, "WEEKLY", sel_w)
                else:
                    months = sorted(list(set([d[:7] for d in dates])), reverse=True)
                    sel_m = st.selectbox("월 선택", months)
                    m_data = get_stats(st.session_state.acts, "MONTHLY", f"{sel_m}-01")
                
                d_obj = w_data if mode == "WEEKLY" else m_data
                if d_obj:
                    v_date, v_dist, v_time, v_pace, v_hr = d_obj['range'], d_obj['total_dist'], d_obj['time'], d_obj['pace'], d_obj['hr']
                    if mode == "MONTHLY": v_act = datetime.strptime(f"{sel_m}-01", "%Y-%m-%d").strftime("%B").upper()

with st.sidebar:
    st.header("⚙️ SYSTEM")
    if st.button("🔓 로그아웃"): st.session_state.clear(); st.query_params.clear(); st.rerun()
    with st.expander("📝 OCR / 수기 입력 (비상용)"):
        v_act = st.text_input("활동명", v_act); v_date = st.text_input("날짜/시간", v_date)
        v_dist = st.text_input("거리 km", v_dist); v_time = st.text_input("시간", v_time)
        v_pace = st.text_input("페이스", v_pace); v_hr = st.text_input("심박 bpm", v_hr)

with col_style:
    st.header("🎨 STYLE")
    with st.container(border=True):
        f_name = st.selectbox("폰트", ["KirangHaerang", "JollyLodger", "Lacquer", "BlackHanSans"])
        c_cols = st.columns(2)
        C_MAP = {"Yellow":"#FFD700", "White":"#FFFFFF", "Black":"#000000", "Orange":"#FF4500", "Blue":"#00BFFF"}
        m_col = C_MAP[c_cols[0].selectbox("메인색", list(C_MAP.keys()), 0)]
        s_col = C_MAP[c_cols[1].selectbox("서브색", list(C_MAP.keys()), 1)]
    
    with st.container(border=True):
        orient = st.radio("방향", ["Vertical", "Horizontal"], horizontal=True)
        t_cols = st.columns(2)
        sw_vis = t_cols[0].toggle("지도/그래프", True); sw_box = t_cols[1].toggle("배경 박스", True)
        sw_shadow = t_cols[0].toggle("그림자", True); b_thick = st.slider("테두리 두께", 0, 50, 0)
        box_al = st.slider("박스 투명도", 0, 255, 0)

    with st.expander("📍 위치/크기 조절"):
        rx = st.number_input("X", 0, 1080, 80); ry = st.number_input("Y", 0, 1920, 1200)
        rw = st.number_input("W", 100, 1080, 450 if orient=="Vertical" else 1000)
        rh = st.number_input("H", 100, 1920, 600 if orient=="Vertical" else 350)
        vis_sz = st.slider("시각화 크기", 50, 1080, 200)

# --- [5. 렌더링 및 출력] ---
with col_main:
    st.divider()
    if bg_files:
        try:
            CW, CH = (1080, 1920) if mode=="DAILY" else (1080, 1350)
            f_t, f_d, f_n, f_l = load_font_cached(f_name, 90), load_font_cached(f_name, 30), load_font_cached(f_name, 60), load_font_cached(f_name, 25)
            
            # 콜라주 배경
            imgs = [ImageOps.exif_transpose(Image.open(f)).convert("RGBA") for f in bg_files]
            if len(imgs) == 1: canvas = ImageOps.fit(imgs[0], (CW, CH))
            else:
                cols = math.ceil(math.sqrt(len(imgs))); rows = math.ceil(len(imgs)/cols)
                canvas = Image.new("RGBA", (CW, CH))
                for i, img in enumerate(imgs):
                    r, c = divmod(i, cols)
                    canvas.paste(ImageOps.fit(img, (CW//cols, CH//rows)), (c*(CW//cols), r*(CH//rows)))
            
            overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            if b_thick > 0: draw.rectangle([(0,0), (CW-1, CH-1)], outline=m_col, width=b_thick)

            if sw_box:
                draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0,0,0, box_al))
                items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
                if orient == "Vertical":
                    draw_text(draw, (rx+40, ry+30), v_act, f_t, m_col, sw_shadow)
                    draw_text(draw, (rx+44, ry+130), v_date, f_d, "#AAAAAA", sw_shadow)
                    yc = ry+210
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

            if sw_vis:
                if mode == "DAILY" and a.get('map', {}).get('summary_polyline'):
                    pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
                    v_lyr = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); md = ImageDraw.Draw(v_lyr)
                    def tr(la, lo): return 10+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-20), (vis_sz-10)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-20)
                    md.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_col, 220), width=5)
                    overlay.paste(v_lyr, (int(rx), int(ry-vis_sz-20 if orient=="Vertical" else ry+20)), v_lyr)
                elif mode != "DAILY":
                    d_obj = w_data if mode == "WEEKLY" else m_data
                    if d_obj:
                        fig, ax = plt.subplots(figsize=(6, 3)); fig.patch.set_alpha(0); ax.patch.set_alpha(0)
                        ax.bar(range(len(d_obj['dists'])), d_obj['dists'], color=m_col)
                        ax.axis('off'); buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); plt.close()
                        c_img = Image.open(buf).convert("RGBA")
                        c_img = c_img.resize((vis_sz*2, vis_sz), Image.Resampling.LANCZOS)
                        overlay.paste(c_img, (int((CW-c_img.width)//2), int(ry-vis_sz-20)), c_img)

            if log_file:
                li = ImageOps.fit(Image.open(log_file).convert("RGBA"), (120, 120))
                overlay.paste(li, (CW-160, 40), li)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, width=450)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 사진 저장", buf.getvalue(), "titan_output.jpg", use_container_width=True)
        except Exception as e: st.error(f"Render Error: {e}")
