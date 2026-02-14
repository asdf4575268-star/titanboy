import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl

# --- [1. 기본 설정 및 제목] ---
st.set_page_config(page_title="TITAN BOY", layout="wide")
mpl.use('Agg')

API_CONFIGS = {
    "PRIMARY": {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'},
    "SECONDARY": {"ID": '202274', "SECRET": '63f6a7007ebe6b405763fc3104e17bb53b468ad0'}
}
CURRENT_CFG = API_CONFIGS["PRIMARY"] 
CLIENT_ID, CLIENT_SECRET = CURRENT_CFG["ID"], CURRENT_CFG["SECRET"]
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

# --- [2. 세션 및 인증 로직] ---
if 'access_token' not in st.session_state: st.session_state['access_token'] = None

def logout_and_clear():
    st.cache_data.clear(); st.cache_resource.clear(); st.session_state.clear(); st.query_params.clear(); st.rerun()

query_params = st.query_params
if "code" in query_params and st.session_state['access_token'] is None:
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": query_params["code"], "grant_type": "authorization_code"
        }, timeout=15).json()
        if 'access_token' in res:
            st.session_state['access_token'] = res['access_token']
            st.query_params.clear(); st.rerun()
    except: pass

# --- [3. 사이드바: 입력창 및 OCR 설정 숨기기] ---
with st.sidebar:
    st.title("⚙️ INPUT & OCR")
    mode = st.radio("모드 선택", ["DAILY", "WEEKLY"], horizontal=True)
    
    st.subheader("📸 FILES")
    bg_files = st.file_uploader("배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("원형 로고", type=['jpg','jpeg','png'])
    
    # 데이터 로드 (Strava)
    v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", datetime.now().strftime("%Y-%m-%d"), "0.00", "00:00:00", "0'00\"", "0"
    acts = []
    if st.session_state['access_token']:
        headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
        try:
            r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)
            if r.status_code == 200: acts = r.json()
        except: pass
    
    a = None
    if acts:
        act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
        sel_str = st.selectbox("활동 선택", act_options)
        a = acts[act_options.index(sel_str)]
        if mode == "DAILY":
            d_km = a.get('distance', 0)/1000; m_sec = a.get('moving_time', 0)
            v_act, v_date, v_dist = a['name'], a['start_date_local'][:10], f"{d_km:.2f}"
            v_time = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}"
            v_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
            v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
    
    st.subheader("✍️ MANUAL EDIT")
    v_act = st.text_input("활동명", v_act)
    v_date = st.text_input("날짜", v_date)
    v_dist = st.text_input("거리 km", v_dist)
    v_time = st.text_input("시간", v_time)
    v_pace = st.text_input("페이스", v_pace)
    v_hr = st.text_input("심박 bpm", v_hr)

# --- [4. 메인 화면 레이아웃] ---
# 상단 타이틀 및 연동 버튼
st.title("TITAN BOY")

if st.session_state['access_token'] is None:
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url, use_container_width=True)
else:
    c_status, c_logout = st.columns([4, 1])
    with c_status: st.success("✅ Strava 연결됨")
    with c_logout: st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)

st.divider()

# 메인 2열 구성 (디자인 설정 / 사진 확인)
col_design, col_preview = st.columns([1, 1.5], gap="large")

with col_design:
    st.header("🎨 DESIGN")
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트 선택", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    
    # 색상 선택 (가독성을 위해 버튼형 옵션 유지 또는 피커 사용)
    m_color = st.color_picker("포인트 컬러 (활동명)", "#FFD700")
    sub_color = st.color_picker("서브 컬러 (데이터)", "#FFFFFF")
    
    # 위치 조절 슬라이더
    ry = st.number_input("박스 Y 위치", 0, 1920, 1400 if mode=="DAILY" else 750)
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    vis_sz = st.slider("지도/그래프 크기", 50, 1080, 200 if mode=="DAILY" else 1080)
    vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 150)
    
    if mode == "WEEKLY":
        g_y_off = st.slider("그래프 상단 여백", 0, 500, 50)

# --- [5. 렌더링 및 결과 출력] ---
with col_preview:
    try:
        # 유틸리티 함수 로직 (생략 - 기존 코드의 load_font, create_bar_chart 등 사용)
        CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1080)
        f_t, f_d, f_n, f_l = load_font(sel_font, 90), load_font(sel_font, 30), load_font(sel_font, 60), load_font(sel_font, 20)
        
        if bg_files:
            canvas = ImageOps.fit(ImageOps.exif_transpose(Image.open(bg_files[0])).convert("RGBA"), (CW, CH))
        else:
            canvas = Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
        
        overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
        
        # [렌더링 로직: 가로모드 중앙정렬/4분할 포함]
        # ... (이전 답변에서 완성한 렌더링 코드 적용) ...
        
        # 예시: 가로모드 로직 일부
        if box_orient == "Horizontal":
            cur_rw = 1080
            draw.rectangle([0, ry, 1080, ry + 260], fill=(0,0,0,box_alpha))
            # 활동명 중앙 정렬 등 실행...
            
        res_img = Image.alpha_composite(canvas, overlay).convert("RGB")
        st.image(res_img, use_container_width=True, caption="PREVIEW")
        
        buf = io.BytesIO(); res_img.save(buf, format="JPEG", quality=95)
        st.download_button(f"📸 {mode} DOWNLOAD", buf.getvalue(), f"{mode.lower()}.jpg", use_container_width=True)
        
    except Exception as e:
        st.info("왼쪽 사이드바에서 활동을 선택하거나 사진을 업로드해 주세요.")
