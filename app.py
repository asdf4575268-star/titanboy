import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl

# --- [1. Strava API 및 기본 설정] ---
API_CONFIGS = {
    "PRIMARY": {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'},
    "SECONDARY": {"ID": '202274', "SECRET": '63f6a7007ebe6b405763fc3104e17bb53b468ad0'}
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

def make_smart_collage(files, target_size):
    tw, th = target_size
    imgs = [ImageOps.exif_transpose(Image.open(f).convert("RGBA")) for f in files[:10]]
    n = len(imgs)
    if n == 0: return Image.new("RGBA", (tw, th), (30, 30, 30, 255))
    if n == 1: return ImageOps.fit(imgs[0], (tw, th))
    if n == 2: cols, rows = 2, 1
    elif n <= 4: cols, rows = 2, 2
    elif n <= 6: cols, rows = 3, 2
    elif n <= 9: cols, rows = 3, 3
    else: cols, rows = 5, 2
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
    w_step, h_step = tw / cols, th / rows
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        x1, y1 = int(c * w_step), int(r * h_step)
        x2 = int((c + 1) * w_step) if (c + 1) < cols else tw
        y2 = int((r + 1) * h_step) if (r + 1) < rows else th
        sub_img = ImageOps.fit(img, (x2 - x1, y2 - y1))
        canvas.paste(sub_img, (x1, y1))
    return canvas

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
        avg_pace = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\""
        fmt_time = f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}"
        return {"dists": weekly_dist, "total_dist": f"{total_dist:.2f}", "total_time": fmt_time, "avg_pace": avg_pace, "avg_hr": str(avg_hr), "range": f"{start_of_week.strftime('%m.%d')} - {end_of_week.strftime('%m.%d')}"}
    except: return None

def get_monthly_stats(activities, target_date_str):
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        first_day = target_date.replace(day=1)
        if target_date.month == 12: last_day = target_date.replace(year=target_date.year + 1, month=1, day=1) - timedelta(days=1)
        else: last_day = target_date.replace(month=target_date.month + 1, day=1) - timedelta(days=1)
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
        avg_pace = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\""
        fmt_time = f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}"
        return {"dists": monthly_dist, "total_dist": f"{total_dist:.2f}", "total_time": fmt_time, "avg_pace": avg_pace, "avg_hr": str(avg_hr), "range": first_day.strftime('%Y.%m'), "labels": [str(i+1) for i in range(num_days)]}
    except: return None

def create_bar_chart(data, color_hex, mode="WEEKLY", labels=None):
    if mode == "WEEKLY": labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    fig, ax = plt.subplots(figsize=(10, 3.5), dpi=150)
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    bars = ax.bar(labels, data, color=color_hex, width=0.6)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='x', colors='white', labelsize=10 if mode=="MONTHLY" else 14); ax.tick_params(axis='y', left=False, labelleft=False)
    if mode == "WEEKLY":
        for bar in bars:
            h = bar.get_height()
            if h > 0: ax.text(bar.get_x() + bar.get_width()/2., h + 0.1, f'{h:.1f}', ha='center', va='bottom', color='white', fontsize=12, fontweight='bold')
    plt.tight_layout(); buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); buf.seek(0); plt.close(fig)
    return Image.open(buf)

@st.cache_resource
def load_font(font_type, size):
    fonts = {"BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf", "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf", "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf", "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf", "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Bold.ttf"}
    f_path = f"font_{font_type}_{int(size)}.ttf"
    if not os.path.exists(f_path):
        r = requests.get(fonts.get(font_type, fonts["BlackHanSans"])); open(f_path, "wb").write(r.content)
    return ImageFont.truetype(f_path, int(size))

# --- [3. 인증 및 데이터 처리] ---
if 'access_token' not in st.session_state: st.session_state['access_token'] = None
query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": query_params["code"], "grant_type": "authorization_code"}).json()
    if 'access_token' in res: st.session_state['access_token'] = res['access_token']; st.query_params.clear(); st.rerun()

