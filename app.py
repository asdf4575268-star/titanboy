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
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

# 모바일 친화적 페이지 설정
logo = Image.open("logo.png")
st.set_page_config(
    layout="centered",
    page_title="TITAN BOY",
    page_icon=logo,
    initial_sidebar_state="collapsed"
)
mpl.use("Agg")

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
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf"
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
                    chart_val = dist if target_type == "Run" else time_min
                    weekly_dist[act_date.weekday()] += chart_val
                    total_dist += dist; total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): hr_sum += act.get('average_heartrate'); hr_count += 1
                elif act.get('type') in ['WeightTraining', 'Workout']:
                    other_count += 1
                    other_total_time += act.get('moving_time', 0) / 60
                    
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        avg_pace_str = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\"" if target_type == "Run" else "-"
        dist_str = f"{total_dist:.2f}" if target_type == "Run" else "-"
        return {"dists": weekly_dist, "total_dist": dist_str, "total_time": f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}", "avg_pace": avg_pace_str, "avg_hr": str(avg_hr), "range": f"{start_of_week.strftime('%m.%d')} - {end_of_week.strftime('%m.%d')}", "other_count": other_count, "other_total_time": other_total_time}
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
                    chart_val = dist if target_type == "Run" else time_min
                    monthly_dist[act_date.day - 1] += chart_val
                    total_dist += dist; total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): hr_sum += act.get('average_heartrate'); hr_count += 1
                elif act.get('type') in ['WeightTraining', 'Workout']:
                    other_count += 1
                    other_total_time += act.get('moving_time', 0) / 60
                    
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        avg_pace_str = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\"" if target_type == "Run" else "-"
        dist_str = f"{total_dist:.2f}" if target_type == "Run" else "-"
        return {"dists": monthly_dist, "total_dist": dist_str, "total_time": f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}", "avg_pace": avg_pace_str, "avg_hr": str(avg_hr), "range": first_day.strftime('%Y.%m'), "labels": [str(i+1) for i in range(num_days)], "other_count": other_count, "other_total_time": other_total_time}
    except: return None

def create_bar_chart(data, color_hex, mode="WEEKLY", labels=None, font_path=None):
    if mode == "WEEKLY": labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    x_pos = np.arange(len(labels))
    prop = font_manager.FontProperties(fname=font_path) if font_path else None
    fig, ax = plt.subplots(figsize=(10, 5.0), dpi=150)
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    bars = ax.bar(x_pos, data, color=color_hex, width=0.6)
    ax.set_xticks(x_pos); ax.set_xticklabels(labels)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='x', colors='white')
    if prop:
        for label in ax.get_xticklabels(): label.set_fontproperties(prop); label.set_fontsize(10 if mode=="MONTHLY" else 14)
    ax.tick_params(axis='y', left=False, labelleft=False)
    plt.tight_layout(); buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); buf.seek(0); plt.close(fig)
    return Image.open(buf)

def make_smart_collage(files, target_size):
    tw, th = target_size
    imgs = []
    for f in files:
        try:
            img = Image.open(f)
            img = ImageOps.exif_transpose(img)
            imgs.append(img.convert("RGBA"))
        except:
            continue
    if not imgs: 
        return Image.new("RGBA", (tw, th), (30, 30, 30, 255))
    
    n = len(imgs)
    if n == 1:
        return ImageOps.fit(imgs[0], (tw, th), Image.Resampling.LANCZOS)

    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
    
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        x0 = int(c * tw / cols)
        y0 = int(r * th / rows)
        
        current_row_count = n % cols if (r == rows - 1 and n % cols != 0) else cols
        if r == rows - 1 and n % cols != 0:
            row_tw = tw / current_row_count
            x0 = int((i % cols) * row_tw)
            x1 = int(((i % cols) + 1) * row_tw)
        else:
            x1 = int((c + 1) * tw / cols)
            
        y1 = int((r + 1) * th / rows)
        cell_w, cell_h = x1 - x0, y1 - y0
        resized_img = ImageOps.fit(img, (cell_w, cell_h), Image.Resampling.LANCZOS)
        canvas.paste(resized_img, (x0, y0))

    return canvas

# --- [3. 인증 및 데이터 연동 - 에러 방지 및 자동 로그인] ---
DB_PATH = "archive_prism_total_v5.db"
acts = [] 

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS strava_tokens (
                id INTEGER PRIMARY KEY, 
                access_token TEXT, 
                refresh_token TEXT, 
                expires_at INTEGER
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"DB 초기화 실패: {e}")

