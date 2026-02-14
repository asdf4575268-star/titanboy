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

# --- [2. 유틸리티 함수 (기존 로직 동일)] ---
def logout_and_clear():
    st.cache_data.clear(); st.cache_resource.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

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

def create_bar_chart(data, color_hex):
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    fig, ax = plt.subplots(figsize=(10, 4), dpi=150)
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    bars = ax.bar(days, data, color=color_hex, width=0.6)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='x', colors='white', labelsize=14); ax.tick_params(axis='y', left=False, labelleft=False)
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

# --- [3. 인증 및 데이터 로드] ---
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

# --- [4. 수기 입력창만 사이드바로 이동] ---
with st.sidebar:
    st.header("✍️ MANUAL EDIT")
    v_act_input = st.text_input("활동명")
    v_date_input = st.text_input("날짜")
    v_dist_input = st.text_input("거리(km)")
    v_time_input = st.text_input("시간")
    v_pace_input = st.text_input("페이스(분/km)")
    v_hr_input = st.text_input("심박(bpm)")

# --- [5. 메인 레이아웃 구성] ---
col_main, col_design = st.columns([2, 1], gap="medium")

with col_main:
    st.title("TITAN BOY")
    
    # 인증 상태 및 로그아웃 버튼
    auth_col, logout_col = st.columns([3, 1])
    with auth_col:
        if st.session_state['access_token']: st.success("✅ Strava 연결됨")
        else: st.link_button("🚀 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    with logout_col:
        if st.session_state['access_token']: st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)

    st.subheader("📝 ACTIVITY & PREVIEW")
    mode = st.radio("모드", ["DAILY", "WEEKLY"], horizontal=True, label_visibility="collapsed")
    
    # 파일 업로드 (원래 그대로 좌측)
    bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("🔘 원형 로고", type=['jpg','jpeg','png'])
    
    # 활동 선택 (원래 그대로 좌측)
    v_act, v_date, v_dist, v_time, v_pace, v_hr, weekly_data, a = "RUNNING", "2026-02-14", "0.00", "00:00:00", "0'00\"", "0", None, None
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
        else:
            weekly_data = get_weekly_stats(acts, a['start_date_local'][:10])
            if weekly_data: v_act, v_date, v_dist, v_time, v_pace, v_hr = "WEEKLY RUN", weekly_data['range'], weekly_data['total_dist'], weekly_data['total_time'], weekly_data['avg_pace'], weekly_data['avg_hr']

    # 수기 입력값이 있으면 우선 적용
    v_act = v_act_input if v_act_input else v_act
    v_date = v_date_input if v_date_input else v_date
    v_dist = v_dist_input if v_dist_input else v_dist
    v_time = v_time_input if v_time_input else v_time
    v_pace = v_pace_input if v_pace_input else v_pace
    v_hr = v_hr_input if v_hr_input else v_hr

with col_design:
    st.header("🎨 DESIGN")
    COLOR_OPTIONS = {"Garmin Yellow": "#FFD700", "Pure White": "#FFFFFF", "Neon Orange": "#FF4500", "Electric Blue": "#00BFFF", "Soft Grey": "#AAAAAA"}
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color, sub_color = COLOR_OPTIONS[st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()))], COLOR_OPTIONS[st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)]
    
    CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1080)
    rx = st.number_input("X 위치", 0, 1080, 70)
    ry = st.number_input("Y 위치", 0, 1920, 1250 if mode=="DAILY" else 750)
    rw = st.number_input("박스 너비", 100, 1080, 940 if box_orient=="Horizontal" else 450)
    rh = st.number_input("박스 높이", 100, 1920, 260 if box_orient=="Horizontal" else 630)
    box_alpha = st.slider("박스 투명도", 0, 255, 100)
    vis_sz = st.slider("지도/그래프 크기", 50, 1080, 200 if mode=="DAILY" else 1080)
    vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 150 if mode=="DAILY" else 220)
    if mode == "WEEKLY": g_y_off = st.slider("그래프 상단 여백", 0, 500, 50)

