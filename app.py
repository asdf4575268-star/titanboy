import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
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
        next_month = target_date.replace(day=28) + timedelta(days=4)
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

def make_smart_collage(files, target_size):
    tw, th = target_size
    imgs = [ImageOps.exif_transpose(Image.open(f).convert("RGBA")) for f in files[:10]]
    n = len(imgs)
    if n == 0: return Image.new("RGBA", (tw, th), (30, 30, 30, 255))
    if n == 1: return ImageOps.fit(imgs[0], (tw, th))
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
    grid = (2, 1) if n == 2 else (2, 2) if n <= 4 else (3, 2) if n <= 6 else (3, 3) if n <= 9 else (5, 2)
    cols, rows = grid
    w_step, h_step = tw / cols, th / rows
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        rem = n - (r * cols)
        curr_cols = cols if (r + 1) * cols <= n else rem
        cw_step = tw / curr_cols
        x1, y1 = int(c * cw_step), int(r * h_step)
        x2, y2 = int((c + 1) * cw_step) if (c + 1) < curr_cols else tw, int((r + 1) * h_step) if (r + 1) < rows else th
        canvas.paste(ImageOps.fit(img, (x2 - x1, y2 - y1)), (x1, y1))
    return canvas

def draw_styled_text(draw, pos, text, font, fill, shadow=True):
    if shadow:
        draw.text((pos[0]+3, pos[1]+3), text, font=font, fill=(0, 0, 0, 180))
    draw.text(pos, text, font=font, fill=fill)

@st.cache_resource
def load_font(font_type, size):
    fonts = {"BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf", "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf", "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf", "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf", "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Bold.ttf"}
    f_path = f"font_{font_type}_{int(size)}.ttf"
    if not os.path.exists(f_path):
        r = requests.get(fonts.get(font_type, fonts["BlackHanSans"])); open(f_path, "wb").write(r.content)
    return ImageFont.truetype(f_path, int(size))

def create_bar_chart(data, color_hex, mode="WEEKLY", labels=None, font_path=None):
    if mode == "WEEKLY": labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    prop = font_manager.FontProperties(fname=font_path) if font_path else None
    fig, ax = plt.subplots(figsize=(10, 4.0), dpi=150) # 그래프 높이 소폭 조정
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    bars = ax.bar(labels, data, color=color_hex, width=0.6)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='x', colors='white')
    if prop:
        for label in ax.get_xticklabels(): label.set_fontproperties(prop); label.set_fontsize(10 if mode=="MONTHLY" else 14)
    ax.tick_params(axis='y', left=False, labelleft=False)
    if mode == "WEEKLY":
        for bar in bars:
            h = bar.get_height()
            if h > 0: ax.text(bar.get_x() + bar.get_width()/2., h + 0.1, f'{h:.1f}', ha='center', va='bottom', color='white', fontproperties=prop, fontsize=12)
    plt.tight_layout(); buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); buf.seek(0); plt.close(fig)
    return Image.open(buf)

# --- [3. 인증 및 데이터] ---
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

# --- [4. 레이아웃] ---
col_main, col_design = st.columns([1.6, 1], gap="medium")

with col_main:
    st.title("TITAN BOY")
    if not st.session_state['access_token']:
        st.link_button("🚀 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        st.button("🔓 로그아웃", on_click=logout_and_clear, key="logout_btn", use_container_width=True)
        with st.container(border=True):
            col_img1, col_img2 = st.columns(2)
            bg_files = col_img1.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
            log_file = col_img2.file_uploader("🔘 원형 로고", type=['jpg','jpeg','png'])

    mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True, key="mode_radio")
    v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", "2026-02-15", "0.00", "00:00:00", "0'00\"", "0"
    weekly_data, monthly_data, a = None, None, None
    if acts:
        with st.container(border=True):
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

