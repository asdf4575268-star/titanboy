import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, requests, polyline, math, os
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# --- [1. 설정 및 유틸리티] ---
st.set_page_config(page_title="TITAN BOY", layout="wide")
plt.switch_backend('Agg') # GUI 에러 방지
CLIENT_ID, CLIENT_SECRET = '202274', '63f6a7007ebe6b405763fc3104e17bb53b468ad0'
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

# [누락된 함수 복구]
def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (int(alpha),)

@st.cache_resource
def load_font_cached(name, size):
    urls = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "KirangHaerang": "https://github.com/google/fonts/raw/main/ofl/kiranghaerang/KirangHaerang-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf"
    }
    path = f"font_{name}.ttf"
    try:
        if not os.path.exists(path):
            if name in urls:
                with open(path, "wb") as f: f.write(requests.get(urls[name]).content)
        return ImageFont.truetype(path, int(size))
    except: return ImageFont.load_default()

def draw_text(draw, pos, text, font, fill, shadow=True):
    if shadow: draw.text((pos[0]+2, pos[1]+2), text, font=font, fill=(0,0,0,220))
    draw.text(pos, text, font=font, fill=fill)

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
            ad = datetime.strptime(a['start_date_local'][:10], "%Y-%m-%d")
            if s_date <= ad <= e_date:
                idx = ad.weekday() if mode == "WEEKLY" else ad.day - 1
                d = a.get('distance', 0)/1000
                dists[idx] += d; tot_d += d; tot_t += a.get('moving_time', 0)
                if a.get('average_heartrate'): hr_s += a['average_heartrate']; hr_c += 1
        
        return {"dists": dists, "total_dist": f"{tot_d:.2f}", "time": f"{tot_t//3600:02d}:{(tot_t%3600)//60:02d}:{tot_t%60:02d}", 
                "pace": f"{int((tot_t/tot_d)//60)}'{int((tot_t/tot_d)%60):02d}\"" if tot_d else "0'00\"", 
                "hr": str(int(hr_s/hr_c)) if hr_c else "0", "range": range_str, "labels": [str(i+1) for i in range(days)] if mode=="MONTHLY" else None}
    except: return None

def create_chart(data, color, mode, labels):
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150); fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    if not labels: labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    ax.bar(np.arange(len(labels)), data, color=color, width=0.6)
    ax.set_xticks(np.arange(len(labels))); ax.set_xticklabels(labels, fontsize=10 if mode=="MONTHLY" else 14, color='white')
    ax.tick_params(left=False, labelleft=False, bottom=False); [ax.spines[s].set_visible(False) for s in ax.spines]
    buf = io.BytesIO(); plt.tight_layout(); plt.savefig(buf, format='png', transparent=True); plt.close(fig); return Image.open(buf)

