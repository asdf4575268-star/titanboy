import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl

# --- [1. 기본 설정] ---
CLIENT_ID = '202275'
CLIENT_SECRET = '969201cab488e4eaf1398b106de1d4e520dc564c'
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

st.set_page_config(page_title="Garmin Dashboard", layout="wide")
mpl.use('Agg')

def logout_and_clear():
    st.cache_data.clear(); st.cache_resource.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

if 'access_token' not in st.session_state: st.session_state['access_token'] = None

# --- [2. Strava 인증] ---
query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": query_params["code"], "grant_type": "authorization_code"
        }, timeout=15)
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            st.query_params.clear(); st.rerun()
    except: pass

# --- [3. 유틸리티] ---
@st.cache_resource
def load_font(font_type, size):
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Jua": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "DoHyeon": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf",
        "NanumBrush": "https://github.com/google/fonts/raw/main/ofl/nanumbrushscript/NanumBrushScript-Regular.ttf",
        "Sunflower": "https://github.com/google/fonts/raw/main/ofl/sunflower/Sunflower-Bold.ttf"
    }
    f_url = fonts.get(font_type, fonts["BlackHanSans"])
    f_path = f"font_{font_type}_{int(size)}.ttf"
    if not os.path.exists(f_path):
        r = requests.get(f_url); open(f_path, "wb").write(r.content)
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
                    day_idx = act_date.weekday()
                    dist = act.get('distance', 0) / 1000
                    weekly_dist[day_idx] += dist; total_dist += dist; total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): hr_sum += act.get('average_heartrate'); hr_count += 1
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        avg_pace = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\""
        fmt_time = f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}"
        return {"dists": weekly_dist, "total_dist": f"{total_dist:.2f}", "total_time": fmt_time, "avg_pace": avg_pace, "avg_hr": str(avg_hr), "range": f"{start_of_week.strftime('%m.%d')} - {end_of_week.strftime('%m.%d')}"}
    except: return None

def create_bar_chart(data, color_hex):
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    bars = ax.bar(days, data, color=color_hex, width=0.6)
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='x', colors='white', labelsize=12); ax.tick_params(axis='y', left=False, labelleft=False)
    for bar in bars:
        h = bar.get_height()
        if h > 0: ax.text(bar.get_x() + bar.get_width()/2., h + 0.1, f'{h:.1f}', ha='center', va='bottom', color='white', fontsize=11, fontweight='bold')
    plt.tight_layout(); buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); buf.seek(0); plt.close(fig)
    return Image.open(buf)

# --- [4. 데이터 로드] ---
acts = []
if st.session_state['access_token']:
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
    try:
        act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers, timeout=15)
        if act_res.status_code == 200: acts = act_res.json()
    except: pass

# --- [5. UI 레이아웃] ---
col1, col2, col3 = st.columns([1.2, 2, 1], gap="medium")
COLOR_OPTIONS = {"Garmin Yellow": "#FFD700", "Pure White": "#FFFFFF", "Pure Black": "#000000", "Neon Orange": "#FF4500", "Electric Blue": "#00BFFF", "Soft Grey": "#AAAAAA"}

v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", datetime.now().strftime("%Y-%m-%d"), "0.00", "00:00:00", "0'00\"", "0"
weekly_data = None; a = None

with col2:
    mode = st.radio("모드 선택", ["DAILY", "WEEKLY"], horizontal=True, label_visibility="collapsed")
    if acts:
        act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
        sel_str = st.selectbox("기록 선택", act_options)
        a = acts[act_options.index(sel_str)]; v_date = a['start_date_local'][:10]
        if mode == "DAILY":
            d_km = a.get('distance', 0)/1000; m_sec = a.get('moving_time', 0)
            v_act, v_dist = a['name'], f"{d_km:.2f}"
            v_time = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}"
            v_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
            v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        else:
            weekly_data = get_weekly_stats(acts, v_date)
            if weekly_data: v_act, v_date, v_dist, v_time, v_pace, v_hr = "WEEKLY RUN", weekly_data['range'], weekly_data['total_dist'], weekly_data['total_time'], weekly_data['avg_pace'], weekly_data['avg_hr']

