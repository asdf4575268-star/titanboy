import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl

# --- [1. 기본 설정 및 초기화] ---
CLIENT_ID = '202275'
CLIENT_SECRET = '969201cab488e4eaf1398b106de1d4e520dc564c'
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# Matplotlib 한글 폰트 문제 회피 (영문 표기) 및 백엔드 설정
mpl.use('Agg')

def logout_and_clear():
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()

if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# --- [2. 인증 로직] ---
query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": query_params["code"], "grant_type": "authorization_code"
        }, timeout=15)
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            st.query_params.clear()
            st.rerun()
    except: pass

# --- [3. 유틸리티 함수] ---
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

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return rgb + (alpha,)

def get_weekly_stats(activities, target_date_str):
    """특정 날짜가 포함된 주의 월~일 통계 계산 (러닝+지도 필수)"""
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        start_of_week = target_date - timedelta(days=target_date.weekday()) # 월요일
        end_of_week = start_of_week + timedelta(days=6) # 일요일
        
        weekly_dist = [0.0] * 7 # Mon~Sun
        total_dist = 0.0
        total_time = 0
        hr_sum = 0
        hr_count = 0
        
        for act in activities:
            # 조건: 러닝(Run)이고, 지도(map)가 있어야 함
            if act.get('type') == 'Run' and act.get('map', {}).get('summary_polyline'):
                act_date = datetime.strptime(act['start_date_local'][:10], "%Y-%m-%d")
                
                if start_of_week <= act_date <= end_of_week:
                    day_idx = act_date.weekday() # 0=Mon, 6=Sun
                    dist = act.get('distance', 0) / 1000
                    weekly_dist[day_idx] += dist
                    total_dist += dist
                    total_time += act.get('moving_time', 0)
                    
                    avg_hr = act.get('average_heartrate')
                    if avg_hr:
                        hr_sum += avg_hr
                        hr_count += 1
                        
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        avg_pace = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\""
        
        # 시간 포맷팅
        fmt_time = f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}"
        
        date_range = f"{start_of_week.strftime('%m.%d')} - {end_of_week.strftime('%m.%d')}"
        
        return {
            "dists": weekly_dist,
            "total_dist": f"{total_dist:.2f}",
            "total_time": fmt_time,
            "avg_pace": avg_pace,
            "avg_hr": str(avg_hr),
            "range": date_range
        }
    except:
        return None

def create_bar_chart(data, color_hex):
    """Matplotlib을 이용해 투명 배경의 막대 그래프 이미지 생성"""
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    # 그래프 설정 (크기 조절 가능)
    fig, ax = plt.subplots(figsize=(6, 3), dpi=150)
    fig.patch.set_alpha(0) # 전체 배경 투명
    ax.patch.set_alpha(0)  # 플롯 배경 투명
    
    # 막대 그리기
    bars = ax.bar(days, data, color=color_hex, width=0.5, zorder=3)
    
    # 스타일링
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#DDDDDD') # 바닥 선 연하게
    
    ax.tick_params(axis='x', colors='gray', labelsize=10) # X축 라벨 색상
    ax.tick_params(axis='y', left=False, labelleft=False) # Y축 숨김
    
    # 값 표시 (막대 위 숫자)
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.1f}', ha='center', va='bottom', color='gray', fontsize=9, fontweight='bold')

    plt.tight_layout()
    
    # 이미지로 변환
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True)
    buf.seek(0)
    plt.close(fig)
    return Image.open(buf)

# --- [4. 데이터 로드 (Strava)] ---
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