def make_collage(files, w, h):
    if not files: return Image.new("RGBA", (w, h), (20,20,20,255))
    imgs = []
    for f in files:
        try: imgs.append(ImageOps.exif_transpose(Image.open(f)).convert("RGBA"))
        except: continue
    if not imgs: return Image.new("RGBA", (w, h), (20,20,20,255))
    if len(imgs) == 1: return ImageOps.fit(imgs[0], (w, h), Image.Resampling.LANCZOS)
    
    cols = math.ceil(math.sqrt(len(imgs))); rows = math.ceil(len(imgs)/cols)
    canvas = Image.new("RGBA", (w, h), (0,0,0,255))
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        n_cols = len(imgs)%cols if (r==rows-1 and len(imgs)%cols) else cols
        cw, ch = w//n_cols if (r==rows-1 and len(imgs)%cols) else w//cols, h//rows
        x, y = (i%cols)*cw if (r==rows-1 and len(imgs)%cols) else c*(w//cols), r*ch
        canvas.paste(ImageOps.fit(img, (cw, ch), Image.Resampling.LANCZOS), (x, y))
    return canvas

# --- [2. 메인 로직] ---
col_main, col_design = st.columns([1.6, 1], gap="medium")

# 인증
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

# UI 구성
with col_main:
    st.title("TITAN BOY")
    bg_files = st.file_uploader("📸 배경", type=['jpg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("🔘 로고", type=['jpg','png'])
    mode = st.radio("모드", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)
    
    v_act, v_date, v_dist, v_time, v_pace, v_hr, a, w_data, m_data = "RUNNING", "2026.02.16", "0.00", "00:00:00", "0'00\"", "0", None, None, None
    
    if not st.session_state.token:
        st.link_button("🚀 Strava Login", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    elif st.button("🔓 Logout", use_container_width=True):
        st.session_state.clear(); st.query_params.clear(); st.rerun()
    elif st.session_state.acts:
        if mode == "DAILY":
            acts_list = [f"{x['start_date_local'][:10]} - {x['name']}" for x in st.session_state.acts]
            sel = st.selectbox("활동", acts_list)
            a = st.session_state.acts[acts_list.index(sel)]
            v_act = a['name'].upper(); v_date = a['start_date_local'][:10].replace('-', '.')
            d = a.get('distance',0)/1000; t = a.get('moving_time',0)
            v_dist = f"{d:.2f}"; v_time = f"{t//3600:02d}:{(t%3600)//60:02d}:{t%60:02d}"
            v_pace = f"{int((t/d)//60)}'{int((t/d)%60):02d}\"" if d else "0'00\""
            v_hr = str(int(a.get('average_heartrate', 0)))
        else:
            dates = sorted(list(set([x['start_date_local'][:10 if mode=="WEEKLY" else 7] for x in st.session_state.acts])), reverse=True)
            if mode == "WEEKLY":
                weeks = sorted(list(set([(datetime.strptime(d, "%Y-%m-%d") - timedelta(days=datetime.strptime(d, "%Y-%m-%d").weekday())).strftime('%Y-%m-%d') for d in dates])), reverse=True)
                sel_w = st.selectbox("주차", weeks)
                w_data = get_stats(st.session_state.acts, "WEEKLY", sel_w)
            else:
                sel_m = st.selectbox("월", dates)
                m_data = get_stats(st.session_state.acts, "MONTHLY", f"{sel_m}-01")
                if m_data: v_act = datetime.strptime(f"{sel_m}-01", "%Y-%m-%d").strftime("%B").upper()
            
            d_obj = w_data if mode == "WEEKLY" else m_data
            if d_obj: v_date, v_dist, v_time, v_pace, v_hr = d_obj['range'], d_obj['total_dist'], d_obj['time'], d_obj['pace'], d_obj['hr']

with col_design:
    st.header("🎨 DESIGN")
    with st.expander("텍스트/스타일", expanded=True):
        v_act = st.text_input("활동명", v_act); v_date = st.text_input("날짜", v_date)
        cols = st.columns(2); v_dist = cols[0].text_input("거리", v_dist); v_time = cols[1].text_input("시간", v_time)
        cols = st.columns(2); v_pace = cols[0].text_input("페이스", v_pace); v_hr = cols[1].text_input("심박", v_hr)
        
        sw_vis = st.toggle("지도/그래프", True); sw_box = st.toggle("데이터박스", True); sw_shadow = st.toggle("그림자", True)
        b_thick = st.slider("테두리 두께", 0, 50, 0)
        
        C_MAP = {"Black":"#000000", "Yellow":"#FFD700", "White":"#FFFFFF", "Orange":"#FF4500", "Blue":"#00BFFF", "Grey":"#AAAAAA"}
        m_col = C_MAP[st.selectbox("메인색", list(C_MAP.keys()), 1)]; s_col = C_MAP[st.selectbox("서브색", list(C_MAP.keys()), 2)]
        orient = st.radio("방향", ["Vertical", "Horizontal"], horizontal=True)
        font_name = st.selectbox("폰트", ["BlackHanSans", "KirangHaerang", "Lacquer"])
        
    with st.expander("위치/크기"):
        rx = st.number_input("X", 0, 1080, 40 if orient=="Horizontal" else 80)
        ry = st.number_input("Y", 0, 1920, 150 if orient=="Horizontal" else 1200)
        rw = st.number_input("W", 100, 1080, 1000 if orient=="Horizontal" else 450)
        rh = st.number_input("H", 100, 1920, 350 if orient=="Horizontal" else 600)
        box_al = st.slider("박스투명도", 0, 255, 0); vis_sz = st.slider("시각화크기", 50, 1080, 180 if mode=="DAILY" else 950)

# 렌더링
with col_main:
    st.subheader("🖼️ PREVIEW")
    if (mode=="DAILY" and a) or (mode!="DAILY" and (w_data or m_data)):
        try:
            CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
            f_t = load_font_cached(font_name, 90)
            f_d = load_font_cached(font_name, 30)
            f_n = load_font_cached(font_name, 60)
            f_l = load_font_cached(font_name, 25)
            
            canvas = make_collage(bg_files, CW, CH)
            overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)

            if b_thick > 0: draw.rectangle([(0,0), (CW-1, CH-1)], outline=m_col, width=b_thick)

            if sw_box:
                draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0,0,0, box_al))
                items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
                
                if orient == "Vertical":
                    draw_text(draw, (rx+40, ry+30), v_act, f_t, m_col, sw_shadow)
                    draw_text(draw, (rx+40+draw.textlength(v_act, f_t)+30, ry+80), v_date, f_d, "#AAAAAA", sw_shadow)
                    yc = ry+165
                    for l, v in items:
                        draw_text(draw, (rx+40, yc), l.lower(), f_l, "#AAAAAA", sw_shadow)
                        draw_text(draw, (rx+40, yc+35), v.lower(), f_n, s_col, sw_shadow); yc+=105
                else:
                    draw_text(draw, (rx+(rw-draw.textlength(v_act,f_t))//2, ry+35), v_act, f_t, m_col, sw_shadow)
                    draw_text(draw, (rx+(rw-draw.textlength(v_date,f_d))//2, ry+135), v_date, f_d, "#AAAAAA", sw_shadow)
                    sw = rw//4
                    for i, (l, v) in enumerate(items):
                        cx = rx + i*sw + sw//2
                        draw_text(draw, (cx-draw.textlength(l.lower(),f_l)//2, ry+200), l.lower(), f_l, "#AAAAAA", sw_shadow)
                        draw_text(draw, (cx-draw.textlength(v.lower(),f_n)//2, ry+245), v.lower(), f_n, s_col, sw_shadow)

            if sw_vis:
                v_lyr = None
                p_pos = (0,0) # 기본 초기화
                
                if mode == "DAILY" and a.get('map', {}).get('summary_polyline'):
                    pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
                    v_lyr = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); md = ImageDraw.Draw(v_lyr)
                    
                    # [hex_to_rgba 사용]
                    def tr(la, lo): return 15+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-30), (vis_sz-15)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-30)
                    md.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_col, 240), width=6)
                    p_pos = (rx, max(5, ry-vis_sz-15)) if orient=="Vertical" else (rx+100, ry+10)
                elif mode != "DAILY":
                    d_obj = w_data if mode == "WEEKLY" else m_data
                    c_img = create_chart(d_obj['dists'], m_col, mode, d_obj.get('labels'))
                    v_lyr = c_img.resize((vis_sz, int(c_img.size[1]*(vis_sz/c_img.size[0]))), Image.Resampling.LANCZOS)
                    p_pos = ((CW-v_lyr.width)//2, CH-v_lyr.height-80)
                
                if v_lyr: overlay.paste(v_lyr, (int(p_pos[0]), int(p_pos[1])), v_lyr)

            if log_file:
                li = ImageOps.fit(Image.open(log_file).convert("RGBA"), (100, 100))
                overlay.paste(li, (CW-140, 40), li)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, width=300)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button(f"📥 DOWNLOAD", buf.getvalue(), f"{mode}.jpg", use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")