with col1:
    st.header("📸 DATA INPUT")
    bg_files = st.file_uploader("사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("원형 로고", type=['jpg','jpeg','png'])
    v_act = st.text_input("활동명", v_act)
    v_date = st.text_input("날짜", v_date)
    v_dist = st.text_input("거리 km", v_dist); v_time = st.text_input("시간", v_time)
    v_pace = st.text_input("페이스 분/km", v_pace); v_hr = st.text_input("심박 bpm", v_hr)

with col3:
    st.header("🎨 DESIGN")
    box_orient = st.radio("로그박스 형태", ["Horizontal", "Vertical"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color = COLOR_OPTIONS[st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()), index=0)]
    sub_color = COLOR_OPTIONS[st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)]
    
    CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1080)
    
    st.subheader("📦 박스 및 요소 조절")
    bx = st.number_input("박스 X", 0, 1080, 70)
    by = st.number_input("박스 Y", 0, 1920, 1400 if mode=="DAILY" else 750)
    bw = st.number_input("박스 너비", 100, 1080, 940 if box_orient=="Horizontal" else 480)
    bh = st.number_input("박스 높이", 100, 1080, 260 if box_orient=="Horizontal" else 550)
    box_alpha = st.slider("박스 투명도", 0, 255, 130)
    
    # 지도/그래프 세부 설정 (작고 흐릿하게 조절 가능)
    vis_sz = st.slider("지도/그래프 크기", 50, 800, 180 if mode=="DAILY" else 800)
    vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 80) # 기본값을 낮게 설정하여 흐릿하게 함
    
    if mode == "WEEKLY": 
        g_y_off = st.slider("그래프 높이 조절", 0, 1000, 150)

# --- [6. 렌더링 엔진] ---
try:
    f_t, f_d, f_n, f_l = load_font(sel_font, 90), load_font(sel_font, 30), load_font(sel_font, 60), load_font(sel_font, 20)
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 255))
    
    # ... [배경 사진/콜라주 로직 생략] ...

    overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
    
    # 1. 시각화 소스 생성 (투명도 반영)
    vis_layer = None
    if mode == "DAILY" and a and a.get('map', {}).get('summary_polyline'):
        pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
        vis_layer = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); m_draw = ImageDraw.Draw(vis_layer)
        def tr(la, lo): 
            m = 20
            return (lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-m*2)+m, (vis_sz-m)-(la-min(lats))/(la_max-la_min+1e-5)*(vis_sz-m*2)
        
        # 포인트 컬러에 투명도(vis_alpha) 적용
        target_rgba = hex_to_rgba(m_color, vis_alpha)
        m_draw.line([tr(la, lo) for la, lo in pts], fill=target_rgba, width=4) # 선 굵기를 4로 가늘게 변경
        
    elif mode == "WEEKLY" and weekly_data:
        chart_img = create_bar_chart(weekly_data['dists'], m_color)
        w_p = (vis_sz / float(chart_img.size[0]))
        vis_layer = chart_img.resize((vis_sz, int(chart_img.size[1]*w_p)), Image.Resampling.LANCZOS)
        # 그래프 이미지 전체에 투명도 적용
        alpha_mask = vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255))
        vis_layer.putalpha(alpha_mask)