acts = []
if st.session_state['access_token']:
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
    r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)
    if r.status_code == 200: acts = r.json()

# --- [4. 레이아웃: 사이드바] ---
with st.sidebar:
    st.header("✍️ MANUAL EDIT")
    v_act_in = st.text_input("활동명 (수기)")
    v_date_in = st.text_input("날짜 (수기)")
    v_dist_in = st.text_input("거리 km (수기)")
    v_time_in = st.text_input("시간 (수기)")
    v_pace_in = st.text_input("페이스 (수기)")
    v_hr_in = st.text_input("심박 bpm (수기)")

# --- [5. 메인 레이아웃] ---
col_main, col_design = st.columns([2, 1], gap="medium")
with col_main:
    st.title("TITAN BOY")
    if not st.session_state['access_token']:
        st.link_button("🚀 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        st.button("🔓 로그아웃", on_click=logout_and_clear)
    
    mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True, label_visibility="collapsed")
    bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("🔘 원형 로고", type=['jpg','jpeg','png'])
    
    v_act, v_date, v_dist, v_time, v_pace, v_hr, weekly_data, monthly_data, a = "RUNNING", "2026-02-14", "0.00", "00:00:00", "0'00\"", "0", None, None, None
    if acts:
        act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
        sel_str = st.selectbox("🏃 활동 선택", act_options)
        a = acts[act_options.index(sel_str)]
        if mode == "DAILY":
            d_km = a.get('distance', 0)/1000; m_sec = a.get('moving_time', 0)
            v_act, v_date, v_dist = a['name'], a['start_date_local'][:10], f"{d_km:.2f}"
            v_time = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}"
            v_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
            v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        elif mode == "WEEKLY":
            weekly_data = get_weekly_stats(acts, a['start_date_local'][:10])
            if weekly_data: v_act, v_date, v_dist, v_time, v_pace, v_hr = "WEEKLY RUN", weekly_data['range'], weekly_data['total_dist'], weekly_data['total_time'], weekly_data['avg_pace'], weekly_data['avg_hr']
        elif mode == "MONTHLY":
            monthly_data = get_monthly_stats(acts, a['start_date_local'][:10])
            if monthly_data: v_act, v_date, v_dist, v_time, v_pace, v_hr = "MONTHLY RUN", monthly_data['range'], monthly_data['total_dist'], monthly_data['total_time'], monthly_data['avg_pace'], monthly_data['avg_hr']

    v_act = v_act_in if v_act_in else v_act
    v_date = v_date_in if v_date_in else v_date
    v_dist = v_dist_in if v_dist_in else v_dist
    v_time = v_time_in if v_time_in else v_time
    v_pace = v_pace_in if v_pace_in else v_pace
    v_hr = v_hr_in if v_hr_in else v_hr

with col_design:
    st.header("🎨 DESIGN")
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    show_box, show_vis = st.toggle("데이터 박스", value=True), st.toggle("지도/그래프", value=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    COLOR_OPTS = {"Yellow": "#FFD700", "White": "#FFFFFF", "Orange": "#FF4500", "Blue": "#00BFFF", "Grey": "#AAAAAA"}
    m_color = COLOR_OPTS[st.selectbox("포인트 컬러", list(COLOR_OPTS.keys()))]
    sub_color = COLOR_OPTS[st.selectbox("서브 컬러", list(COLOR_OPTS.keys()), index=1)]
    CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
    rx = st.number_input("X 위치", 0, 1080, 70)
    ry = st.number_input("Y 위치", 0, 1920, 1250 if mode=="DAILY" else 850)
    rw, rh = st.number_input("박스 너비", 100, 1080, 1080 if box_orient=="Horizontal" else 450), st.number_input("박스 높이", 100, 1920, 260 if box_orient=="Horizontal" else 630)
    box_alpha = st.slider("박스 투명도", 0, 255, 80)
    vis_sz = st.slider("지도/그래프 크기", 50, 1080, 250 if mode=="DAILY" else 1080)
    vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 255)