# --- [5. 디자인 설정] ---
with col_design:
    st.header("🎨 DESIGN")
    
    if "prev_orient" not in st.session_state: st.session_state.prev_orient = "Vertical"
    if "prev_mode" not in st.session_state: st.session_state.prev_mode = "DAILY"

    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True, key="orient_radio")

    # 모드나 방향이 바뀌면 리셋
    if st.session_state.prev_orient != box_orient or st.session_state.prev_mode != mode:
        st.session_state.prev_orient = box_orient
        st.session_state.prev_mode = mode
        st.rerun()

    # 모드/방향별 좌표 자동 계산 로직
    if mode == "DAILY":
        if box_orient == "Horizontal": def_rx, def_ry, def_rw, def_rh = 0, 1400, 1080, 350
        else: def_rx, def_ry, def_rw, def_rh = 70, 1250, 450, 550
    else: # WEEKLY, MONTHLY (1350 높이)
        if box_orient == "Horizontal": def_rx, def_ry, def_rw, def_rh = 0, 100, 1080, 350 # 상단 배치 추천
        else: def_rx, def_ry, def_rw, def_rh = 70, 70, 450, 550

    with st.expander("✍️ 텍스트 수정"):
        v_act = st.text_input("활동명", v_act, key="ti_act")
        v_date = st.text_input("날짜", v_date, key="ti_date")
        v_dist = st.text_input("거리 km", v_dist, key="ti_dist")
        v_time = st.text_input("시간", v_time, key="ti_time")
        v_pace = st.text_input("페이스", v_pace, key="ti_pace")
        v_hr = st.text_input("심박 bpm", v_hr, key="ti_hr")

    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"], key="font_sel")
    
    with st.expander("💄 매거진 스타일", expanded=True):
        use_shadow = st.toggle("글자 그림자 효과", value=True, key="shadow_tg")
        border_thick = st.slider("프레임 테두리 두께", 0, 50, 0, key="border_sl")
        COLOR_OPTS = {"Yellow": "#FFD700", "White": "#FFFFFF", "Orange": "#FF4500", "Blue": "#00BFFF", "Grey": "#AAAAAA"}
        m_color = COLOR_OPTS[st.selectbox("포인트 컬러", list(COLOR_OPTS.keys()), key="m_col_sel")]
        sub_color = COLOR_OPTS[st.selectbox("서브 컬러", list(COLOR_OPTS.keys()), index=1, key="s_col_sel")]

    with st.expander("📍 위치/크기 조절", expanded=True):
        # key에 모드와 방향을 합쳐서 리셋 유도
        k_suf = f"{mode}_{box_orient}"
        rx = st.number_input("박스 X", 0, 1080, def_rx, key=f"rx_{k_suf}")
        ry = st.number_input("박스 Y", 0, 1920, def_ry, key=f"ry_{k_suf}")
        rw = st.number_input("박스 너비", 100, 1080, def_rw, key=f"rw_{k_suf}")
        rh = st.number_input("박스 높이", 100, 1920, def_rh, key=f"rh_{k_suf}")
        box_alpha = st.slider("박스 투명도", 0, 255, 110, key="box_alpha_sl")
        vis_sz_adj = st.slider("지도/그래프 크기", 50, 1080, 180 if mode=="DAILY" else 950, key="vis_sz_sl")
        vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 180, key="vis_alpha_sl")