# --- [6. 렌더링 엔진] ---
try:
    f_t, f_d, f_n, f_l = load_font(sel_font, 90), load_font(sel_font, 30), load_font(sel_font, 60), load_font(sel_font, 20)
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 255))
    
    if bg_files:
        num_pics = len(bg_files)
        if mode == "DAILY" or num_pics == 1:
            canvas = ImageOps.fit(ImageOps.exif_transpose(Image.open(bg_files[0])).convert("RGBA"), (CW, CH))
        else:
            cols, rows = (1, num_pics) if num_pics <= 3 else ((2, 2) if num_pics == 4 else (2, math.ceil(num_pics/2)))
            w_u, h_u = CW // cols, CH // rows
            for i, f in enumerate(bg_files):
                img = ImageOps.fit(ImageOps.exif_transpose(Image.open(f)).convert("RGBA"), (CW if (i==num_pics-1 and num_pics%2==1 and cols==2) else w_u, h_u))
                canvas.paste(img, (0 if (i==num_pics-1 and num_pics%2==1 and cols==2) else (i%cols)*w_u, (i//cols)*h_u))

    overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
    
    # 1. 시각화 소스 생성
    vis_layer = None
    if mode == "DAILY" and a and a.get('map', {}).get('summary_polyline'):
        pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
        vis_layer = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); m_draw = ImageDraw.Draw(vis_layer)
        def tr(la, lo): return (lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-40)+20, (vis_sz-20)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-40)
        m_draw.line([tr(la, lo) for la, lo in pts], fill=m_color, width=8)
    elif mode == "WEEKLY" and weekly_data:
        chart_img = create_bar_chart(weekly_data['dists'], m_color)
        w_p = (vis_sz / float(chart_img.size[0])); vis_layer = chart_img.resize((vis_sz, int(chart_img.size[1]*w_p)), Image.Resampling.LANCZOS)

    # 2. 로그박스 및 텍스트 배치
    draw.rectangle([bx, by, bx + bw, by + bh], fill=(0,0,0,box_alpha))
    items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
    
    if mode == "DAILY" and vis_layer:
        # [DAILY] 지도를 박스 내부 레이아웃에 맞춰 배치
        if box_orient == "Vertical":
            # 활동명 우측 상단 배치
            overlay.paste(vis_layer, (bx + bw - vis_layer.width - 20, by + 20), vis_layer)
        else:
            # 활동명 좌측 배치
            overlay.paste(vis_layer, (bx + 20, by + (bh - vis_layer.height)//2), vis_layer)
    
    if mode == "WEEKLY" and vis_layer:
        # [WEEKLY] 그래프는 박스 외부 상단 중앙
        overlay.paste(vis_layer, ((CW - vis_layer.width)//2, by - vis_layer.height - g_y_off), vis_layer)

    # 텍스트 렌더링
    if box_orient == "Vertical":
        draw.text((bx+40, by+30), v_act, font=f_t, fill=m_color)
        draw.text((bx+40, by+130), v_date, font=f_d, fill="#AAAAAA")
        y_c = by + 200
        for lab, val in items:
            draw.text((bx+40, y_c), lab.lower(), font=f_l, fill="#AAAAAA")
            draw.text((bx+40, y_c+25), val.lower() if "bpm" in val or "km" in val else val, font=f_n, fill=sub_color); y_c += 110
    else:
        # Horizontal 모드일 때 지도가 있으면 텍스트를 오른쪽으로 밀기
        text_x_off = vis_layer.width + 40 if (mode == "DAILY" and vis_layer) else 40
        draw.text((bx + text_x_off, by + 40), v_act, font=f_t, fill=m_color)
        draw.text((bx + text_x_off, by + 130), v_date, font=f_d, fill="#AAAAAA")
        sec_w = (bw - text_x_off - 40) // 4
        for i, (lab, val) in enumerate(items):
            draw.text((bx + text_x_off + (i*sec_w), by + 175), lab.lower(), font=f_l, fill="#AAAAAA")
            draw.text((bx + text_x_off + (i*sec_w), by + 200), val.lower() if "bpm" in val or "km" in val else val, font=f_n, fill=sub_color)

    if log_file:
        ls = 100; l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (ls, ls))
        mask = Image.new('L', (ls, ls), 0); ImageDraw.Draw(mask).ellipse((0, 0, ls, ls), fill=255); l_img.putalpha(mask)
        overlay.paste(l_img, (bx + bw - ls - 20, by + bh - ls - 20 if box_orient=="Vertical" else by + 25), l_img)

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    with col2:
        st.image(final, use_container_width=True)
        buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
        st.download_button(f"📸 {mode} DOWNLOAD", buf.getvalue(), f"{mode.lower()}_result.jpg", use_container_width=True)
        if st.session_state['access_token']: st.button("🔓 로그아웃", on_click=logout_and_clear)
except Exception as e: st.error(f"Error: {e}")

