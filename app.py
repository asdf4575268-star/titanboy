import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import font_manager
import base64
import streamlit.components.v1 as components
import sqlite3
import time

# --- [1. 기본 설정 및 API] ---
API_CONFIGS = {
    "PRIMARY": {"ID": '202274', "SECRET": '63f6a7007ebe6b405763fc3104e17bb53b468ad0'},
    "SECONDARY": {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'}
}
CURRENT_CFG = API_CONFIGS["PRIMARY"]
CLIENT_ID, CLIENT_SECRET = CURRENT_CFG["ID"], CURRENT_CFG["SECRET"]
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app/"

try:
    logo = Image.open("logo.png")
    st.set_page_config(layout="centered", page_title="TITAN BOY", page_icon=logo, initial_sidebar_state="collapsed")
except:
    st.set_page_config(layout="centered", page_title="TITAN BOY", initial_sidebar_state="collapsed")
mpl.use("Agg")

# --- [2. 유틸리티 함수] ---
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
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf",
        "Condiment": "https://github.com/google/fonts/raw/main/ofl/condiment/Condiment-Regular.ttf",
        "Bangers": "https://github.com/google/fonts/raw/main/ofl/bangers/Bangers-Regular.ttf",
        "BagelFatOne": "https://github.com/google/fonts/raw/main/ofl/bagelfatone/BagelFatOne-Regular.ttf"
    }
    f_path = f"font_{name}.ttf"
    if not os.path.exists(f_path):
        try:
            r = requests.get(fonts[name])
            with open(f_path, "wb") as f:
                f.write(r.content)
        except:
            return ImageFont.load_default()
    try:
        return ImageFont.truetype(f_path, int(size))
    except:
        return ImageFont.load_default()

@st.cache_data(show_spinner=False)
def get_icon_pil(name, size=(30, 30)):
    urls = {
        "dumbbell": "https://img.icons8.com/ios-filled/150/ffffff/dumbbell.png",
        "run": "https://img.icons8.com/ios-filled/150/ffffff/running.png"
    }
    try:
        r = requests.get(urls.get(name), headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    except: pass
    return None

def colorize_icon(icon, hex_color):
    if not icon: return None
    c_rgb = hex_to_rgba(hex_color, 255)[:3]
    c_icon = Image.new("RGBA", icon.size, c_rgb)
    c_icon.putalpha(icon.getchannel('A'))
    return c_icon

def get_weekly_stats(activities, target_date_str, target_type="Run"):
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        weekly_dist = [0.0] * 7
        total_dist, total_time, hr_sum, hr_count = 0.0, 0, 0, 0
        other_count, other_total_time = 0, 0.0
        
        for act in activities:
            act_date = datetime.strptime(act['start_date_local'][:10], "%Y-%m-%d")
            if start_of_week <= act_date <= end_of_week:
                if act.get('type') == target_type:
                    dist = act.get('distance', 0) / 1000
                    time_min = act.get('moving_time', 0) / 60
                    weekly_dist[act_date.weekday()] += dist if target_type == "Run" else time_min
                    total_dist += dist; total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): hr_sum += act.get('average_heartrate'); hr_count += 1
                elif act.get('type') in ['WeightTraining', 'Workout']:
                    other_count += 1; other_total_time += act.get('moving_time', 0) / 60
                    
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        avg_pace_str = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\"" if target_type == "Run" else "-"
        return {"dists": weekly_dist, "total_dist": f"{total_dist:.2f}" if target_type == "Run" else "-", "total_time": f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}", "avg_pace": avg_pace_str, "avg_hr": str(avg_hr), "range": f"{start_of_week.strftime('%m.%d')} - {end_of_week.strftime('%m.%d')}", "other_count": other_count, "other_total_time": other_total_time}
    except: return None

def get_monthly_stats(activities, target_date_str, target_type="Run"):
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        first_day = target_date.replace(day=1)
        next_month = first_day.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        num_days = last_day.day
        monthly_dist = [0.0] * num_days
        total_dist, total_time, hr_sum, hr_count = 0.0, 0, 0, 0
        other_count, other_total_time = 0, 0.0
        
        for act in activities:
            act_date = datetime.strptime(act['start_date_local'][:10], "%Y-%m-%d")
            if first_day <= act_date <= last_day:
                if act.get('type') == target_type:
                    dist = act.get('distance', 0) / 1000
                    time_min = act.get('moving_time', 0) / 60
                    monthly_dist[act_date.day - 1] += dist if target_type == "Run" else time_min
                    total_dist += dist; total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): hr_sum += act.get('average_heartrate'); hr_count += 1
                elif act.get('type') in ['WeightTraining', 'Workout']:
                    other_count += 1; other_total_time += act.get('moving_time', 0) / 60
                    
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        avg_pace_str = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\"" if target_type == "Run" else "-"
        return {"dists": monthly_dist, "total_dist": f"{total_dist:.2f}" if target_type == "Run" else "-", "total_time": f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}", "avg_pace": avg_pace_str, "avg_hr": str(avg_hr), "range": first_day.strftime('%Y.%m'), "labels": [str(i+1) for i in range(num_days)], "other_count": other_count, "other_total_time": other_total_time}
    except: return None