with col2:
    m_col, l_col = st.columns([3, 1])
    with m_col: mode = st.radio("모드", ["DAILY", "WEEKLY"], horizontal=True, label_visibility="collapsed")
    with l_col: 
        if st.session_state['access_token']:
            st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)
        else:
            auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
                        f"&response_type=code&redirect_uri={ACTUAL_URL}"
                        f"&scope=read,activity:read_all&approval_prompt=force")
            st.link_button("🚀 Strava 연동", auth_url, use_container_width=True)

    # 초기값 설정
    v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", datetime.now().strftime("%Y-%m-%d"), "0.00", "00:00:00", "0'00\"", "0"
    weekly_data = None
    a = None

    # 데이터 처리 로직
    if acts:
        # 기준 날짜 선택 (최신 활동 기준)
        act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
        sel_str = st.selectbox("기준 기록 선택 (주간 통계용)", act_options)
        sel_idx = act_options.index(sel_str)
        a = acts[sel_idx]
        
        v_date = a['start_date_local'][:10] # 선택된 날짜
        
        if mode == "DAILY":
            # [DAILY] 단일 기록 정보
            d_km = a.get('distance', 0)/1000
            m_sec = a.get('moving_time', 0)
            v_act = a['name']
            v_dist = f"{d_km:.2f}"
            v_time = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}" if m_sec >= 3600 else f"{m_sec//60:02d}:{m_sec%60:02d}"
            v_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
            v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        else:
            # [WEEKLY] 주간 통계 계산
            weekly_data = get_weekly_stats(acts, v_date)
            if weekly_data:
                v_act = "WEEKLY RUN"
                v_date = weekly_data['range']
                v_dist = weekly_data['total_dist']
                v_time = weekly_data['total_time']
                v_pace = weekly_data['avg_pace']
                v_hr = weekly_data['avg_hr']

with col1:
    st.header("📸 DATA INPUT")
    bg_files = st.file_uploader("배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("원형 로고", type=['jpg','jpeg','png'])
    
    st.divider()
    # 수동 입력/수정
    v_act = st.text_input("활동명 (Title)", v_act)
    v_date = st.text_input("날짜/기간", v_date)
    v_dist = st.text_input("거리 (Total km)", v_dist)
    v_time = st.text_input("시간 (Total Time)", v_time)
    v_pace = st.text_input("페이스 (Avg Pace)", v_pace)
    v_hr = st.text_input("심박 (Avg BPM)", v_hr)

with col3:
    st.header("🎨 DESIGN")
    show_box = st.checkbox("로그 박스 표시", value=True)
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color = COLOR_OPTIONS[st.selectbox("포인트 컬러", list(COLOR_OPTIONS.keys()), index=4)] # Blue default for graph
    sub_color = COLOR_OPTIONS[st.selectbox("서브 컬러", list(COLOR_OPTIONS.keys()), index=1)]
    
    t_sz, d_sz, n_sz, l_sz = 90, 30, 60, 20
    
    # 박스 기본 위치/크기
    d_rx, d_ry, d_rw, d_rh = (70, 1250, 480, 600) if box_orient == "Vertical" else (70, 1600, 940, 260)
    rx = st.number_input("X 위치", 0, 1080, d_rx)
    ry = st.number_input("Y 위치", 0, 1920, d_ry)
    rw = st.number_input("박스 너비", 100, 1080, d_rw)
    rh = st.number_input("박스 높이", 100, 1920, d_rh)
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    map_size = st.slider("지도/그래프 크기", 50, 1000, 300 if mode=="WEEKLY" else 100)

# --- [6. 렌더링 엔진] ---
if bg_files:
    try:
        f_t, f_d, f_n, f_l = load_font(sel_font, t_sz), load_font(sel_font, d_sz), load_font(sel_font, n_sz), load_font(sel_font, l_sz)
        
        CW, CH = 1080, 1920
        canvas = Image.new("RGBA", (CW, CH), (0,0,0,255))
        
        # [콜라주 로직] : WEEKLY 스마트 그리드 (여백 제거)
        num_pics = len(bg_files)
        
        if mode == "DAILY" or num_pics == 1:
            img = ImageOps.exif_transpose(Image.open(bg_files[0]))
            canvas = ImageOps.fit(img.convert("RGBA"), (CW, CH))
        else:
            # 사진 개수에 따라 레이아웃 자동 결정
            if num_pics <= 3:
                cols = 1
                rows = num_pics
            elif num_pics == 4:
                cols = 2
                rows = 2
            else:
                cols = 2
                rows = math.ceil(num_pics / cols)

            w_unit = CW // cols
            h_unit = CH // rows
            
            for i, f in enumerate(bg_files):
                img = ImageOps.exif_transpose(Image.open(f))
                
                # 마지막 사진이고, 홀수 개수이며, cols가 2인 경우 -> 마지막 줄 꽉 채우기
                if i == num_pics - 1 and num_pics % 2 == 1 and cols == 2:
                     img = ImageOps.fit(img.convert("RGBA"), (CW, h_unit), centering=(0.5, 0.5))
                     canvas.paste(img, (0, (i // cols) * h_unit))
                else:
                    img = ImageOps.fit(img.convert("RGBA"), (w_unit, h_unit), centering=(0.5, 0.5))
                    canvas.paste(img, ((i % cols) * w_unit, (i // cols) * h_unit))

        overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
        
        if show_box:
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
            items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
            
            # --- [시각화 요소: 지도(Daily) vs 그래프(Weekly)] ---
            vis_layer = None
            
            if mode == "DAILY" and a and a.get('map', {}).get('summary_polyline'):
                # [DAILY] 지도 그리기
                pts = polyline.decode(a['map']['summary_polyline'])
                lats, lons = zip(*pts)
                vis_layer = Image.new("RGBA", (map_size, map_size), (0,0,0,0)); m_draw = ImageDraw.Draw(vis_layer)
                def trans(la, lo):
                    tx = 10 + (lo - min(lons)) / (max(lons) - min(lons) + 0.00001) * (map_size - 20)
                    ty = (map_size - 10) - (la - min(lats)) / (max(lats) - min(lats) + 0.00001) * (map_size - 20)
                    return tx, ty
                m_draw.line([trans(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, 255), width=4)
                
            elif mode == "WEEKLY" and weekly_data:
                # [WEEKLY] 막대 그래프 생성
                chart_img = create_bar_chart(weekly_data['dists'], m_color)
                # 그래프 크기 조절 (가로폭 기준 map_size 사용)
                w_percent = (map_size / float(chart_img.size[0]))
                h_size = int((float(chart_img.size[1]) * float(w_percent)))
                vis_layer = chart_img.resize((map_size, h_size), Image.Resampling.LANCZOS)

            # 시각화 레이어 합성
            if vis_layer:
                if box_orient == "Vertical":
                    # Vertical: 박스 상단 우측
                    overlay.paste(vis_layer, (rx + rw - vis_layer.width - 20, ry + 20), vis_layer)
                else:
                    # Horizontal: 박스 좌측
                    overlay.paste(vis_layer, (rx + 30, ry + 20), vis_layer)

            # --- [텍스트 배치] ---
            if box_orient == "Vertical":
                draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
                draw.text((rx+40, ry+30+t_sz+10), v_date, font=f_d, fill="#AAAAAA")
                y_c = ry + t_sz + d_sz + 90
                for lab, val in items:
                    draw.text((rx+40, y_c), lab, font=f_l, fill="#AAAAAA")
                    draw.text((rx+40, y_c+l_sz+5), val, font=f_n, fill=sub_color); y_c += (n_sz + l_sz + 35)
            else:
                title_w = draw.textlength(v_act, font=f_t)
                draw.text((rx + (rw // 2) - (title_w // 2), ry + 25), v_act, font=f_t, fill=m_color)
                date_w = draw.textlength(v_date, font=f_d)
                draw.text((rx + (rw // 2) - (date_w // 2), ry + 25 + t_sz + 5), v_date, font=f_d, fill="#AAAAAA")
                
                # 통계 수치 배치 (가로)
                sec_w = (rw - 80) // 4
                for i, (lab, val) in enumerate(items):
                    item_x = rx + 40 + (i * sec_w)
                    draw.text((item_x, ry + t_sz + d_sz + 50), lab, font=f_l, fill="#AAAAAA")
                    draw.text((item_x, ry + t_sz + d_sz + 50 + l_sz + 5), val, font=f_n, fill=sub_color)

            if log_file:
                l_sz_img = 100 if box_orient == "Vertical" else 80
                l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (l_sz_img, l_sz_img))
                mask = Image.new('L', (l_sz_img, l_sz_img), 0); ImageDraw.Draw(mask).ellipse((0, 0, l_sz_img, l_sz_img), fill=255); l_img.putalpha(mask)
                if box_orient == "Vertical":
                    overlay.paste(l_img, (rx + rw - l_sz_img - 20, ry + rh - l_sz_img - 20), l_img)
                else:
                    overlay.paste(l_img, (rx + rw - l_sz_img - 30, ry + 25), l_img)

        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        with col2:
            st.image(final, use_container_width=True)
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 DOWNLOAD", buf.getvalue(), "result.jpg", use_container_width=True)
                
    except Exception as e:
        st.error(f"Error: {e}")
