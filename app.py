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

def draw_styled_text(draw, pos, text, font, fill, shadow=True):
    if shadow:
        # 그림자 위치를 (3, 3)으로 설정하여 약간의 입체감을 줍니다.
        draw.text((pos[0] + 3, pos[1] + 3), text, font=font, fill=(0, 0, 0, 180))
    draw.text(pos, text, font=font, fill=fill)
@st.cache_resource
def load_font(font_type, size):
    # 원하는 폰트의 GitHub 또는 구글 폰트 원본 주소를 여기에 추가하세요.
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Regular.ttf",
        "KirangHaerang": "https://github.com/google/fonts/raw/main/ofl/kiranghaerang/KirangHaerang-Regular.ttf",
        "JollyLodger": "https://github.com/google/fonts/raw/main/ofl/jollylodger/JollyLodger-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf",
        "IndieFlower": "https://github.com/google/fonts/raw/main/ofl/indieflower/IndieFlower-Regular.ttf"
    }
    
    f_path = f"font_{font_type}_{int(size)}.ttf"
    if not os.path.exists(f_path):
        font_url = fonts.get(font_type, fonts["BlackHanSans"])
        r = requests.get(font_url)
        with open(f_path, "wb") as f:
            f.write(r.content)
            
    return ImageFont.truetype(f_path, int(size))
            
    return ImageFont.truetype(f_path, int(size))

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
        next_month = first_day.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
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

    # [핵심] 사진 개수에 따라 행/열을 동적으로 결정
    # 최대한 정사각형에 가깝거나 세로로 긴 매거진 비율 유지
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
    
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        
        # 기본 좌표 계산
        x0 = int(c * tw / cols)
        y0 = int(r * th / rows)
        
        # 마지막 줄 사진들이 비어 보이지 않게 너비를 자동 확장
        # (예: 3장일 때 아래줄에 혼자 있는 사진은 가로로 꽉 채움)
        current_row_count = n % cols if (r == rows - 1 and n % cols != 0) else cols
        if r == rows - 1 and n % cols != 0:
            row_tw = tw / current_row_count
            x0 = int((i % cols) * row_tw)
            x1 = int(((i % cols) + 1) * row_tw)
        else:
            x1 = int((c + 1) * tw / cols)
            
        y1 = int((r + 1) * th / rows)
        
        cell_w = x1 - x0
        cell_h = y1 - y0
        
        resized_img = ImageOps.fit(img, (cell_w, cell_h), Image.Resampling.LANCZOS)
        canvas.paste(resized_img, (x0, y0))

    return canvas

# --- [3. 레이아웃 선언 (최상단 고정)] ---
col_main, col_design = st.columns([1.6, 1], gap="medium")

# --- [4. 인증 및 데이터 연동 (모바일 끊김 방지 최적화)] ---
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# 모바일 리프레시 대비: URL 파라미터에 토큰이 있다면 세션으로 복구
if "token" in st.query_params:
    st.session_state['access_token'] = st.query_params["token"]

query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    try:
        res = requests.post(
            "https://www.strava.com/oauth/token", 
            data={
                "client_id": CLIENT_ID, 
                "client_secret": CLIENT_SECRET, 
                "code": query_params["code"], 
                "grant_type": "authorization_code"
            }
        ).json()
        if 'access_token' in res:
            st.session_state['access_token'] = res['access_token']
            # URL에 토큰을 저장하여 모바일 브라우저 재시작 시 자동 로그인 유지
            st.query_params["token"] = res['access_token']
            st.rerun()
    except Exception as e:
        st.error(f"인증 오류: {e}")

acts = [] 
if st.session_state['access_token']:
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
    # 매번 API를 호출하지 않도록 세션에 활동 데이터 캐싱
    if 'cached_acts' not in st.session_state:
        r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers=headers)
        if r.status_code == 200:
            st.session_state['cached_acts'] = r.json()
        elif r.status_code == 401: # 토큰 만료 대응
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()
    acts = st.session_state.get('cached_acts', [])