def create_bar_chart(data, color_hex, mode="WEEKLY", labels=None, font_path=None):
    if mode == "WEEKLY": labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    x_pos = np.arange(len(labels))
    prop = font_manager.FontProperties(fname=font_path) if font_path else None
    
    fig, ax = plt.subplots(figsize=(10, 5.0), dpi=150)
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    ax.bar(x_pos, data, color=color_hex, width=0.6)
    ax.set_xticks(x_pos); ax.set_xticklabels(labels)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='x', colors='white')
    if prop:
        for label in ax.get_xticklabels(): label.set_fontproperties(prop); label.set_fontsize(10 if mode=="MONTHLY" else 14)
    ax.tick_params(axis='y', left=False, labelleft=False)
    plt.tight_layout(); buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); buf.seek(0); plt.close(fig)
    return Image.open(buf)

def make_smart_collage(files, target_size):
    tw, th = target_size; imgs = []
    for f in files:
        try: imgs.append(ImageOps.exif_transpose(Image.open(f)).convert("RGBA"))
        except: continue
    if not imgs: return Image.new("RGBA", (tw, th), (30, 30, 30, 255))
    
    n = len(imgs)
    if n == 1: return ImageOps.fit(imgs[0], (tw, th), Image.Resampling.LANCZOS)

    cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
    
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        x0, y0 = int(c * tw / cols), int(r * th / rows)
        if r == rows - 1 and n % cols != 0:
            row_tw = tw / (n % cols); x0 = int((i % cols) * row_tw); x1 = int(((i % cols) + 1) * row_tw)
        else: x1 = int((c + 1) * tw / cols)
        y1 = int((r + 1) * th / rows)
        canvas.paste(ImageOps.fit(img, (x1 - x0, y1 - y0), Image.Resampling.LANCZOS), (x0, y0))
    return canvas

# --- [3. 인증 및 데이터 연동] ---
DB_PATH = "archive_prism_total_v5.db"
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS strava_tokens (id INTEGER PRIMARY KEY, access_token TEXT, refresh_token TEXT, expires_at INTEGER)")
        conn.commit(); conn.close()
    except: pass
init_db()

def handle_token_db(mode="load", data=None):
    try:
        conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
        if mode == "save" and data:
            cur.execute("DELETE FROM strava_tokens")
            cur.execute("INSERT INTO strava_tokens (access_token, refresh_token, expires_at) VALUES (?, ?, ?)", (data['access_token'], data['refresh_token'], data['expires_at']))
            conn.commit()
        elif mode == "load":
            cur.execute("SELECT access_token, refresh_token, expires_at FROM strava_tokens LIMIT 1")
            row = cur.fetchone(); conn.close(); return row
        conn.close()
    except: return None

if 'access_token' not in st.session_state:
    saved = handle_token_db("load")
    if saved:
        a_token, r_token, exp_at = saved
        if time.time() > (exp_at - 1800):
            try:
                res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "refresh_token", "refresh_token": r_token})
                if res.status_code == 200:
                    res_data = res.json()
                    if 'access_token' in res_data: 
                        handle_token_db("save", res_data)
                        st.session_state['access_token'] = res_data['access_token']
            except: pass
        else: st.session_state['access_token'] = a_token

if "code" in st.query_params:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": st.query_params["code"], "grant_type": "authorization_code"})
    if res.status_code == 200:
        res_data = res.json()
        if 'access_token' in res_data: 
            handle_token_db("save", res_data)
            st.session_state['access_token'] = res_data['access_token']
            st.query_params.clear()
            st.rerun()
    else:
        st.error(f"인증 코드를 토큰으로 교환하는데 실패했습니다. (상태 코드: {res.status_code})")