init_db()

def handle_token_db(mode="load", data=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        if mode == "save" and data:
            cur.execute("DELETE FROM strava_tokens")
            cur.execute("INSERT INTO strava_tokens (access_token, refresh_token, expires_at) VALUES (?, ?, ?)",
                        (data['access_token'], data['refresh_token'], data['expires_at']))
            conn.commit()
        elif mode == "load":
            cur.execute("SELECT access_token, refresh_token, expires_at FROM strava_tokens LIMIT 1")
            row = cur.fetchone()
            conn.close()
            return row
        conn.close()
    except:
        return None

if 'access_token' not in st.session_state:
    saved = handle_token_db("load")
    if saved:
        a_token, r_token, exp_at = saved
        if time.time() > (exp_at - 1800):
            try:
                res = requests.post("https://www.strava.com/oauth/token", data={
                    "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                    "grant_type": "refresh_token", "refresh_token": r_token
                }).json()
                if 'access_token' in res:
                    handle_token_db("save", res)
                    st.session_state['access_token'] = res['access_token']
            except: pass
        else:
            st.session_state['access_token'] = a_token

if "code" in st.query_params:
    code = st.query_params["code"]
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": code, "grant_type": "authorization_code"
    }).json()
    if 'access_token' in res:
        handle_token_db("save", res)
        st.session_state['access_token'] = res['access_token']
        st.query_params.clear()
        st.rerun()

if st.session_state.get('access_token'):
    if not st.session_state.get('cached_acts'):
        headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
        r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers=headers)
        if r.status_code == 200:
            st.session_state['cached_acts'] = r.json()
        elif r.status_code == 401: 
            st.session_state.clear()
            st.rerun()
    acts = st.session_state.get('cached_acts', [])

# --- [4. 메인 화면 구성 및 UI 레이아웃] ---
def get_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_base64 = get_base64("logo.png")