# --- [5. 메인 화면 구성] ---
with col_main:
    st.title("TITAN BOY")
    
    v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", "2026-02-15", "0.00", "00:00:00", "0'00\"", "0"
    weekly_data, monthly_data, a = None, None, None

    if not st.session_state['access_token']:
        st.link_button("🚀 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        # 로그아웃 시 모든 데이터 초기화
        if st.button("🔓 로그아웃", use_container_width=True):
            logout_and_clear()
            
        bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
        log_file = st.file_uploader("🔘 원형 로고", type=['jpg','jpeg','png'])
        
        mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True, key="main_mode_sel")
        
        if acts:
            if mode == "DAILY":
                act_opts = [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts]
                sel_act = st.selectbox("🏃 활동 선택", act_opts)
                a = acts[act_opts.index(sel_act)]
                if a:
                    v_act = a['name'].upper()
                    v_date = a['start_date_local'][:10].replace('-', '.')
                    d_km = a.get('distance', 0)/1000; m_s = a.get('moving_time', 0)
                    v_dist, v_time = f"{d_km:.2f}", f"{m_s//3600:02d}:{(m_s%3600)//60:02d}:{m_s%60:02d}"
                    v_pace = f"{int((m_s/d_km)//60)}'{int((m_s/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
                    v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
            
            elif mode == "WEEKLY":
                weeks = sorted(list(set([(datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d") - timedelta(days=datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d").weekday())).strftime('%Y.%m.%d') for ac in acts])), reverse=True)
                sel_week = st.selectbox("📅 주차 선택", weeks)
                weekly_data = get_weekly_stats(acts, sel_week.replace('.','-'))
                if weekly_data:
                    dt_t = datetime.strptime(sel_week.replace('.','-'), "%Y-%m-%d")
                    w_num = dt_t.isocalendar()[1]
                    sfx = "TH" if 11 <= w_num <= 13 else {1: "ST", 2: "ND", 3: "RD"}.get(w_num % 10, "TH")
                    v_act, v_date = f"{w_num}{sfx} WEEK", weekly_data['range']
                    v_dist, v_time, v_pace, v_hr = weekly_data['total_dist'], weekly_data['total_time'], weekly_data['avg_pace'], weekly_data['avg_hr']

            elif mode == "MONTHLY":
                months = sorted(list(set([ac['start_date_local'][:7] for ac in acts])), reverse=True)
                sel_month = st.selectbox("🗓️ 월 선택", months)
                monthly_data = get_monthly_stats(acts, f"{sel_month}-01")
                if monthly_data:
                    v_act = datetime.strptime(f"{sel_month}-01", "%Y-%m-%d").strftime("%B").upper()
                    v_date, v_dist, v_time, v_pace, v_hr = monthly_data['range'], monthly_data['total_dist'], monthly_data['total_time'], monthly_data['avg_pace'], monthly_data['avg_hr']

# --- [6. 디자인 창 구성] ---
with col_design:
    st.header("🎨 DESIGN")
    with st.expander("✍️ 텍스트 수정"):
        v_act = st.text_input("활동명", v_act)
        v_date = st.text_input("날짜", v_date)
        v_dist = st.text_input("거리 km", v_dist)
        v_time = st.text_input("시간", v_time)
        v_pace = st.text_input("페이스", v_pace)
        v_hr = st.text_input("심박 bpm", v_hr)

    with st.expander("💄 매거진 스타일", expanded=True):
        show_vis = st.toggle("지도/그래프 표시", value=True)
        show_box = st.toggle("데이터 박스 표시", value=True)
        use_shadow = st.toggle("글자 그림자 효과", value=True)
        
        COLOR_OPTS = {"Yellow": "#FFD700", "White": "#FFFFFF", "Black": "#000000", "Grey": "#AAAAAA"}
        m_color = COLOR_OPTS[st.selectbox("포인트 컬러", list(COLOR_OPTS.keys()))]
        sub_color = COLOR_OPTS[st.selectbox("서브 컬러", list(COLOR_OPTS.keys()), index=1)]
        box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
        sel_font = st.selectbox("폰트", ["BlackHanSans", "Sunflower", "Orbit", "KirangHaerang", "JollyLodger", "Lacquer"])

    with st.expander("📍 위치/크기 조절"):
        rx = st.number_input("박스 X", 0, 1080, 70)
        ry = st.number_input("박스 Y", 0, 1920, 1250)
        rw = st.number_input("박스 너비", 100, 1080, 450)
        rh = st.number_input("박스 높이", 100, 1920, 600)
        box_alpha = st.slider("박스 투명도", 0, 255, 110)
        vis_sz_adj = st.slider("지도/그래프 크기", 50, 1080, 200)
        vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 240)