# --- [6. 렌더링 엔진] ---
try:
    f_t, f_d, f_n, f_l = load_font(sel_font, 70), load_font(sel_font, 20), load_font(sel_font, 40), load_font(sel_font, 23)
    canvas = make_smart_collage(bg_files, (CW, CH)) if bg_files else Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
    overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
    
    if show_box:
        items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
        if box_orient == "Vertical":
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
            draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
            draw.text((rx+40, ry+130), v_date, font=f_d, fill="#AAAAAA")
            y_c = ry + 210
            for lab, val in items:
                draw.text((rx+40, y_c), lab.lower(), font=f_l, fill="#AAAAAA")
                v_s = val.lower() if any(x in val for x in ["km","bpm"]) else val
                draw.text((rx+40, y_c+25), v_s, font=f_n, fill=sub_color); y_c += 115
        else:
            draw.rectangle([0, ry, 1080, ry + rh], fill=(0,0,0,box_alpha))
            t_w = draw.textlength(v_act, font=f_t); draw.text(((1080 - t_w)//2, ry + 35), v_act, font=f_t, fill=m_color)
            d_w = draw.textlength(v_date, font=f_d); draw.text(((1080 - d_w)//2, ry + 125), v_date, font=f_d, fill="#AAAAAA")
            sec_w = 1080 // 4
            for i, (lab, val) in enumerate(items):
                cx = (i * sec_w) + (sec_w // 2); v_s = val.lower() if any(x in val for x in ["km","bpm"]) else val
                lw, vw = draw.textlength(lab.lower(), font=f_l), draw.textlength(v_s, font=f_n)
                draw.text((cx - lw//2, ry + 175), lab.lower(), font=f_l, fill="#AAAAAA")
                draw.text((cx - vw//2, ry + 205), v_s, font=f_n, fill=sub_color)

    if show_vis:
        if mode == "DAILY" and a and a.get('map', {}).get('summary_polyline'):
            pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
            vis_layer = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); m_draw = ImageDraw.Draw(vis_layer)
            def tr(la, lo): return 15+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-30), (vis_sz-15)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-30)
            m_draw.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, vis_alpha), width=5)
            act_w = draw.textlength(v_act, font=f_t)
            m_x, m_y = (rx + 40 + act_w + 20, ry + 30) if box_orient == "Vertical" else ((1080 + act_w)//2 + 20, ry + 35)
            overlay.paste(vis_layer, (int(m_x), int(m_y)), vis_layer)
        elif mode in ["WEEKLY", "MONTHLY"]:
            data_obj = weekly_data if mode == "WEEKLY" else monthly_data
            if data_obj:
                chart_img = create_bar_chart(data_obj['dists'], m_color, mode=mode, labels=data_obj.get('labels'))
                w_p = (vis_sz / float(chart_img.size[0])); vis_layer = chart_img.resize((vis_sz, int(chart_img.size[1]*w_p)), Image.Resampling.LANCZOS)
                alpha_mask = vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255)); vis_layer.putalpha(alpha_mask)
                overlay.paste(vis_layer, ((CW - vis_layer.width)//2, CH - vis_layer.height - 80), vis_layer)

    if log_file:
        ls = 100; l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (ls, ls))
        mask = Image.new('L', (ls, ls), 0); ImageDraw.Draw(mask).ellipse((0, 0, ls, ls), fill=255); l_img.putalpha(mask)
        l_pos = (1080 - ls - 30, ry + 30) if box_orient == "Horizontal" else (rx + rw - ls - 25, ry + rh - ls - 25)
        overlay.paste(l_img, l_pos, l_img)

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    with col_main:
        st.image(final, use_container_width=True)
        buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
        st.download_button(f"📸 {mode} DOWNLOAD", buf.getvalue(), f"{mode.lower()}.jpg", use_container_width=True)

except Exception as e:
    with col_main: st.info(f"데이터를 선택해 주세요.")
