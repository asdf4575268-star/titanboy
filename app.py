import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
import numpy as np
from datetime import datetime, timedelta
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
try:
    logo_img = Image.open("logo.png")
    st.set_page_config(layout="centered", page_title="TITAN BOY", page_icon=logo_img, initial_sidebar_state="collapsed")
except:
    st.set_page_config(layout="centered", page_title="TITAN BOY", initial_sidebar_state="collapsed")

# --- [2. 유틸리티 및 디자인 함수] ---
def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

def draw_styled_text(draw, pos, text, font, fill, shadow=True, anchor=None):
    if shadow:
        draw.text((pos[0]+2, pos[1]+2), text, font=font, fill=(0, 0, 0, 220), anchor=anchor)
    draw.text(pos, text, font=font, fill=fill, anchor=anchor)

def load_font(name, size):
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Bangers": "https://github.com/google/fonts/raw/main/ofl/bangers/Bangers-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf"
    }
    f_path = f"font_{name}.ttf"
    if not os.path.exists(f_path):
        try:
            r = requests.get(fonts[name])
            with open(f_path, "wb") as f: f.write(r.content)
        except: return ImageFont.load_default()
    try: return ImageFont.truetype(f_path, int(size))
    except: return ImageFont.load_default()

# --- [3. 인증 및 데이터 연동 (Strava 유지)] ---
DB_PATH = "archive_prism_total_v5.db"
acts = [] 

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS strava_tokens (id INTEGER PRIMARY KEY, access_token TEXT, refresh_token TEXT, expires_at INTEGER)")
        conn.commit(); conn.close()
    except: pass
init_db()

def handle_token_db(mode="load", data=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
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
                res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "refresh_token", "refresh_token": r_token}).json()
                if 'access_token' in res: handle_token_db("save", res); st.session_state['access_token'] = res['access_token']
            except: pass
        else: st.session_state['access_token'] = a_token

if "code" in st.query_params:
    code = st.query_params["code"]
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": code, "grant_type": "authorization_code"}).json()
    if 'access_token' in res: handle_token_db("save", res); st.session_state['access_token'] = res['access_token']; st.query_params.clear(); st.rerun()

if st.session_state.get('access_token'):
    if not st.session_state.get('cached_acts'):
        headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
        r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers)
        if r.status_code == 200: st.session_state['cached_acts'] = r.json()
        elif r.status_code == 401: st.session_state.clear(); st.rerun()
    acts = st.session_state.get('cached_acts', [])

# --- [4. 메인 화면 구성 및 UI] ---
def get_base64(path):
    try:
        with open(path, "rb") as f: return base64.b64encode(f.read()).decode()
    except: return ""

st.markdown("""<style>.header-wrap { display: flex; align-items: center; gap: 8px; } .header-wrap h1 { margin: 0; letter-spacing: -1px; }</style>""", unsafe_allow_html=True)
logo_base64 = get_base64("logo.png")
if logo_base64:
    st.markdown(f"""<div class="header-wrap"><img src="data:image/png;base64,{logo_base64}" width="90"><h1>TITAN BOY</h1></div>""", unsafe_allow_html=True)
else:
    st.markdown(f"""<div class="header-wrap"><h1>TITAN BOY</h1></div>""", unsafe_allow_html=True)

# 변수 초기화
bg_file = None; v_date, v_dist, v_pace, v_time, v_hr, a, poly = "2026.03.16", "10.00", "4'30\"", "45:00", "165", None, None

if not st.session_state.get('access_token'):
    auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force")
    st.link_button("🚀 Strava 연동하기", auth_url, use_container_width=True)
