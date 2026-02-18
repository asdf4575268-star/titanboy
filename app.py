import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import font_manager

# --- [1. 기본 설정 및 API] ---
API_CONFIGS = {
    "PRIMARY": {"ID": '202274', "SECRET": '63f6a7007ebe6b405763fc3104e17bb53b468ad0'},
    "SECONDARY": {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'}
}
CURRENT_CFG = API_CONFIGS["PRIMARY"] 
CLIENT_ID, CLIENT_SECRET = CURRENT_CFG["ID"], CURRENT_CFG["SECRET"]
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

st.set_page_config(page_title="TITAN BOY", layout="wide")
mpl.use('Agg')

# --- [2. 유틸리티 함수] ---
def logout_and_clear():
    st.cache_data.clear(); st.cache_resource.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

def draw_styled_text(draw, pos, text, font, fill, shadow=True):
    if shadow:
        draw.text((pos[0]+2, pos[1]+2), text, font=font, fill=(0, 0, 0, 220))
    draw.text(pos, text, font=font, fill=fill)

def load_font(name, size):
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "KirangHaerang": "https://github.com/google/fonts/raw/main/ofl/kiranghaerang/KirangHaerang-Regular.ttf",
        "JollyLodger": "https://github.com/google/fonts/raw/main/ofl/jollylodger/JollyLodger-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf"
    }
    f_path = f"font_{name}.ttf"
    if not os.path.exists(f_path):
        try:
            r = requests.get(fonts[name])
            with open(f_path, "wb") as f: f.write(r.content)
        except: return ImageFont.load_default()
    try: return ImageFont.truetype(f_path, int(size))
    except: return ImageFont.load_default()

def get_weekly_stats(activities, target_date_str):
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        weekly_dist = [0.0] * 7
        total_dist, total_time, hr_sum, hr_count = 0.0, 0, 0, 0
        for act in activities:
            if act.get('type') == 'Run':
                act_date = datetime.strptime(act['start_date_local'][:10], "%Y-%m-%d")
                if start_of_week <= act_date <= end_of_week:
                    dist = act.get('distance', 0) / 1000
                    weekly_dist[act_date.weekday()] += dist
                    total_dist += dist; total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): hr_sum += act.get('average_heartrate'); hr_count += 1
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        return {"dists": weekly_dist, "total_dist": f"{total_dist:.2f}", "total_time": f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}", "avg_pace": f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\"", "avg_hr": str(avg_hr), "range": f"{start_of_week.strftime('%m.%d')} - {end_of_week.strftime('%m.%d')}"}
    except: return None

def get_monthly_stats(activities, target_date_str):
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        first_day = target_date.replace(day=1)
        next_month = (first_day + timedelta(days=32)).replace(day=1)
        last_day = next_month - timedelta(days=1)
        num_days = last_day.day
        monthly_dist = [0.0] * num_days
        total_dist, total_time, hr_sum, hr_count = 0.0, 0, 0, 0
        for act in activities:
            if act.get('type') == 'Run':
                act_date = datetime.strptime(act['start_date_local'][:10], "%Y-%m-%d")
                if first_day <= act_date <= last_day:
                    dist = act.get('distance', 0) / 1000
                    monthly_dist[act_date.day - 1] += dist
                    total_dist += dist; total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): hr_sum += act.get('average_heartrate'); hr_count += 1
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        return {"dists": monthly_dist, "total_dist": f"{total_dist:.2f}", "total_time": f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}", "avg_pace": f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\"", "avg_hr": str(avg_hr), "range": first_day.strftime('%Y.%m'), "labels": [str(i+1) for i in range(num_days)]}
    except: return None

def create_bar_chart(data, color_hex, mode="WEEKLY", labels=None):
    if mode == "WEEKLY": labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    x_pos = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(10, 5.0), dpi=150)
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    ax.bar(x_pos, data, color=color_hex, width=0.6)
    ax.set_xticks(x_pos); ax.set_xticklabels(labels)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', left=False, labelleft=False)
    plt.tight_layout(); buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); buf.seek(0); plt.close(fig)
    return Image.open(buf)

def make_smart_collage(files, target_size):
    tw, th = target_size
    imgs = [ImageOps.exif_transpose(Image.open(f)).convert("RGBA") for f in files]
    if not imgs: return Image.new("RGBA", (tw, th), (30, 30, 30, 255))
    n = len(imgs)
    if n == 1: return ImageOps.fit(imgs[0], (tw, th), Image.Resampling.LANCZOS)
    cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        x0, y0 = int(c * tw / cols), int(r * th / rows)
        x1 = int((c + 1) * tw / cols) if not (r == rows - 1 and n % cols != 0) else int(((i % cols) + 1) * (tw / (n % cols)))
        y1 = int((r + 1) * th / rows)
        canvas.paste(ImageOps.fit(img, (x1-x0, y1-y0), Image.Resampling.LANCZOS), (x0, y0))
    return canvas

