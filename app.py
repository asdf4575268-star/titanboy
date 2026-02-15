import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# --- [1. 설정 및 API] ---
CLIENT_ID = '202275'
CLIENT_SECRET = '969201cab488e4eaf1398b106de1d4e520dc564c'
REDIRECT_URI = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

st.set_page_config(page_title="TITAN BOY", layout="wide")

# --- [2. 핵심 유틸리티 함수] ---
def logout():
    st.cache_data.clear(); st.cache_resource.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

def hex_to_rgba(hex_code, alpha):
    h = hex_code.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

@st.cache_resource
def load_font(name, size):
    urls = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Regular.ttf",
        "KirangHaerang": "https://github.com/google/fonts/raw/main/ofl/kiranghaerang/KirangHaerang-Regular.ttf",
        "JollyLodger": "https://github.com/google/fonts/raw/main/ofl/jollylodger/JollyLodger-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf",
        "Orbit": "https://github.com/google/fonts/raw/main/ofl/orbit/Orbit-Regular.ttf",
        "IndieFlower": "https://github.com/google/fonts/raw/main/ofl/indieflower/IndieFlower-Regular.ttf"
    }
    try:
        path = f"font_{name}_{size}.ttf"
        if not os.path.exists(path):
            r = requests.get(urls.get(name, urls["BlackHanSans"]))
            with open(path, "wb") as f: f.write(r.content)
        return ImageFont.truetype(path, int(size))
    except: return ImageFont.load_default()

def draw_text(draw, pos, text, font, color, shadow=True):
    if shadow: draw.text((pos[0]+3, pos[1]+3), text, font=font, fill=(0,0,0,180))
    draw.text(pos, text, font=font, fill=color)

def get_period_stats(activities, target_date, mode):
    # mode: 'WEEKLY' or 'MONTHLY'
    try:
        td = datetime.strptime(target_date, "%Y-%m-%d")
        if mode == "WEEKLY":
            start = td - timedelta(days=td.weekday())
            end = start + timedelta(days=6)
            days = 7
            idx_func = lambda d: d.weekday()
            rng_str = f"{start.strftime('%m.%d')} - {end.strftime('%m.%d')}"
        else: # MONTHLY
            start = td.replace(day=1)
            next_m = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = next_m - timedelta(days=1)
            days = end.day
            idx_func = lambda d: d.day - 1
            rng_str = start.strftime('%Y.%m')

        dists = [0.0] * days
        t_dist, t_time, h_s, h_c = 0.0, 0, 0, 0
        
        for a in activities:
            if a.get('type') == 'Run':
                ad = datetime.strptime(a['start_date_local'][:10], "%Y-%m-%d")
                if start <= ad <= end:
                    d = a['distance']/1000
                    dists[idx_func(ad)] += d
                    t_dist += d; t_time += a['moving_time']
                    if a.get('average_heartrate'): h_s += a['average_heartrate']; h_c += 1
        
        pace = t_time/t_dist if t_dist > 0 else 0
        return {
            "dists": dists, "total_dist": f"{t_dist:.2f}", 
            "total_time": f"{t_time//3600:02d}:{(t_time%3600)//60:02d}:{t_time%60:02d}",
            "avg_pace": f"{int(pace//60)}'{int(pace%60):02d}\"", 
            "avg_hr": str(int(h_s/h_c)) if h_c > 0 else "0", 
            "range": rng_str, "labels": [str(i+1) for i in range(days)] if mode=="MONTHLY" else ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        }
    except: return None

def create_chart(data, color, labels):
    fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    ax.bar(range(len(labels)), data, color=color, width=0.6)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, color='white', fontsize=12)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='y', left=False, labelleft=False)
    buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); plt.close(fig)
    return Image.open(buf)

def make_collage(files, size):
    tw, th = size
    imgs = [ImageOps.exif_transpose(Image.open(f).convert("RGBA")) for f in files] if files else []
    if not imgs: return Image.new("RGBA", size, (30,30,30,255))
    
    n = len(imgs)
    if n == 1: return ImageOps.fit(imgs[0], size, Image.Resampling.LANCZOS)
    
    cols = math.ceil(math.sqrt(n)); rows = math.ceil(n/cols)
    canvas = Image.new("RGBA", size, (0,0,0,255))
    
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        cur_cols = n % cols if (r == rows-1 and n % cols != 0) else cols
        w_p = tw / cur_cols if (r == rows-1 and n % cols != 0) else tw / cols
        
        x = int(c * w_p) if (r == rows-1 and n % cols != 0) else int(c * tw / cols)
        y = int(r * th / rows)
        w, h = int(w_p), int(th / rows)
        
        canvas.paste(ImageOps.fit(img, (w, h), Image.Resampling.LANCZOS), (x, y))
    return canvas

