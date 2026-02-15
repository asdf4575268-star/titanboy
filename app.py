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
    "PRIMARY": {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'}
}
CLIENT_ID, CLIENT_SECRET = API_CONFIGS["PRIMARY"]["ID"], API_CONFIGS["PRIMARY"]["SECRET"]
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

st.set_page_config(page_title="TITAN BOY", layout="wide")
mpl.use('Agg')

# --- [2. 유틸리티 함수] ---
def logout_and_clear():
    st.cache_data.clear(); st.cache_resource.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

@st.cache_resource
def load_font(font_type, size):
    fonts = {"BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf", "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf", "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf", "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf", "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Bold.ttf"}
    f_path = f"font_{font_type}_{int(size)}.ttf"
    if not os.path.exists(f_path):
        r = requests.get(fonts.get(font_type, fonts["BlackHanSans"])); open(f_path, "wb").write(r.content)
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
    imgs = [ImageOps.exif_transpose(Image.open(f).convert("RGBA")) for f in files[:10]]
    if not imgs: return Image.new("RGBA", (tw, th), (30, 30, 30, 255))
    if len(imgs) == 1: return ImageOps.fit(imgs[0], (tw, th))
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
    n = len(imgs); cols, rows = (2, 1) if n == 2 else (2, 2) if n <= 4 else (3, 2) if n <= 6 else (3, 3)
    w_step, h_step = tw / cols, th / rows
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        canvas.paste(ImageOps.fit(img, (int(w_step), int(h_step))), (int(c * w_step), int(r * h_step)))
    return canvas

# --- [3. 레이아웃 선언 (최상단 고정)] ---
col_main, col_design = st.columns([1.6, 1], gap="medium")

# --- [4. 인증 및 데이터 연동] ---
if 'access_token' not in st.session_state: st.session_state['access_token'] = None
query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": query_params["code"], "grant_type": "authorization_code"}).json()
    if 'access_token' in res: st.session_state['access_token'] = res['access_token']; st.query_params.clear(); st.rerun()

acts = [] 
if st.session_state['access_token']:
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
    r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers=headers)
    if r.status_code == 200: acts = r.json()

# --- [5. 메인 화면 구성] ---
with col_main:
    st.title("TITAN BOY")
    if not st.session_state['access_token']:
        st.link_button("🚀 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)
        bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
        log_file = st.file_uploader("🔘 원형 로고", type=['jpg','jpeg','png'])
        
        mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)
        v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", "2026-02-15", "0.00", "00:00:00", "0'00\"", "0"
        weekly_data, monthly_data, a = None, None, None
        
        if acts:
            if mode == "DAILY":
                act_opts = [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts]
                sel_act = st.selectbox("🏃 활동 선택", act_opts)
                a = acts[act_opts.index(sel_act)]
                d_km = a.get('distance', 0)/1000; m_s = a.get('moving_time', 0)
                v_act, v_date, v_dist, v_time = a['name'], a['start_date_local'][:10], f"{d_km:.2f}", f"{m_s//3600:02d}:{(m_s%3600)//60:02d}:{m_s%60:02d}"
                v_pace = f"{int((m_s/d_km)//60)}'{int((m_s/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
                v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
            elif mode == "WEEKLY":
                weeks = sorted(list(set([(datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d") - timedelta(days=datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d").weekday())).strftime('%Y.%m.%d') for ac in acts])), reverse=True)
                sel_week = st.selectbox("📅 주차 선택", weeks)
                weekly_data = get_weekly_stats(acts, sel_week.replace('.','-'))
                if weekly_data: v_act, v_date, v_dist, v_time, v_pace, v_hr = "WEEKLY RUN", weekly_data['range'], weekly_data['total_dist'], weekly_data['total_time'], weekly_data['avg_pace'], weekly_data['avg_hr']
            elif mode == "MONTHLY":
                months = sorted(list(set([ac['start_date_local'][:7] for ac in acts])), reverse=True)
                sel_month = st.selectbox("🗓️ 월 선택", months)
                monthly_data = get_monthly_stats(acts, f"{sel_month}-01")
                if monthly_data: v_act, v_date, v_dist, v_time, v_pace, v_hr = "MONTHLY RUN", monthly_data['range'], monthly_data['total_dist'], monthly_data['total_time'], monthly_data['avg_pace'], monthly_data['avg_hr']