# --- [6. 렌더링 엔진 (기존 로직 100% 동일)] ---
try:
    f_t, f_d, f_n, f_l = load_font(sel_font, 70), load_font(sel_font, 20), load_font(sel_font, 45), load_font(sel_font, 22)
    
    if bg_files:
        canvas = ImageOps.fit(ImageOps.exif_transpose(Image.open(bg_files[0])).convert("RGBA"), (CW, CH))
    else:
        canvas = Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
    
    overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
    
    vis_layer = None
    if mode == "DAILY" and a and a.get('map', {}).get('summary_polyline'):
        pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
        vis_layer = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); m_draw = ImageDraw.Draw(vis_layer)
        def tr(la, lo): return 15+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-30), (vis_sz-15)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-30)
        m_draw.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, vis_alpha), width=4)
    elif mode == "WEEKLY" and weekly_data:
        chart_img = create_bar_chart(weekly_data['dists'], m_color)
        w_p = (vis_sz / float(chart_img.size[0])); vis_layer = chart_img.resize((vis_sz, int(chart_img.size[1]*w_p)), Image.Resampling.LANCZOS)
        alpha_mask = vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255)); vis_layer.putalpha(alpha_mask)
        overlay.paste(vis_layer, ((CW - vis_layer.width)//2, g_y_off), vis_layer)

    items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]

    if box_orient == "Vertical":
        draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
        if mode == "DAILY" and vis_layer: 
            overlay.paste(vis_layer, (rx + rw - vis_layer.width - 20, ry + 20), vis_layer)
        draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
        draw.text((rx+40, ry+130), v_date, font=f_d, fill="#AAAAAA")
        y_c = ry + 210
        for lab, val in items:
            draw.text((rx+40, y_c), lab.lower(), font=f_l, fill="#AAAAAA")
            draw.text((rx+40, y_c+25), val.lower() if "bpm" in val or "km" in val else val, font=f_n, fill=sub_color)
            y_c += 110
    else:
        cur_rw = 1080; cur_rx = 0
        draw.rectangle([cur_rx, ry, cur_rx + cur_rw, ry + rh], fill=(0,0,0,box_alpha))
        if mode == "DAILY" and vis_layer:
            overlay.paste(vis_layer, (20, ry + (rh - vis_layer.height)//2), vis_layer)
        t_w = draw.textlength(v_act, font=f_t); d_w = draw.textlength(v_date, font=f_d)
        draw.text(((cur_rw - t_w) // 2, ry + 35), v_act, font=f_t, fill=m_color)
        draw.text(((cur_rw - d_w) // 2, ry + 125), v_date, font=f_d, fill="#AAAAAA")
        sec_w = cur_rw // 4
        for i, (lab, val) in enumerate(items):
            center_x = (i * sec_w) + (sec_w // 2)
            v_str = val.lower() if "bpm" in val or "km" in val else val
            l_w = draw.textlength(lab.lower(), font=f_l); v_w = draw.textlength(v_str, font=f_n)
            draw.text((center_x - (l_w // 2), ry + 175), lab.lower(), font=f_l, fill="#AAAAAA")
            draw.text((center_x - (v_w // 2), ry + 205), v_str, font=f_n, fill=sub_color)

    if log_file:
        ls = 100; l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (ls, ls))
        mask = Image.new('L', (ls, ls), 0); ImageDraw.Draw(mask).ellipse((0, 0, ls, ls), fill=255); l_img.putalpha(mask)
        l_pos = (1080 - ls - 25, ry + 25) if box_orient == "Horizontal" else (rx + rw - ls - 25, ry + rh - ls - 25)
        overlay.paste(l_img, l_pos, l_img)

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    
    # [중요] 미리보기를 좌측(col_main) 하단에 배치
    with col_main:
        st.image(final, use_container_width=True)
        buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
        st.download_button(f"📸 {mode} DOWNLOAD", buf.getvalue(), f"{mode.lower()}.jpg", use_container_width=True)

except Exception as e:
    with col_main: st.info("데이터를 불러오거나 사진을 업로드하면 대시보드가 생성됩니다.")