# --- [3. 인증 및 데이터] ---
if 'access_token' not in st.session_state: st.session_state['access_token'] = None
if 'cached_acts' not in st.session_state: st.session_state['cached_acts'] = []

q_params = st.query_params
if "token" in q_params: st.session_state['access_token'] = q_params["token"]
if "code" in q_params and not st.session_state['access_token']:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": q_params["code"], "grant_type": "authorization_code"}).json()
    if 'access_token' in res:
        st.session_state['access_token'] = res['access_token']
        st.query_params.clear(); st.query_params["token"] = res['access_token']; st.rerun()

if st.session_state['access_token'] and not st.session_state['cached_acts']:
    r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers={'Authorization': f"Bearer {st.session_state['access_token']}"})
    if r.status_code == 200: st.session_state['cached_acts'] = r.json()

acts = st.session_state['cached_acts']

# --- [4. 레이아웃] ---
col_main, col_design = st.columns([1.6, 1], gap="medium")

with col_main:
    st.title("TITAN BOY")
    v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", "2026.02.16", "0.00", "00:00:00", "0'00\"", "0"
    a, weekly_data, monthly_data = None, None, None

    if not st.session_state['access_token']:
        st.link_button("🚀 Strava 연동하기", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        if st.button("🔓 로그아웃", use_container_width=True): logout_and_clear()
        bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
        log_file = st.file_uploader("🔘 로고", type=['jpg','jpeg','png'])
        mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)

        if acts:
            if mode == "DAILY":
                act_opts = [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts]
                sel_act = st.selectbox("🏃 활동 선택", act_opts); a = acts[act_opts.index(sel_act)]
                if a:
                    v_act = a['name'].upper()
                    dt_obj = datetime.strptime(a['start_date_local'][:19], "%Y-%m-%dT%H:%M:%S")
                    v_date = f"{a['start_date_local'][:10].replace('-', '.')} {dt_obj.strftime('%I:%M %p').lower()}"
                    d_km = a.get('distance', 0)/1000; m_s = a.get('moving_time', 0)
                    v_dist = f"{d_km:.2f}"; v_time = f"{int(m_s//3600):02d}:{int((m_s%3600)//60):02d}:{int(m_s%60):02d}" if m_s >= 3600 else f"{int(m_s//60):02d}:{int(m_s%60):02d}"
                    v_pace = f"{int((m_s/d_km)//60)}'{int((m_s/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
                    v_hr = str(int(a.get('average_heartrate', 0)))
            elif mode == "WEEKLY":
                weeks = sorted(list(set([(datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d") - timedelta(days=datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d").weekday())).strftime('%Y-%m-%d') for ac in acts])), reverse=True)
                sel_week = st.selectbox("📅 주차 선택", weeks, format_func=lambda x: f"{x[:4]}-{datetime.strptime(x, '%Y-%m-%d').isocalendar()[1]}주차")
                weekly_data = get_weekly_stats(acts, sel_week)
                if weekly_data:
                    v_act = f"{datetime.strptime(sel_week, '%Y-%m-%d').isocalendar()[1]} WEEK"
                    v_date, v_dist, v_time, v_pace, v_hr = weekly_data['range'], weekly_data['total_dist'], weekly_data['total_time'], weekly_data['avg_pace'], weekly_data['avg_hr']
            elif mode == "MONTHLY":
                months = sorted(list(set([ac['start_date_local'][:7] for ac in acts])), reverse=True)
                sel_month = st.selectbox("🗓️ 월 선택", months)
                monthly_data = get_monthly_stats(acts, f"{sel_month}-01")
                if monthly_data:
                    v_act = datetime.strptime(f"{sel_month}-01", "%Y-%m-%d").strftime("%B").upper()
                    v_date, v_dist, v_time, v_pace, v_hr = monthly_data['range'], monthly_data['total_dist'], monthly_data['total_time'], monthly_data['avg_pace'], monthly_data['avg_hr']