st.markdown("""
<style>
.header-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
}
.header-wrap h1 {
    margin: 0;
    letter-spacing: -1px;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="header-wrap">
        <img src="data:image/png;base64,{logo_base64}" width="90">
        <h1>TITAN BOY</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# 변수 초기화
bg_files = [] 
log_file = None
user_graph_file = None
mode = "DAILY"
v_act, v_date, v_dist, v_pace, v_time, v_hr, v_type = "RUNNING", "2026.02.16", "0.00", "00:00:00", "0'00\"", "0", "Run"
v_memo = "" 
weekly_data, monthly_data, a = None, None, None
v_diff_str = ""

if not st.session_state.get('access_token'):
    auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
                f"&response_type=code&redirect_uri={ACTUAL_URL}"
                f"&scope=read,activity:read_all&approval_prompt=force")
    st.link_button("🚀 Strava 연동하기", auth_url, use_container_width=True)
else:
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("🔓 로그아웃", use_container_width=True):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    # --- Section 1: 데이터 및 파일 업로드 ---
    with st.expander("📂 1. 데이터 및 사진 설정", expanded=True):
        st.markdown("**이미지 업로드**")
        bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
        
        c_up1, c_up2 = st.columns(2)
        with c_up1:
            log_file = st.file_uploader("🔘 로고", type=['jpg','jpeg','png'])
        with c_up2:
            user_graph_file = st.file_uploader("📈 그래프(선택)", type=['jpg','png','jpeg'], key="user_graph")
                
        st.markdown("---")
        st.markdown("**러닝 데이터 선택**")
        mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True, key="main_mode_sel")
        
        if mode in ["WEEKLY", "MONTHLY"]:
            target_type = st.radio("종목 선택", ["Run", "WeightTraining", "Workout"], horizontal=True, key="type_sel")
            v_type = target_type

        if acts:
            if mode == "DAILY":
                act_opts = [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts]
                sel_act = st.selectbox("🏃 활동 선택", act_opts)
                a = acts[act_opts.index(sel_act)]
                if a:
                    v_type = a.get('type', 'Run')
                    v_act = a['name'].upper()
                    dt_obj = datetime.strptime(a['start_date_local'][:19], "%Y-%m-%dT%H:%M:%S")
                    v_time_str = dt_obj.strftime("%I:%M %p").lower()
                    v_date = f"{a['start_date_local'][:10].replace('-', '.')} {v_time_str}"
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
                    v_act = f"{datetime.strptime(sel_week, '%Y-%m-%d').isocalendar()[1]}th WEEK"
                    v_date = weekly_data['range']
                    v_dist = weekly_data['total_dist']
                    v_pace = weekly_data['avg_pace']
                    v_time = weekly_data['total_time']
                    v_hr   = weekly_data['avg_hr']
                    
                    prev_week_str = (datetime.strptime(sel_week, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
                    prev_weekly_data = get_weekly_stats(acts, prev_week_str, v_type)
                    if prev_weekly_data and v_type == "Run":
                        diff_val = float(v_dist) - float(prev_weekly_data['total_dist'])
                        v_diff_str = f"({'+' if diff_val >= 0 else ''}{diff_val:.2f} km)"
            
            elif mode == "MONTHLY":
                months = sorted(list(set([ac['start_date_local'][:7] for ac in acts])), reverse=True)
                sel_month = st.selectbox("🗓️ 월 선택", months)
                monthly_data = get_monthly_stats(acts, f"{sel_month}-01", v_type)
                if monthly_data:
                    dt_t = datetime.strptime(f"{sel_month}-01", "%Y-%m-%d")
                    v_act = dt_t.strftime("%B").upper()
                    v_date, v_dist, v_time, v_pace, v_hr = monthly_data['range'], monthly_data['total_dist'], monthly_data['total_time'], monthly_data['avg_pace'], monthly_data['avg_hr']
                    
                    curr_date = datetime.strptime(f"{sel_month}-01", "%Y-%m-%d")
                    prev_month_date = (curr_date - timedelta(days=1)).replace(day=1)
                    prev_monthly_data = get_monthly_stats(acts, prev_month_date.strftime("%Y-%m-%d"), v_type)
                    if prev_monthly_data and v_type == "Run":
                        diff_val = float(v_dist) - float(prev_monthly_data['total_dist'])
                        v_diff_str = f"({'+' if diff_val >= 0 else ''}{diff_val:.2f} km)"

    # --- Section 2: 디자인 및 텍스트 수정 ---
    with st.expander("🎨 2. 디자인 및 텍스트 수정", expanded=False):
        st.markdown("**텍스트 수정**")
        c_txt1, c_txt2 = st.columns(2)
        with c_txt1:
            v_act = st.text_input("활동명", v_act)
            if v_type not in ["WeightTraining", "Workout"]:
                v_dist = st.text_input("거리 km", v_dist)
                v_pace = st.text_input("페이스", v_pace)
            else:
                v_memo = st.text_input("운동 메모 (선택)", placeholder="예: 풀업 5x10, 스쿼트 3x10 등")
        with c_txt2:
            v_date = st.text_input("날짜", v_date)
            v_time = st.text_input("시간", v_time)
            v_hr = st.text_input("심박 bpm", v_hr)

        st.markdown("---")
        st.markdown("**매거진 스타일 옵션**")
        c_tog1, c_tog2 = st.columns(2)
        with c_tog1:
            show_vis = st.toggle("지도/그래프 표시", value=True, key="sw_vis")
            show_box = st.toggle("데이터 박스 표시", value=True, key="sw_box")
        with c_tog2:
            use_shadow = st.toggle("글자 그림자 효과", value=True, key="sw_shadow")
            
        border_thick = st.slider("프레임 테두리 두께", 0, 50, 0)
        
        COLOR_OPTS = {"Black": "#000000", "Yellow": "#FFD700", "White": "#FFFFFF", "Orange": "#FF4500", "Blue": "#00BFFF", "Grey": "#AAAAAA"}
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            m_color = COLOR_OPTS[st.selectbox("포인트 컬러", list(COLOR_OPTS.keys()), index=1,  key="m_col_sel")]
        with c_col2:
            sub_color = COLOR_OPTS[st.selectbox("서브 컬러", list(COLOR_OPTS.keys()), index=2, key="s_col_sel")]

        default_idx = 0 if mode == "DAILY" else 1
        c_opt1, c_opt2 = st.columns(2)
        with c_opt1:
            box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], index=default_idx, horizontal=True, key=f"orient_{mode}")     
        with c_opt2:
            sel_font = st.selectbox("폰트", ["BlackHanSans", "KirangHaerang", "Lacquer"])

        st.markdown("**위치 및 크기 조절**")
        c_pos1, c_pos2 = st.columns(2)
        with c_pos1:
            rx = st.number_input("박스 X", 0, 1080, 40 if box_orient=="Horizontal" else 80)
            rw = st.number_input("박스 너비", 100, 1080, 1000 if box_orient=="Horizontal" else 450)
        with c_pos2:
            ry = st.number_input("박스 Y", 0, 1920, 250 if box_orient=="Horizontal" else 1200)
            rh = st.number_input("박스 높이", 100, 1920, 350 if box_orient=="Horizontal" else 650)
            
        box_alpha = st.slider("박스 투명도", 0, 255, 100)
        vis_sz_adj = st.slider("지도/그래프 크기", 50, 1080, 180 if mode=="DAILY" else 1080)
        vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 255)

    # --- Section 3: 미리보기 및 다운로드/공유 ---
    st.markdown("---")
    st.subheader("🖼️ 미리보기 및 저장")
    
    data_ready = (mode == "DAILY" and a) or (mode == "WEEKLY" and weekly_data) or (mode == "MONTHLY" and monthly_data)
    
    if data_ready:
        try:
            CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
            f_t, f_d, f_n, f_l = load_font(sel_font, 70), load_font(sel_font, 30), load_font(sel_font, 50), load_font(sel_font, 25)
            
            canvas = make_smart_collage(bg_files, (CW, CH)) if bg_files else Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
            overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            
            if v_type in ["WeightTraining", "Workout"]:
                items = [("", v_time, ""), ("", f"{v_hr} bpm", "")]
                if v_memo:
                    items.append(("", v_memo, ""))
            else:
                items = [("", f"{v_dist} km", v_diff_str), ("", v_pace, ""), ("", v_time, ""), ("", f"{v_hr} bpm", "")]
            
            if border_thick > 0:
                draw.rectangle([(0, 0), (CW-1, CH-1)], outline=m_color, width=border_thick)
            
            if show_box:
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
                if box_orient == "Vertical":
                    draw_styled_text(draw, (rx + 40, ry + 30), v_act, f_t, m_color, shadow=use_shadow)
                    draw_styled_text(draw, (rx + 40, ry + 110), v_date, f_d, "#AAAAAA", shadow=use_shadow)
                    y_c = ry + 200
                    for lab, val, diff in items:
                        # 라벨(lab) 출력 생략하고 값의 높이를 살짝 올려서 정렬
                        draw_styled_text(draw, (rx + 40, y_c + 15), val.lower(), f_n, sub_color, shadow=use_shadow)
                        if diff: 
                            draw_styled_text(draw, (rx + 230, y_c + 15), diff, f_l, m_color, shadow=use_shadow)
                        y_c += 95
                else: 
                    # 가로모드 왼쪽 상단 워크아웃 세션/시간 표시 (WEEKLY, MONTHLY)
                    if mode in ["WEEKLY", "MONTHLY"] and v_type == "Run":
                        d_data = weekly_data if mode == "WEEKLY" else monthly_data
                        if d_data and d_data.get('other_count', 0) > 0:
                            dumb_icon = get_icon_pil("dumbbell", size=(25, 25))
                            wo_text = f"{d_data['other_count']}sessions/{int(d_data['other_total_time'])}min"
                            if dumb_icon:
                                overlay.paste(dumb_icon, (rx + 25, ry + 25), dumb_icon)
                                draw_styled_text(draw, (rx + 55, ry + 27), wo_text, f_l, "#AAAAAA", shadow=use_shadow)
                            else:
                                draw_styled_text(draw, (rx + 25, ry + 27), wo_text, f_l, "#AAAAAA", shadow=use_shadow)
                    
                    title_w = draw.textlength(v_act, f_t)
                    draw_styled_text(draw, (rx + (rw-title_w)//2, ry+35), v_act, f_t, m_color, shadow=use_shadow)
                    draw_styled_text(draw, (rx + (rw-draw.textlength(v_date, f_d))//2, ry+110), v_date, f_d, "#AAAAAA", shadow=use_shadow)
                    sec_w = rw // len(items) if len(items) > 0 else rw
                    for i, (lab, val, diff) in enumerate(items):
                        cx = rx + (i * sec_w) + (sec_w // 2)
                        # 라벨(lab) 출력 생략
                        draw_styled_text(draw, (cx - draw.textlength(val.lower(), f_n)//2, ry+175), val.lower(), f_n, sub_color, shadow=use_shadow)
                        if diff: 
                            draw_styled_text(draw, (cx - draw.textlength(diff, f_l)//2, ry+230), diff, f_l, m_color, shadow=use_shadow)

                # --- [추가된 부분: 데일리 모드 전용 오른쪽 하단 아이콘] ---
                if mode == "DAILY":
                    daily_icon_name = "dumbbell" if v_type in ["WeightTraining", "Workout"] else "run"
                    daily_icon = get_icon_pil(daily_icon_name, size=(60, 60))
                    if daily_icon:
                        icon_x = int(rx + rw - 60 - 20)
                        icon_y = int(ry + rh - 60 - 20)
                        overlay.paste(daily_icon, (icon_x, icon_y), daily_icon)
                # -------------------------------------------------------------
                            
            if show_vis:
                vis_layer = None
                vis_sz = vis_sz_adj
                
                if user_graph_file:
                    user_img = Image.open(user_graph_file).convert("RGBA")
                    w_h_ratio = user_img.height / user_img.width
                    vis_layer = user_img.resize((vis_sz, int(vis_sz * w_h_ratio)), Image.Resampling.LANCZOS)
                    vis_layer.putalpha(vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255)))

                elif mode == "DAILY" and v_type not in ["WeightTraining", "Workout"] and a and a.get('map', {}).get('summary_polyline'):
                    pts = polyline.decode(a['map']['summary_polyline'])
                    if pts:
                        lats, lons = zip(*pts)
                        vis_layer = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); m_draw = ImageDraw.Draw(vis_layer)
                        def tr(la, lo): return 15+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-30), (vis_sz-15)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-30)
                        m_draw.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, vis_alpha), width=6)
                    
                elif mode in ["WEEKLY", "MONTHLY"] and (weekly_data or monthly_data):
                    d_obj = weekly_data if mode == "WEEKLY" else monthly_data
                    chart_img = create_bar_chart(d_obj['dists'], m_color, mode=mode, labels=d_obj.get('labels'), font_path=None)
                    target_h = int(CH * 0.7)
                    vis_layer = chart_img.resize((vis_sz, int(chart_img.size[1]*(vis_sz/chart_img.size[0]))), Image.Resampling.LANCZOS)
                    vis_layer.putalpha(vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255)))

                if vis_layer:
                    if box_orient == "Vertical": 
                        m_pos = (rx, max(5, ry - vis_layer.height - 20))
                    else: 
                        m_pos_x = (CW - vis_layer.width) // 2
                        m_pos_y = CH - vis_layer.height - 50                      
                        m_pos = (m_pos_x, m_pos_y)
                    overlay.paste(vis_layer, (int(m_pos[0]), int(m_pos[1])), vis_layer)

            if log_file:
                ls, margin = 100, 40
                l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (ls, ls))
                mask = Image.new('L', (ls, ls), 0); ImageDraw.Draw(mask).ellipse((0, 0, ls, ls), fill=255); l_img.putalpha(mask)
                overlay.paste(l_img, (CW - ls - margin, margin), l_img)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            
            st.image(final, use_container_width=True)
            
            buf = io.BytesIO()
            final.save(buf, format="JPEG", quality=95)
            img_bytes = buf.getvalue()
            img_64 = base64.b64encode(img_bytes).decode()

            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                share_btn_html = f"""
                    <div style="margin-bottom: 10px;">
                        <button onclick="share()" style="
                            width:100%; padding:12px; 
                            background: linear-gradient(45deg, #405de6, #5851db, #833ab4, #c13584, #e1306c, #fd1d1d);
                            color:white; border-radius:8px; border:none; 
                            cursor:pointer; font-weight:bold; font-size:16px;
                            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
                        ">
                            📲 공유
                        </button>
                    </div>
                    <script>
                    async function share() {{
                        try {{
                            const blob = await (await fetch('data:image/jpeg;base64,{img_64}')).blob();
                            const file = new File([blob], 'run_record.jpg', {{type: 'image/jpeg'}});
                            if (navigator.share) {{
                                await navigator.share({{
                                    files: [file],
                                    title: 'TITAN BOY RUN',
                                    text: '오늘의 운동 기록!'
                                }});
                            }} else {{
                                alert('현재 브라우저가 공유 기능을 지원하지 않습니다. 다운로드 버튼을 이용해주세요.');
                            }}
                        }} catch (e) {{
                            console.log('공유 취소 또는 오류:', e);
                        }}
                    }}
                    </script>
                """
                components.html(share_btn_html, height=65)
                
            with c_btn2:
                st.download_button(
                    label=f"📸 {mode} 저장", 
                    data=img_bytes, 
                    file_name=f"{mode.lower()}.jpg", 
                    use_container_width=True
                )
            
        except Exception as e:
            st.error(f"렌더링 오류 발생: {e}")