acts = []
if st.session_state.get('access_token'):
    if not st.session_state.get('cached_acts'):
        r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers={'Authorization': f"Bearer {st.session_state['access_token']}"})
        if r.status_code == 200: 
            st.session_state['cached_acts'] = r.json()
        elif r.status_code == 429:
            st.error("⚠️ Strava API 호출 한도(15분 당 100회)를 초과했습니다. 잠시 후 다시 시도해주세요.")
        elif r.status_code == 401: 
            st.session_state.clear()
            st.rerun()
        else:
            st.error(f"데이터를 불러오는데 실패했습니다. (상태 코드: {r.status_code})")
            
    acts = st.session_state.get('cached_acts', [])

# --- [4. 메인 화면 구성 및 UI] ---
def get_base64(path):
    try:
        with open(path, "rb") as f: return base64.b64encode(f.read()).decode()
    except: return ""

st.markdown("""<style>.header-wrap { display: flex; align-items: center; gap: 8px; } .header-wrap h1 { margin: 0; letter-spacing: -1px; }</style>""", unsafe_allow_html=True)
logo_base64 = get_base64("logo.png")
st.markdown(f"""<div class="header-wrap"><img src="data:image/png;base64,{logo_base64}" width="90"><h1>TITAN BOY</h1></div>""" if logo_base64 else "<h1>TITAN BOY</h1>", unsafe_allow_html=True)

bg_files, log_file, user_graph_file = [], None, None
mode = "DAILY"
v_act, v_date, v_dist, v_pace, v_time, v_hr, v_type, v_memo = "RUNNING", "2026.02.16", "0.00", "00:00:00", "0'00\"", "0", "Run", ""
weekly_data, monthly_data, a, v_diff_str = None, None, None, ""