# --- [6. 미리보기] ---
with col_main:
    st.subheader("🖼️ PREVIEW")
    try:
        CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
        f_t, f_d, f_n, f_l = load_font(sel_font, 90), load_font(sel_font, 30), load_font(sel_font, 60), load_font(sel_font, 23)
        f_path = f"font_{sel_font}_90.ttf"
        
        canvas = make_smart_collage(bg_files, (CW, CH)) if bg_files else Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
        overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
        
        if border_thick > 0:
            draw.rectangle([0, 0, CW, CH], outline=m_color, width=border_thick)

        title_w = draw.textlength(v_act, font=f_t)

        if st.checkbox("데이터 박스 보기", value=True, key="show_box_cb"):
            items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
            if box_orient == "Vertical":
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
                draw_styled_text(draw, (rx+40, ry+30), v_act, f_t, m_color, use_shadow)
                draw_styled_text(draw, (rx+40, ry+125), v_date, f_d, "#AAAAAA", use_shadow)
                y_c = ry + 200
                for lab, val in items:
                    draw_styled_text(draw, (rx+40, y_c), lab.lower(), f_l, "#AAAAAA", use_shadow)
                    v_s = val.lower() if any(x in val for x in ["km","bpm"]) else val
                    draw_styled_text(draw, (rx+40, y_c+30), v_s, f_n, sub_color, use_shadow)
                    y_c += 95
            else:
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
                t_x = rx + (rw - title_w)//2
                draw_styled_text(draw, (t_x, ry + 35), v_act, f_t, m_color, use_shadow)
                draw_styled_text(draw, (rx + (rw - draw.textlength(v_date, font=f_d))//2, ry + 140), v_date, f_d, "#AAAAAA", use_shadow)
                sec_w = rw // 4
                for i, (lab, val) in enumerate(items):
                    cx = rx + (i * sec_w) + (sec_w // 2); v_s = val.lower() if any(x in val for x in ["km","bpm"]) else val
                    draw_styled_text(draw, (cx - draw.textlength(lab.lower(), font=f_l)//2, ry + 195), lab.lower(), f_l, "#AAAAAA", use_shadow)
                    draw_styled_text(draw, (cx - draw.textlength(v_s, font=f_n)//2, ry + 235), v_s, f_n, sub_color, use_shadow)

        if st.checkbox("지도/그래프 보기", value=True, key="show_vis_cb"):
            if mode == "DAILY" and a and a.get('map', {}).get('summary_polyline'):
                pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
                vis_sz = vis_sz_adj
                vis_layer = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); m_draw = ImageDraw.Draw(vis_layer)
                def tr(la, lo): return 15+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-30), (vis_sz-15)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-30)
                m_draw.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, vis_alpha), width=5)
                m_x = rx + 40 + title_w + 30 if box_orient == "Vertical" else rx + (rw - title_w)//2 - vis_sz - 30
                overlay.paste(vis_layer, (int(m_x), int(ry + 35)), vis_layer)
            elif mode in ["WEEKLY", "MONTHLY"] and (weekly_data or monthly_data):
                d_obj = weekly_data if mode == "WEEKLY" else monthly_data
                chart_img = create_bar_chart(d_obj['dists'], m_color, mode=mode, labels=d_obj.get('labels'), font_path=f_path)
                vis_sz = vis_sz_adj
                v_l = chart_img.resize((vis_sz, int(chart_img.size[1]*(vis_sz/chart_img.size[0]))), Image.Resampling.LANCZOS)
                v_l.putalpha(v_l.getchannel('A').point(lambda x: x * (vis_alpha / 255)))
                # 통계 그래프 위치 최적화: 캔버스 하단 중앙
                overlay.paste(v_l, ((CW - v_l.width)//2, CH - v_l.height - 50), v_l)

        if log_file:
            ls = 100; l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (ls, ls))
            mask = Image.new('L', (ls, ls), 0); ImageDraw.Draw(mask).ellipse((0, 0, ls, ls), fill=255); l_img.putalpha(mask)
            l_pos = (rx + rw - ls - 30, ry + 30) if box_orient == "Horizontal" else (rx + rw - ls - 25, ry + rh - ls - 25)
            overlay.paste(l_img, l_pos, l_img)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        st.image(final, width=500)
        
        buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
        st.download_button(f"📸 {mode} DOWNLOAD", buf.getvalue(), f"{mode.lower()}.jpg", use_container_width=True, key="down_btn")
    except Exception as e:
        st.info("데이터와 사진을 선택하면 매거진 미리보기가 나타납니다.")
