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

# --- [2. 세션 및 인증] ---
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

# --- [3. 사이드바: 오직 MANUAL EDIT만] ---
with st.sidebar:
    st.header("✍️ MANUAL EDIT")
    # 아래 로직에서 사용될 변수들을 미리 session_state로 관리하여 사이드바에서 수정 가능케 함
    s_v_act = st.text_input("활동명", key="manual_act")
    s_v_date = st.text_input("날짜", key="manual_date")
    s_v_dist = st.text_input("거리 km", key="manual_dist")
    s_v_time = st.text_input("시간", key="manual_time")
    s_v_pace = st.text_input("페이스", key="manual_pace")
    s_v_hr = st.text_input("심박 bpm", key="manual_hr")

# --- [4. 메인 최상단: TITAN BOY & Strava] ---
st.title("TITAN BOY")
if st.session_state['access_token'] is None:
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force"
    st.link_button("🚀 Strava 연동하기", auth_url, use_container_width=True)
else:
    c_status, c_logout = st.columns([4, 1])
    with c_status: st.success("✅ Strava 연결됨")
    with c_logout: st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)

st.divider()

# --- [5. 메인 2열 레이아웃: 좌(PREVIEW & FILES) / 우(DESIGN)] ---
col_main, col_design = st.columns([2, 1], gap="large")

with col_main:
    st.subheader("📝 ACTIVITY & PREVIEW")
    
    # 상단: 모드 및 파일 업로드
    m1, m2 = st.columns(2)
    with m1: mode = st.radio("모드 선택", ["DAILY", "WEEKLY"], horizontal=True)
    with m2: 
        acts = []
        if st.session_state['access_token']:
            headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
            r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=30", headers=headers)
            if r.status_code == 200: acts = r.json()
        
        if acts:
            act_options = [f"{act['start_date_local'][:10]} - {act['name']}" for act in acts]
            sel_str = st.selectbox("🏃 활동 선택", act_options)
            a = acts[act_options.index(sel_str)]
            
            # 사이드바 입력값이 비어있을 때만 스트라바 데이터로 초기화
            if not st.session_state.manual_act:
                d_km = a.get('distance', 0)/1000; m_sec = a.get('moving_time', 0)
                st.session_state.manual_act = a['name']
                st.session_state.manual_date = a['start_date_local'][:10]
                st.session_state.manual_dist = f"{d_km:.2f}"
                st.session_state.manual_time = f"{m_sec//3600:02d}:{(m_sec%3600)//60:02d}:{m_sec%60:02d}"
                st.session_state.manual_pace = f"{int((m_sec/d_km)//60)}'{int((m_sec/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
                st.session_state.manual_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"

    bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
    log_file = st.file_uploader("🔘 원형 로고", type=['jpg','jpeg','png'])
    
    # 미리보기 영역 (이미지 생성 로직이 이 아래에 위치)
    preview_placeholder = st.empty()

with col_design:
    st.subheader("🎨 DESIGN")
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트 선택", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    
    m_color = st.color_picker("포인트 컬러", "#FFD700")
    sub_color = st.color_picker("서브 컬러", "#FFFFFF")
    
    ry = st.number_input("박스 Y 위치", 0, 1920, 1400 if mode=="DAILY" else 750)
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    vis_sz = st.slider("지도/그래프 크기", 50, 1080, 200 if mode=="DAILY" else 1080)
    vis_alpha = st.slider("지도/그래프 투명도", 0, 255, 150)
    
    if mode == "WEEKLY":
        g_y_off = st.slider("그래프 상단 여백", 0, 500, 50)

# --- [6. 렌더링 엔진 (실시간 업데이트)] ---
# (이전에 완성한 가로모드 1080 너비 고정, 가운데 정렬, 4분할 로직을 적용)
try:
    CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1080)
    f_t, f_d, f_n, f_l = load_font(sel_font, 90), load_font(sel_font, 30), load_font(sel_font, 60), load_font(sel_font, 20)
    
    if bg_files:
        canvas = ImageOps.fit(ImageOps.exif_transpose(Image.open(bg_files[0])).convert("RGBA"), (CW, CH))
    else:
        canvas = Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
    
    overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
    
    # 데이터 매핑 (사이드바 수동 입력값 우선)
    v_act, v_date, v_dist, v_time, v_pace, v_hr = st.session_state.manual_act, st.session_state.manual_date, st.session_state.manual_dist, st.session_state.manual_time, st.session_state.manual_pace, st.session_state.manual_hr
    items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]

    # [렌더링 로직 적용 시작]
    if box_orient == "Vertical":
        draw.rectangle([70, ry, 70+480, ry+550], fill=(0,0,0,box_alpha))
        # ... (생략된 세로 렌더링)
    else:
        # 가로모드: 너비 1080 고정 및 가운데 정렬
        draw.rectangle([0, ry, 1080, ry+260], fill=(0,0,0,box_alpha))
        t_w = draw.textlength(v_act, font=f_t)
        draw.text(((1080 - t_w) // 2, ry + 35), v_act, font=f_t, fill=m_color)
        # ... (생략된 4분할 배치 로직)
    
    final_img = Image.alpha_composite(canvas, overlay).convert("RGB")
    
    # 미리보기 위치에 이미지 배치
    with col_main:
        st.image(final_img, use_container_width=True)
        buf = io.BytesIO(); final_img.save(buf, format="JPEG", quality=95)
        st.download_button(f"📸 {mode} DOWNLOAD", buf.getvalue(), f"{mode.lower()}.jpg", use_container_width=True)

except Exception as e:
    with col_main:
        st.info("왼쪽 상단의 활동을 선택하거나 배경 사진을 올려주세요.")
