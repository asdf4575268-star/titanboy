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

def create_bar_chart(data, color_hex, mode="WEEKLY", labels=None, font_path=None):
    if mode == "WEEKLY": 
        labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    elif labels is None:
        labels = [str(i+1) for i in range(len(data))]
    
    x_pos = np.arange(len(labels)) # MONTHLY dtype 에러 해결 핵심
    prop = font_manager.FontProperties(fname=font_path) if font_path else None
    fig, ax = plt.subplots(figsize=(10, 5.0), dpi=150)
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    
    bars = ax.bar(x_pos, data, color=color_hex, width=0.6)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels)
    
    for s in ['top', 'right', 'left']: ax.spines[s].set_visible(False)
    ax.tick_params(axis='x', colors='white')
    if prop:
        for label in ax.get_xticklabels(): 
            label.set_fontproperties(prop)
            label.set_fontsize(8 if mode=="MONTHLY" else 14)
    ax.tick_params(axis='y', left=False, labelleft=False)
    plt.tight_layout(); buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); buf.seek(0); plt.close(fig)
    return Image.open(buf)

def draw_styled_text(draw, pos, text, font, fill, shadow=True):
    if shadow:
        draw.text((pos[0]+3, pos[1]+3), text, font=font, fill=(0, 0, 0, 180))
    draw.text(pos, text, font=font, fill=fill)

# --- [3. 레이아웃 정의 (가장 먼저 수행)] ---
col_main, col_design = st.columns([1.6, 1], gap="medium")

# --- [4. 메인 데이터 로직] ---
with col_main:
    st.title("TITAN BOY")
    # ... (인증 로직 생략) ...
    bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("🔘 원형 로고", type=['jpg','jpeg','png'])
    
    mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)
    
    v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", "2026-02-15", "0.00", "00:00:00", "0'00\"", "0"
    weekly_data, monthly_data, a = None, None, None

    # (Strava API 데이터 fetch 및 get_weekly_stats 로직이 여기에 위치한다고 가정)
    # ... 데이터 선택 로직 ...

# --- [5. 디자인 설정] ---
with col_design:
    st.header("🎨 DESIGN")
    # 사용자 텍스트 입력창 (상단 데이터 할당 후)
    v_act = st.text_input("활동명", v_act)
    v_date = st.text_input("날짜", v_date)
    v_dist = st.text_input("거리 km", v_dist)
    v_time = st.text_input("시간", v_time)
    v_pace = st.text_input("페이스", v_pace)
    v_hr = st.text_input("심박 bpm", v_hr)

    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    
    use_shadow = st.toggle("글자 그림자 효과", value=True)
    m_color = st.color_picker("포인트 컬러", "#FFD700")
    sub_color = st.color_picker("서브 컬러", "#FFFFFF")
    
    rx, ry = st.number_input("박스 X", 0, 1080, 70), st.number_input("박스 Y", 0, 1920, 1250 if mode=="DAILY" else 80)
    rw, rh = st.number_input("박스 너비", 100, 1080, 1000 if box_orient=="Horizontal" else 450), st.number_input("박스 높이", 100, 1920, 350 if box_orient=="Horizontal" else 600)
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    vis_sz_adj = st.slider("지도/그래프 크기", 50, 1080, 180 if mode=="DAILY" else 950)
    vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 180)

# --- [6. 미리보기 렌더링 (최종 완성본)] ---
with col_main:
    st.subheader("🖼️ PREVIEW")
    
    # 사진 유무와 무관하게 데이터가 있으면 실행
    data_ready = (mode == "DAILY" and a) or (mode == "WEEKLY" and weekly_data) or (mode == "MONTHLY" and monthly_data)
    
    if data_ready:
        try:
            CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
            
            # [규칙 1] 폰트 크기 고정: 70 / 20 / 45 / 23
            f_t = load_font(sel_font, 70) # 활동명
            f_d = load_font(sel_font, 20) # 날짜
            f_n = load_font(sel_font, 45) # 숫자
            f_l = load_font(sel_font, 23) # 유닛
            f_path = f"font_{sel_font}_70.ttf"
            
            # 배경: 사진 없으면 검은색
            canvas = make_smart_collage(bg_files, (CW, CH)) if bg_files else Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
            overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
            
            # [규칙 2] 단위 소문자 km, bpm 고정
            items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]

            # 박스 렌더링
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
            
            if box_orient == "Vertical":
                draw_styled_text(draw, (rx+40, ry+30), v_act, f_t, m_color, use_shadow)
                draw_styled_text(draw, (rx+40, ry+125), v_date, f_d, "#AAAAAA", use_shadow)
                y_c = ry + 190
                for lab, val in items:
                    draw_styled_text(draw, (rx+40, y_c), lab.lower(), f_l, "#AAAAAA", use_shadow)
                    draw_styled_text(draw, (rx+40, y_c+35), val.lower(), f_n, sub_color, use_shadow)
                    y_c += 100
            else:
                t_x = rx + (rw - draw.textlength(v_act, font=f_t)) // 2
                draw_styled_text(draw, (t_x, ry + 35), v_act, f_t, m_color, use_shadow)
                d_x = rx + (rw - draw.textlength(v_date, font=f_d)) // 2
                draw_styled_text(draw, (d_x, ry + 130), v_date, f_d, "#AAAAAA", use_shadow)
                sec_w = rw // 4
                for i, (lab, val) in enumerate(items):
                    cx = rx + (i * sec_w) + (sec_w // 2)
                    draw_styled_text(draw, (cx - draw.textlength(lab.lower(), font=f_l)//2, ry + 185), lab.lower(), f_l, "#AAAAAA", use_shadow)
                    draw_styled_text(draw, (cx - draw.textlength(val.lower(), font=f_n)//2, ry + 230), val.lower(), f_n, sub_color, use_shadow)

            # 지도/차트 및 로고 로직 (생략된 기존 부분)
            # ...
            
            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, width=300)
        except Exception as e:
            st.error(f"렌더링 중 오류: {e}")