with col_design:
    st.header("🎨 DESIGN")
    with st.expander("✍️ 텍스트 수정"):
        v_act = st.text_input("활동명", v_act); v_date = st.text_input("날짜", v_date)
        v_dist = st.text_input("거리 km", v_dist); v_time = st.text_input("시간", v_time)
        v_pace = st.text_input("페이스", v_pace); v_hr = st.text_input("심박 bpm", v_hr)
    with st.expander("💄 스타일", expanded=True):
        show_vis, show_box, use_shadow = st.toggle("지도/그래프", True), st.toggle("박스", True), st.toggle("그림자", True)
        m_color = st.selectbox("포인트 컬러", ["#FFD700", "#FFFFFF", "#000000", "#FF4500"])
        sub_color = st.selectbox("서브 컬러", ["#FFFFFF", "#FFD700", "#AAAAAA"])
        sel_font = st.selectbox("폰트", ["BlackHanSans", "KirangHaerang", "JollyLodger", "Lacquer"])
    box_orient = st.radio("방향", ["Vertical", "Horizontal"], index=(0 if mode == "DAILY" else 1), horizontal=True)
    with st.expander("📍 조절"):
        rx = st.number_input("X", 0, 1080, 40); ry = st.number_input("Y", 0, 1920, 1200)
        rw = st.number_input("W", 100, 1080, 1000); rh = st.number_input("H", 100, 1920, 400)
        box_alpha = st.slider("투명도", 0, 255, 0)
        vis_sz_adj = st.slider("크기", 50, 1080, 1000); vis_alpha = st.slider("가시성", 0, 255, 255)

with col_main:
    st.subheader("🖼️ PREVIEW")
    if (mode == "DAILY" and a) or (mode == "WEEKLY" and weekly_data) or (mode == "MONTHLY" and monthly_data):
        try:
            CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
            f_t, f_d, f_n, f_l = load_font(sel_font, 90), load_font(sel_font, 30), load_font(sel_font, 60), load_font(sel_font, 23)
            canvas = make_smart_collage(bg_files, (CW, CH)) if bg_files else Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
            overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
            
            if show_box:
                draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0,0,0,box_alpha))
                if box_orient == "Vertical":
                    draw_styled_text(draw, (rx+40, ry+30), v_act, f_t, m_color, use_shadow)
                    draw_styled_text(draw, (rx+40, ry+130), v_date, f_d, "#AAAAAA", use_shadow)
                    for i, (l, v) in enumerate(items):
                        draw_styled_text(draw, (rx+40, ry+220+i*110), l.lower(), f_l, "#AAAAAA", use_shadow)
                        draw_styled_text(draw, (rx+40, ry+255+i*110), v.lower(), f_n, sub_color, use_shadow)
                else:
                    draw_styled_text(draw, (rx+(rw-draw.textlength(v_act, f_t))//2, ry+30), v_act, f_t, m_color, use_shadow)
                    draw_styled_text(draw, (rx+(rw-draw.textlength(v_date, f_d))//2, ry+130), v_date, f_d, "#AAAAAA", use_shadow)
                    for i, (l, v) in enumerate(items):
                        cx = rx + (i*rw//4) + (rw//8)
                        draw_styled_text(draw, (cx-draw.textlength(l.lower(), f_l)//2, ry+220), l.lower(), f_l, "#AAAAAA", use_shadow)
                        draw_styled_text(draw, (cx-draw.textlength(v.lower(), f_n)//2, ry+260), v.lower(), f_n, sub_color, use_shadow)

            if show_vis:
                if mode == "DAILY" and a.get('map', {}).get('summary_polyline'):
                    pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
                    v_layer = Image.new("RGBA", (vis_sz_adj, vis_sz_adj), (0,0,0,0)); m_draw = ImageDraw.Draw(v_layer)
                    def tr(la, lo): return 20+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz_adj-40), (vis_sz_adj-20)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz_adj-40)
                    m_draw.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, vis_alpha), width=8)
                    overlay.paste(v_layer, ((CW-vis_sz_adj)//2, ry-vis_sz_adj-20), v_layer)
                elif mode in ["WEEKLY", "MONTHLY"]:
                    d_obj = weekly_data if mode == "WEEKLY" else monthly_data
                    chart = create_bar_chart(d_obj['dists'], m_color, mode=mode)
                    chart = chart.resize((vis_sz_adj, int(chart.size[1]*vis_sz_adj/chart.size[0])), Image.Resampling.LANCZOS)
                    chart.putalpha(chart.getchannel('A').point(lambda x: x * vis_alpha / 255))
                    overlay.paste(chart, ((CW-vis_sz_adj)//2, CH-chart.height-50), chart)

            if log_file:
                l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (100, 100), Image.Resampling.LANCZOS)
                overlay.paste(l_img, (CW-140, 40), l_img)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, width=400)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "running.jpg", use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")