else:
    if st.button("🔓 로그아웃", use_container_width=True): st.session_state.clear(); st.query_params.clear(); st.rerun()
    
    # --- Section 1: 배경 사진 및 러닝 데이터 선택 ---
    with st.expander("📂 1. 데이터 및 사진 설정", expanded=True):
        bg_file = st.file_uploader("📸 배경 사진 (영상 몸체)", type=['jpg','jpeg','png'])
        
        if acts:
            act_opts = [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts]
            sel_act = st.selectbox("🏃 활동 선택", act_opts)
            a = acts[act_opts.index(sel_act)]
            if a and a.get('type') == 'Run':
                v_dist = f"{a.get('distance', 0)/1000:.2f}"; m_s = a.get('moving_time', 0)
                v_pace = f"{int((m_s/(a.get('distance',1)/1000))//60)}'{int((m_s/(a.get('distance',1)/1000))%60):02d}\"" if a.get('distance',0) > 0 else "0'00\""
                v_time = f"{int(m_s//3600):02d}:{int((m_s%3600)//60):02d}:{int(m_s%60):02d}" if m_s >= 3600 else f"{int(m_s//60):02d}:{int(m_s%60):02d}"
                v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
                poly = a.get('map', {}).get('summary_polyline')
            else:
                st.warning("⚠️ 러닝 활동만 애니메이션 제작이 가능합니다.")
                a = None

    # --- Section 2: 템플릿 선택 (runkku.app 스타일) ---
    with st.expander("🎨 2. 디자인 템플릿 선택", expanded=True):
        st.markdown("**원클릭 스타일 적용**")
        # 템플릿 프리셋 정의
        TEMPLATES = {
            "Minimal Bottom (하단 미니멀)": {"font": "Bangers", "m_color": "#FFFFFF", "s_color": "#AAAAAA", "rx": 540, "ry": 1650, "align": "center", "show_map": True},
            "Magazine Left (매거진 좌측)": {"font": "BlackHanSans", "m_color": "#FFD700", "s_color": "#FFFFFF", "rx": 80, "ry": 1200, "align": "left", "show_map": True},
            "Bold Center (중앙 강조)": {"font": "Lacquer", "m_color": "#FF4500", "s_color": "#FFFFFF", "rx": 540, "ry": 960, "align": "center", "show_map": False}
        }
        sel_temp_name = st.selectbox("템플릿 고르기", list(TEMPLATES.keys()))
        T = TEMPLATES[sel_temp_name]
        
        st.markdown("---")
        c_col1, c_col2 = st.columns(2)
        with c_col1: m_color = st.color_picker("포인트 컬러 (거리)", T["m_color"])
        with c_col2: sub_color = st.color_picker("서브 컬러 (정보)", T["s_color"])
        show_map = st.toggle("지도(루트) 표시", value=T["show_map"])

    # --- Section 3: 애니메이션 GIF 생성 및 미리보기 ---
    st.markdown("---")
    st.subheader("🎬 애니메이션 미리보기 및 저장")
    
    if bg_file and a:
        if st.button("✨ 애니메이션 GIF 생성 (시간 소요)", use_container_width=True):
            try:
                with st.spinner("km 숫자를 올리고 지도를 그리는 중... (약 10~15초)"):
                    # 1. 원본 이미지 로드 및 캔버스 설정
                    try:
                        orig_bg = Image.open(bg_file)
                        orig_bg = ImageOps.exif_transpose(orig_bg) # 사진 방향 바로잡기
                        # 인스타 스토리 비율(9:16)로 고정 크기 조정 (속도를 위해 540x960으로 축소)
                        CW, CH = (540, 960)
                        canvas_bg = ImageOps.fit(orig_bg.convert("RGBA"), (CW, CH), Image.Resampling.LANCZOS)
                    except:
                        st.error("❌ 배경 사진을 불러오지 못했습니다."); st.stop()

                    # 2. 폰트 로드 (영상 크기에 맞춰 조절)
                    f_m_km = load_font(T["font"], 120) # 거리 숫자
                    f_s_unit = load_font(T["font"], 40) # 'km' 단위
                    f_info = load_font("BlackHanSans", 25) # 페이스, 시간, 심박
                    
                    # 3. 지도(루트) 레이어 미리 준비
                    map_layer = Image.new("RGBA", (CW, CH), (0,0,0,0))
                    if show_map and poly:
                        pts = polyline.decode(poly)
                        if pts:
                            m_draw = ImageDraw.Draw(map_layer)
                            lats, lons = zip(*pts)
                            # 지도를 중앙 상단 빈 공간에 배치
                            ms = 200 # 지도 크기
                            mx, my = (CW - ms)//2, 150 
                            def tr(la, lo): return mx+10+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(ms-20), (my+ms-10)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(ms-20)
                            m_draw.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, 200), width=4)

                    # 4. 애니메이션 프레임 생성 (숫자 카운트업 0.00 -> 최종 km)
                    frames = []
                    final_dist_float = float(v_dist)
                    num_frames = 30 # 총 프레임 수 (움짤 길이 조절)
                    
                    # 정해진 위치(rx, ry) 및 정렬(align) 방식 적용
                    rx, ry = T["rx"]//2, T["ry"]//2 # 1080 기준 좌표를 540 기준으로 나눔
                    
                    for i in range(num_frames + 10): # 마지막에 10프레임 멈춤 효과
                        # 현재 프레임의 거리 계산 (점점 느려지는 효과)
                        pct = i / num_frames
                        if pct > 1.0: pct = 1.0
                        # Ease-out 효과 (0 -> 1.0)
                        eased_pct = 1 - (1 - pct) * (1 - pct)
                        curr_dist = final_dist_float * eased_pct
                        
                        # 프레임 배경 복사
                        frame = canvas_bg.copy()
                        overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
                        
                        # 4-1. 지도(루트) 그리기
                        if show_map: overlay.paste(map_layer, (0,0), map_layer)
                        
                        # 4-2. 데이터 텍스트 배치
                        # 정보 텍스트 (페이스, 시간, 심박)
                        info_text = f"{v_pace}   {v_time}   {v_hr} bpm"
                        info_fill = hex_to_rgba(sub_color, 230)
                        # 거리 숫자 및 단위
                        dist_text = f"{curr_dist:.2f}"
                        dist_fill = hex_to_rgba(m_color, 255)
                        
                        if T["align"] == "center":
                            anchor = "mm" # 중앙 정렬
                            # 서브 정보
                            draw_styled_text(draw, (rx, ry - 70), info_text, f_info, info_fill, shadow=True, anchor=anchor)
                            # 거리 숫자
                            draw_styled_text(draw, (rx, ry), dist_text, f_m_km, dist_fill, shadow=True, anchor=anchor)
                            # 'km' 단위 (숫자 바로 아래)
                            draw_styled_text(draw, (rx, ry + 60), "km", f_s_unit, info_fill, shadow=True, anchor=anchor)
                        else:
                            anchor = "lm" # 좌측 정렬
                            # 서브 정보
                            draw_styled_text(draw, (rx, ry), info_text, f_info, info_fill, shadow=True, anchor=anchor)
                            # 거리 숫자
                            draw_styled_text(draw, (rx, ry + 70), dist_text, f_m_km, dist_fill, shadow=True, anchor=anchor)
                            # 'km' 단위 (숫자 우측)
                            d_w = draw.textlength(dist_text, f_m_km)
                            draw_styled_text(draw, (rx + d_w + 10, ry + 85), "km", f_s_unit, info_fill, shadow=True, anchor=anchor)
                        
                        # 배경에 오버레이 합치기
                        comp = Image.alpha_composite(frame, overlay).convert("RGB")
                        frames.append(comp)

                    # 5. 메모리 내에서 GIF로 변환
                    buf = io.BytesIO()
                    # duration: 프레임당 속도(ms), loop=0: 무한반복
                    frames[0].save(buf, format='GIF', save_all=True, append_images=frames[1:], duration=60, loop=0, quality=85)
                    gif_bytes = buf.getvalue()
                    
                    # 6. 결과물 출력
                    st.success("✅ 애니메이션 GIF 생성 완료!")
                    # 미리보기 (GIF는 st.image로 재생 가능)
                    st.image(gif_bytes, use_container_width=True, caption=f"TITAN BOY: {v_dist} km 카운트업")
                    
                    # 다운로드 버튼
                    st.download_button(label="📸 애니메이션(GIF) 다운로드", data=gif_bytes, file_name=f"titanboy_{v_dist}km.gif", mime="image/gif", use_container_width=True)

            except Exception as e:
                st.error(f"🎬 애니메이션 제작 중 오류 발생: {e}")
    else:
        st.info("💡 1단계에서 '배경 사진'을 업로드하고 '러닝 활동'을 선택하면, 움직이는 기록을 만들 수 있습니다.")