# --- [3. 메인 로직] ---
col_main, col_design = st.columns([1.6, 1], gap="medium")

# 인증
if 'access_token' not in st.session_state: st.session_state.access_token = None
if "code" in st.query_params and not st.session_state.access_token:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": st.query_params["code"], "grant_type": "authorization_code"}).json()
    st.session_state.access_token = res.get('access_token'); st.query_params.clear(); st.rerun()

acts = []
if st.session_state.access_token:
    r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers={'Authorization': f"Bearer {st.session_state.access_token}"})
    acts = r.json() if r.status_code == 200 else []

# 기본 데이터
v = {"act": "RUNNING", "date": "2026-02-15", "dist": "0.00", "time": "00:00:00", "pace": "0'00\"", "hr": "0"}
chart_data, a_sel = None, None

with col_main:
    st.title("TITAN BOY")
    if not st.session_state.access_token:
        st.link_button("🚀 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        st.button("🔓 로그아웃", on_click=logout)
        bg_files = st.file_uploader("📸 배경", accept_multiple_files=True)
        log_file = st.file_uploader("🔘 로고")
        mode = st.radio("모드", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)

        if acts:
            if mode == "DAILY":
                opts = [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts]
                a_sel = acts[opts.index(st.selectbox("활동", opts))]
                d_km = a_sel['distance']/1000; m_s = a_sel['moving_time']
                v.update({"act": a_sel['name'], "date": a_sel['start_date_local'][:10], 
                          "dist": f"{d_km:.2f}", "time": f"{m_s//3600:02d}:{(m_s%3600)//60:02d}:{m_s%60:02d}", 
                          "pace": f"{int((m_s/d_km)//60)}'{int((m_s/d_km)%60):02d}\"", 
                          "hr": str(int(a_sel.get('average_heartrate', 0)))})
            else:
                is_week = (mode == "WEEKLY")
                dates = sorted(list(set([(datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d") - timedelta(days=datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d").weekday() if is_week else 0)).strftime('%Y-%m-%d' if is_week else '%Y-%m') for ac in acts])), reverse=True)
                sel_d = st.selectbox("기간", dates)
                stats = get_period_stats(acts, f"{sel_d}-01" if not is_week else sel_d, mode)
                
                if stats:
                    chart_data = stats
                    dt = datetime.strptime(sel_d + ("-01" if not is_week else ""), "%Y-%m-%d")
                    if is_week:
                        wn = dt.isocalendar()[1]
                        sfx = "TH" if 11 <= wn <= 13 else {1:"ST",2:"ND",3:"RD"}.get(wn%10, "TH")
                        title = f"{wn}{sfx} WEEK"
                    else:
                        title = dt.strftime("%B").upper()
                    
                    v.update({"act": title, "date": stats['range'], "dist": stats['total_dist'], 
                              "time": stats['total_time'], "pace": stats['avg_pace'], "hr": stats['avg_hr']})

# --- [4. 디자인 및 렌더링] ---
with col_design:
    st.header("🎨 DESIGN")
    v["act"] = st.text_input("제목", v["act"]); v["date"] = st.text_input("날짜", v["date"])
    v["dist"] = st.text_input("거리", v["dist"]); v["time"] = st.text_input("시간", v["time"])
    v["pace"] = st.text_input("페이스", v["pace"]); v["hr"] = st.text_input("심박", v["hr"])
    
    show_vis = st.toggle("그래프/지도", True)
    show_box = st.toggle("박스", True)
    shadow = st.toggle("그림자", True)
    
    cols = {"Yellow":"#FFD700", "White":"#FFFFFF", "Black":"#000000", "Orange":"#FF4500", "Blue":"#00BFFF"}
    m_col = cols[st.selectbox("메인 컬러", list(cols.keys()))]
    s_col = cols[st.selectbox("서브 컬러", list(cols.keys()), index=1)]
    
    orient = st.radio("방향", ["Vertical", "Horizontal"], horizontal=True)
    font_name = st.selectbox("폰트", ["BlackHanSans", "Sunflower", "KirangHaerang", "JollyLodger", "Lacquer", "Orbit", "IndieFlower"])
    
    rx, ry = st.number_input("X", 0, 1080, 40 if orient=="Horizontal" else 70), st.number_input("Y", 0, 1920, 350 if orient=="Horizontal" else 1250)
    rw, rh = st.number_input("W", 100, 1080, 1000 if orient=="Horizontal" else 450), st.number_input("H", 100, 1920, 350 if orient=="Horizontal" else 600)
    b_alpha, v_sz, v_alpha = st.slider("박스 투명도",0,255,110), st.slider("시각화 크기",50,1080,200), st.slider("시각화 투명도",0,255,240)