# --- [6. 디자인 창 구성] ---
with col_design:
    st.header("🎨 DESIGN")
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color = st.color_picker("포인트 컬러", "#FFD700")
    sub_color = st.color_picker("서브 컬러", "#FFFFFF")
    rx, ry = st.number_input("박스 X", 0, 1080, 70), st.number_input("박스 Y", 0, 1920, 1250 if mode=="DAILY" else 80)
    rw, rh = st.number_input("박스 너비", 100, 1080, 1000 if box_orient=="Horizontal" else 450), st.number_input("박스 높이", 100, 1920, 350 if box_orient=="Horizontal" else 600)
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    vis_sz_adj = st.slider("지도/그래프 크기", 50, 1080, 180 if mode=="DAILY" else 950)
    vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 180)

# --- [7. 미리보기 렌더링 (최종 통합)] ---
with col_main:
    st.subheader("🖼️ PREVIEW")
    data_ready = (mode == "DAILY" and a) or (mode == "WEEKLY" and weekly_data) or (mode == "MONTHLY" and monthly_data)
    if data_ready:
        try:
            CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
            f_t, f_d, f_n, f_l = load_font(sel_font, 70), load_font(sel_font, 20), load_font(sel_font, 45), load_font(sel_font, 23)
            f_path = f"font_{sel_font}_70.ttf"
            
            canvas = make_smart_collage(bg_files, (CW, CH)) if bg_files else Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
            overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
            
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
            if box_orient == "Vertical":
                draw_styled_text(draw, (rx+40, ry+30), v_act, f_t, m_color)
                draw_styled_text(draw, (rx+40, ry+125), v_date, f_d, "#AAAAAA")
                y_c = ry + 190
                for lab, val in items:
                    draw_styled_text(draw, (rx+40, y_c), lab.lower(), f_l, "#AAAAAA")
                    draw_styled_text(draw, (rx+40, y_c+35), val.lower(), f_n, sub_color)
                    y_c += 100
            else:
                draw_styled_text(draw, (rx + (rw-draw.textlength(v_act, f_t))//2, ry+35), v_act, f_t, m_color)
                draw_styled_text(draw, (rx + (rw-draw.textlength(v_date, f_d))//2, ry+130), v_date, f_d, "#AAAAAA")
                sec_w = rw // 4
                for i, (lab, val) in enumerate(items):
                    cx = rx + (i * sec_w) + (sec_w // 2)
                    draw_styled_text(draw, (cx - draw.textlength(lab.lower(), f_l)//2, ry+185), lab.lower(), f_l, "#AAAAAA")
                    draw_styled_text(draw, (cx - draw.textlength(val.lower(), f_n)//2, ry+230), val.lower(), f_n, sub_color)

            if mode in ["WEEKLY", "MONTHLY"]:
                d_obj = weekly_data if mode == "WEEKLY" else monthly_data
                chart_img = create_bar_chart(d_obj['dists'], m_color, mode=mode, labels=d_obj.get('labels'), font_path=f_path)
                vis_layer = chart_img.resize((vis_sz_adj, int(chart_img.size[1]*(vis_sz_adj/chart_img.size[0]))), Image.Resampling.LANCZOS)
                vis_layer.putalpha(vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255)))
                overlay.paste(vis_layer, ((CW - vis_layer.width)//2, CH - vis_layer.height - 80), vis_layer)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, width=300)
        except Exception as e:
            st.error(f"렌더링 오류: {e}")