if not st.session_state.get('access_token'):
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url, use_container_width=True)
else:
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("🔓 로그아웃", use_container_width=True): 
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    with st.expander("📂 1. 데이터 및 사진 설정", expanded=True):
        bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
        c_up1, c_up2 = st.columns(2)
        with c_up1: log_file = st.file_uploader("🔘 로고", type=['jpg','jpeg','png'])
        with c_up2: user_graph_file = st.file_uploader("📈 그래프(선택)", type=['jpg','png','jpeg'])
                
        st.markdown("---")
        mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)
        if mode in ["WEEKLY", "MONTHLY"]: v_type = st.radio("종목 선택", ["Run", "WeightTraining", "Workout"], horizontal=True)

        if acts:
            if mode == "DAILY":
                act_opts = [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts]
                sel_act = st.selectbox("🏃 활동 선택", act_opts)
                a = acts[act_opts.index(sel_act)]
                if a:
                    v_type = a.get('type', 'Run'); v_act = a['name'].upper()
                    v_date = f"{a['start_date_local'][:10].replace('-', '.')} {datetime.strptime(a['start_date_local'][:19], '%Y-%m-%dT%H:%M:%S').strftime('%I:%M %p').lower()}"
                    d_km = a.get('distance', 0)/1000; m_s = a.get('moving_time', 0)
                    v_dist = f"{d_km:.2f}" 
                    v_pace = f"{int((m_s/d_km)//60)}'{int((m_s/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
                    v_time = f"{int(m_s//3600):02d}:{int((m_s%3600)//60):02d}:{int(m_s%60):02d}" if m_s >= 3600 else f"{int(m_s//60):02d}:{int(m_s%60):02d}"
                    v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
            elif mode == "WEEKLY":
                weeks = sorted(list(set([(datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d") - timedelta(days=datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d").weekday())).strftime('%Y-%m-%d') for ac in acts])), reverse=True)
                sel_week = st.selectbox("📅 주차 선택", weeks, format_func=lambda x: f"{x[:4]}-{datetime.strptime(x, '%Y-%m-%d').isocalendar()[1]}주차")              
                weekly_data = get_weekly_stats(acts, sel_week, v_type)      
                if weekly_data:
                    v_act, v_date, v_dist, v_pace, v_time, v_hr = f"{datetime.strptime(sel_week, '%Y-%m-%d').isocalendar()[1]}th WEEK", weekly_data['range'], weekly_data['total_dist'], weekly_data['avg_pace'], weekly_data['total_time'], weekly_data['avg_hr']
                    prev_w = get_weekly_stats(acts, (datetime.strptime(sel_week, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d"), v_type)
                    if prev_w and v_type == "Run": diff = float(v_dist) - float(prev_w['total_dist']); v_diff_str = f"({'+' if diff >= 0 else ''}{diff:.2f} km)"
            elif mode == "MONTHLY":
                months = sorted(list(set([ac['start_date_local'][:7] for ac in acts])), reverse=True)
                sel_month = st.selectbox("🗓️ 월 선택", months)
                monthly_data = get_monthly_stats(acts, f"{sel_month}-01", v_type)
                if monthly_data:
                    v_act, v_date, v_dist, v_pace, v_time, v_hr = datetime.strptime(f"{sel_month}-01", "%Y-%m-%d").strftime("%B").upper(), monthly_data['range'], monthly_data['total_dist'], monthly_data['avg_pace'], monthly_data['total_time'], monthly_data['avg_hr']
                    prev_m = get_monthly_stats(acts, (datetime.strptime(f"{sel_month}-01", "%Y-%m-%d") - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d"), v_type)
                    if prev_m and v_type == "Run": diff = float(v_dist) - float(prev_m['total_dist']); v_diff_str = f"({'+' if diff >= 0 else ''}{diff:.2f} km)"
        else:
            st.info("현재 분석할 수 있는 활동 데이터가 없습니다.")

    with st.expander("🎨 2. 디자인 및 텍스트 수정", expanded=False):
        c_txt1, c_txt2 = st.columns(2)
        with c_txt1:
            v_act = st.text_input("활동명", v_act)
            if v_type not in ["WeightTraining", "Workout"]: v_dist = st.text_input("거리 km", v_dist); v_pace = st.text_input("페이스", v_pace)
            else: v_memo = st.text_input("운동 메모", placeholder="예: 풀업 5x10")
        with c_txt2: v_date, v_time, v_hr = st.text_input("날짜", v_date), st.text_input("시간", v_time), st.text_input("심박 bpm", v_hr)

        st.markdown("---")
        COLOR_OPTS = {"Black": "#000000", "Yellow": "#FFD700", "White": "#FFFFFF", "Orange": "#FF4500", "Blue": "#00BFFF", "Grey": "#AAAAAA"}
        
        # --- 템플릿 적용 로직 ---
        if mode == "DAILY":
            temp_sel = st.selectbox("템플릿 적용 (DAILY 전용)", ["매거진 좌측 (Magazine)", "하단 미니멀 (Minimal)", "중앙 집중 (Center)", "수동 설정 (Custom)"])
            if temp_sel != "수동 설정 (Custom)":
                if temp_sel == "매거진 좌측 (Magazine)":
                    box_orient, sel_font, rx, ry, rw, rh, box_alpha = "Vertical", "BlackHanSans", 80, 1150, 450, 650, 120
                elif temp_sel == "하단 미니멀 (Minimal)":
                    box_orient, sel_font, rx, ry, rw, rh, box_alpha = "Horizontal", "Bangers", 40, 1600, 1000, 280, 80
                elif temp_sel == "중앙 집중 (Center)":
                    box_orient, sel_font, rx, ry, rw, rh, box_alpha = "Horizontal", "Lacquer", 40, 850, 1000, 350, 150
                
                c_col1, c_col2 = st.columns(2)
                with c_col1: m_color = COLOR_OPTS[st.selectbox("포인트 컬러", list(COLOR_OPTS.keys()), index=1)]
                with c_col2: sub_color = COLOR_OPTS[st.selectbox("서브 컬러", list(COLOR_OPTS.keys()), index=2)]
                show_vis, show_box, use_shadow, border_thick, vis_sz_adj, vis_alpha, logo_sz = True, True, True, 0, 180, 255, 60
            else:
                is_custom = True
        
        # 수동 설정 모드이거나 WEEKLY/MONTHLY 인 경우
        if mode != "DAILY" or (mode == "DAILY" and temp_sel == "수동 설정 (Custom)"):
            c_tog1, c_tog2 = st.columns(2)
            with c_tog1: show_vis, show_box = st.toggle("지도/그래프", True), st.toggle("데이터 박스", True)
            with c_tog2: use_shadow, border_thick = st.toggle("그림자 효과", True), st.slider("테두리 두께", 0, 50, 0)
            c_col1, c_col2 = st.columns(2)
            with c_col1: m_color = COLOR_OPTS[st.selectbox("포인트 컬러", list(COLOR_OPTS.keys()), index=1)]
            with c_col2: sub_color = COLOR_OPTS[st.selectbox("서브 컬러", list(COLOR_OPTS.keys()), index=2)]
            c_opt1, c_opt2 = st.columns(2)
            with c_opt1: box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], index=0 if mode=="DAILY" else 1, horizontal=True)     
            with c_opt2: sel_font = st.selectbox("폰트", ["BlackHanSans", "KirangHaerang", "Lacquer", "Condiment", "Bangers", "BagelFatOne"], index=2 if v_type in ["WeightTraining", "Workout"] else 4)
            c_pos1, c_pos2 = st.columns(2)
            with c_pos1: rx, rw = st.number_input("박스 X", 0, 1080, 40 if box_orient=="Horizontal" else 80), st.number_input("박스 너비", 100, 1080, 1000 if box_orient=="Horizontal" else 450)
            with c_pos2: ry, rh = st.number_input("박스 Y", 0, 1920, 250 if box_orient=="Horizontal" else 1200), st.number_input("박스 높이", 100, 1920, 350 if box_orient=="Horizontal" else 650)
            box_alpha, vis_sz_adj, vis_alpha, logo_sz = st.slider("박스 투명도", 0, 255, 100), st.slider("지도/그래프 크기", 50, 1080, 180 if mode=="DAILY" else 1080), st.slider("투명도", 0, 255, 255), st.slider("로고 크기", 30, 200, 60)

    st.markdown("---")
    st.subheader("🖼️ 미리보기 및 저장")
    if (mode == "DAILY" and a) or (mode == "WEEKLY" and weekly_data) or (mode == "MONTHLY" and monthly_data):
        try:
            CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
            f_t, f_d, f_n, f_l = load_font(sel_font, 70), load_font(sel_font, 30), load_font(sel_font, 50), load_font(sel_font, 25)
            canvas = make_smart_collage(bg_files, (CW, CH)) if bg_files else Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
            overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            
            items = [("", v_time, ""), ("", f"{v_hr} bpm", "")] if v_type in ["WeightTraining", "Workout"] else [("", f"{v_dist} km", v_diff_str), ("", v_pace, ""), ("", v_time, ""), ("", f"{v_hr} bpm", "")]
            if v_type in ["WeightTraining", "Workout"] and v_memo: items.append(("", v_memo, ""))
            if border_thick > 0: draw.rectangle([(0, 0), (CW-1, CH-1)], outline=m_color, width=border_thick)
            
            if show_box:
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
                if box_orient == "Vertical":
                    draw_styled_text(draw, (rx + 40, ry + 30), v_act, f_t, m_color, shadow=use_shadow)
                    draw_styled_text(draw, (rx + 40, ry + 110), v_date, f_d, "#AAAAAA", shadow=use_shadow)
                    if mode in ["WEEKLY", "MONTHLY"] and v_type == "Run" and (d := weekly_data if mode=="WEEKLY" else monthly_data) and d.get('other_count',0) > 0:
                        dumb_icon = get_icon_pil("dumbbell", size=(25, 25))
                        if dumb_icon:
                            c_icon = colorize_icon(dumb_icon, m_color); overlay.paste(c_icon, (rx + 40, ry + 155), c_icon)
                            draw_styled_text(draw, (rx + 70, ry + 157), f"{d['other_count']} sessions / {int(d['other_total_time'])} min", f_l, m_color, shadow=use_shadow)
                        else: draw_styled_text(draw, (rx + 40, ry + 157), f"{d['other_count']} sessions / {int(d['other_total_time'])} min", f_l, m_color, shadow=use_shadow)
                    
                    y_c = ry + 200
                    for _, val, diff in items:
                        draw_styled_text(draw, (rx + 40, y_c + 15), val.lower(), f_n, sub_color, shadow=use_shadow)
                        if diff: draw_styled_text(draw, (rx + 230, y_c + 15), diff, f_l, m_color, shadow=use_shadow)
                        y_c += 95
                else: 
                    if mode in ["WEEKLY", "MONTHLY"] and v_type == "Run" and (d := weekly_data if mode=="WEEKLY" else monthly_data) and d.get('other_count',0) > 0:
                        dumb_icon = get_icon_pil("dumbbell", size=(25, 25))
                        if dumb_icon:
                            c_icon = colorize_icon(dumb_icon, m_color); overlay.paste(c_icon, (rx + 25, ry + 25), c_icon)
                            draw_styled_text(draw, (rx + 55, ry + 27), f"{d['other_count']} sessions / {int(d['other_total_time'])} min", f_l, m_color, shadow=use_shadow)
                        else: draw_styled_text(draw, (rx + 25, ry + 27), f"{d['other_count']} sessions / {int(d['other_total_time'])} min", f_l, m_color, shadow=use_shadow)
                    
                    draw_styled_text(draw, (rx + (rw-draw.textlength(v_act, f_t))//2, ry+35), v_act, f_t, m_color, shadow=use_shadow)
                    draw_styled_text(draw, (rx + (rw-draw.textlength(v_date, f_d))//2, ry+110), v_date, f_d, "#AAAAAA", shadow=use_shadow)
                    sec_w = rw // len(items) if len(items) > 0 else rw
                    for i, (_, val, diff) in enumerate(items):
                        cx = rx + (i * sec_w) + (sec_w // 2)
                        draw_styled_text(draw, (cx - draw.textlength(val.lower(), f_n)//2, ry+175), val.lower(), f_n, sub_color, shadow=use_shadow)
                        if diff: draw_styled_text(draw, (cx - draw.textlength(diff, f_l)//2, ry+230), diff, f_l, m_color, shadow=use_shadow)

                if mode == "DAILY" and (daily_icon := get_icon_pil("dumbbell" if v_type in ["WeightTraining", "Workout"] else "run", size=(60, 60))):
                    c_icon = colorize_icon(daily_icon, m_color); overlay.paste(c_icon, (int(rx + rw - 80), int(ry + rh - 80)), c_icon)
                            
            if show_vis:
                vis_layer = None
                if user_graph_file:
                    user_img = Image.open(user_graph_file).convert("RGBA")
                    vis_layer = user_img.resize((vis_sz_adj, int(vis_sz_adj * user_img.height / user_img.width)), Image.Resampling.LANCZOS)
                    vis_layer.putalpha(vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255)))
                elif mode == "DAILY" and v_type not in ["WeightTraining", "Workout"] and a and a.get('map', {}).get('summary_polyline'):
                    pts = polyline.decode(a['map']['summary_polyline'])
                    if pts:
                        vis_layer = Image.new("RGBA", (vis_sz_adj, vis_sz_adj), (0,0,0,0)); m_draw = ImageDraw.Draw(vis_layer)
                        lats, lons = zip(*pts)
                        def tr(la, lo): return 15+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz_adj-30), (vis_sz_adj-15)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz_adj-30)
                        m_draw.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, vis_alpha), width=6)
                elif mode in ["WEEKLY", "MONTHLY"] and (d_obj := weekly_data if mode == "WEEKLY" else monthly_data):
                    chart_img = create_bar_chart(d_obj['dists'], m_color, mode=mode, labels=d_obj.get('labels'))
                    vis_layer = chart_img.resize((vis_sz_adj, int(chart_img.size[1]*(vis_sz_adj/chart_img.size[0]))), Image.Resampling.LANCZOS)
                    vis_layer.putalpha(vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255)))

                if vis_layer:
                    m_pos = (rx, max(5, ry - vis_layer.height - 20)) if box_orient == "Vertical" else ((CW - vis_layer.width) // 2, CH - vis_layer.height - 50)
                    overlay.paste(vis_layer, (int(m_pos[0]), int(m_pos[1])), vis_layer)

            if log_file:
                ls, margin = logo_sz, 20
                l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (ls, ls))
                mask = Image.new('L', (ls, ls), 0); ImageDraw.Draw(mask).ellipse((0, 0, ls, ls), fill=255); l_img.putalpha(mask)
                overlay.paste(l_img, (int(rx + rw - ls - margin), int(ry + margin)), l_img)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, use_container_width=True)
            
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95); img_bytes = buf.getvalue()
            img_64 = base64.b64encode(img_bytes).decode()

            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                components.html(f"""<div style="margin-bottom: 10px;"><button onclick="share()" style="width:100%; padding:12px; background: linear-gradient(45deg, #405de6, #5851db, #833ab4, #c13584, #e1306c, #fd1d1d); color:white; border-radius:8px; border:none; cursor:pointer; font-weight:bold; font-size:16px;">📲 공유</button></div><script>async function share() {{ try {{ const file = new File([await (await fetch('data:image/jpeg;base64,{img_64}')).blob()], 'run_record.jpg', {{type: 'image/jpeg'}}); if (navigator.share) await navigator.share({{files: [file], title: 'TITAN BOY RUN'}}); }} catch (e) {{}} }}</script>""", height=65)
            with c_btn2:
                st.download_button(label=f"📸 {mode} 저장", data=img_bytes, file_name=f"{mode.lower()}.jpg", use_container_width=True)
            
        except Exception as e:
            st.error(f"렌더링 오류 발생: {e}")