with col_main:
    if st.session_state.access_token:
        CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
        # 90, 30, 60 규칙 적용
        ft, fd, fn, fl = [load_font(font_name, s) for s in [90, 30, 60, 23]]
        
        canvas = make_collage(bg_files, (CW, CH))
        over = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(over)
        
        # 1. 데이터 박스
        if show_box:
            draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0,0,0,b_alpha))
            items = [("distance", f"{v['dist']} km"), ("time", v["time"]), ("pace", v["pace"]), ("avg bpm", f"{v['hr']} bpm")]
            
            if orient == "Vertical":
                draw_text(draw, (rx+40, ry+30), v["act"], ft, m_col, shadow)
                draw_text(draw, (rx+40+draw.textlength(v["act"], ft)+20, ry+80), v["date"], fd, "#AAAAAA", shadow)
                for i, (l, val) in enumerate(items):
                    y = ry + 165 + i*105
                    draw_text(draw, (rx+40, y), l, fl, "#AAAAAA", shadow)
                    draw_text(draw, (rx+40, y+35), val, fn, s_col, shadow)
            else:
                draw_text(draw, (rx+(rw-draw.textlength(v["act"], ft))//2, ry+35), v["act"], ft, m_col, shadow)
                draw_text(draw, (rx+(rw-draw.textlength(v["date"], fd))//2, ry+135), v["date"], fd, "#AAAAAA", shadow)
                step = rw // 4
                for i, (l, val) in enumerate(items):
                    cx = rx + i*step + step//2
                    draw_text(draw, (cx-draw.textlength(l, fl)//2, ry+200), l, fl, "#AAAAAA", shadow)
                    draw_text(draw, (cx-draw.textlength(val, fn)//2, ry+245), val, fn, s_col, shadow)

        # 2. 시각화 (지도/차트)
        if show_vis:
            vis_img = None
            if mode == "DAILY" and a_sel and a_sel.get('map',{}).get('summary_polyline'):
                pts = polyline.decode(a_sel['map']['summary_polyline'])
                lats, lons = zip(*pts)
                vis_img = Image.new("RGBA", (v_sz, v_sz), (0,0,0,0)); vd = ImageDraw.Draw(vis_img)
                def tr(la, lo): return 15+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(v_sz-30), (v_sz-15)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(v_sz-30)
                vd.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_col, v_alpha), width=6)
                pos = (rx, ry-v_sz-20) if orient=="Vertical" else (rx+100, ry+10)
                
            elif mode in ["WEEKLY", "MONTHLY"] and chart_data:
                c_img = create_chart(chart_data['dists'], m_col, chart_data['labels'])
                vis_img = c_img.resize((v_sz, int(c_img.height*(v_sz/c_img.width))), Image.Resampling.LANCZOS)
                vis_img.putalpha(vis_img.getchannel('A').point(lambda x: x*(v_alpha/255)))
                pos = ((CW-vis_img.width)//2, CH-vis_img.height-80)

            if vis_img: over.paste(vis_img, (int(pos[0]), int(pos[1])), vis_img)

        # 3. 로고
        if log_file:
            ls = 90
            l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (ls, ls))
            mask = Image.new('L', (ls,ls), 0); ImageDraw.Draw(mask).ellipse((0,0,ls,ls), fill=255); l_img.putalpha(mask)
            over.paste(l_img, (CW-ls-40, 40), l_img)

        final = Image.alpha_composite(canvas, over).convert("RGB")
        st.image(final, width=350)
        buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
        st.download_button("📸 DOWNLOAD", buf.getvalue(), "titan.jpg", use_container_width=True)
