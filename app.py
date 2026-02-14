import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, time
from datetime import datetime, timedelta

# --- [1. 설정] ---
CLIENT_ID = '202274'
CLIENT_SECRET = 'cf2ab22bb9995254e6ea68ac3c942572f7114c9a'
# 실제 주소 끝에 / 가 붙어있는지 확인해 보세요.
ACTUAL_URL = "https://titanboy-5fxenvcchdubwx3swjh8ut.streamlit.app"

st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# --- [2. 핵심: 인증 로직 보강] ---
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# 현재 주소창의 파라미터 읽기
params = st.query_params

# 중요: 코드가 주소창에 들어왔다면
if "code" in params and st.session_state['access_token'] is None:
    code = params["code"]
    # 1. 즉시 토큰 교환 시도
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": code, "grant_type": "authorization_code"
    })
    
    if res.status_code == 200:
        # 2. 성공 시 세션에 저장
        st.session_state['access_token'] = res.json()['access_token']
        # 3. 주소창을 완전히 비우고 재시작 (코드 찌꺼기 제거)
        st.query_params.clear()
        st.rerun()
    else:
        st.error(f"인증 실패: {res.text}") # 왜 실패했는지 에러 메시지 출력

# --- [3. 화면 분기] ---
if not st.session_state['access_token']:
    st.title("🏃 Garmin Photo Dashboard")
    st.warning("로그인이 필요합니다. 아래 버튼을 눌러 승인해 주세요.")
    
    # 승인 주소 생성
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=activity:read_all&approval_prompt=force"
    
    st.link_button("🚀 Strava 연동하기", auth_url)
    
    if st.button("🔌 세션 강제 리셋 (무한 반복 시 클릭)"):
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()
    st.stop()

# --- [4. 이후 기능 로직 (성공 시에만 진입)] ---
st.success("✅ 인증 완료! 활동 데이터를 불러오는 중...")
# (이 아래에 이전 대화의 DAILY/WEEKLY 전체 코드를 그대로 붙여넣으세요)

# --- [5. 사이드바 - 디자인 가이드 준수 (80, 20, 50)] ---
with st.sidebar:
    if st.button("Logout"): full_reset()
    app_mode = st.radio("작업 모드", ["DAILY", "WEEKLY"])
    st.markdown("---")
    selected_font = st.selectbox("폰트", ["Jua", "DoHyeon", "GothicA1", "BlackHanSans"])
    main_color = st.color_picker("활동명 색상", "#FFD700")
    num_color = st.color_picker("정보 색상", "#FFFFFF")
    
    t_sz = st.slider("활동명 크기", 10, 200, 80)
    d_sz = st.slider("날짜 크기", 5, 100, 20)
    n_sz = st.slider("숫자 크기", 10, 300, 50)
    l_sz = st.slider("라벨 크기", 10, 80, 25)
    
    st.markdown("---")
    rx, ry = st.slider("X 위치", 0, 1080, 70), st.slider("Y 위치", 0, 1920, 1150)
    rw, rh = st.slider("너비", 300, 1000, 500), st.slider("높이", 300, 1200, 720)
    alpha, m_alpha = st.slider("박스 투명도", 0, 255, 60), st.slider("지도 투명도", 0, 255, 100)

# --- [6. 메인 로직] ---
headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}

if app_mode == "DAILY":
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers)
    if act_res.status_code == 200:
        acts = act_res.json()
        sel = st.selectbox("활동 선택", [f"{a['start_date_local']} - {a['name']}" for a in acts])
        idx = [f"{a['start_date_local']} - {a['name']}" for a in acts].index(sel)
        a = acts[idx]

        # 데이터 파싱
        dist_km = a.get('distance', 0) / 1000
        m_time = a.get('moving_time', 0)
        time_v = f"{m_time//3600:02d}:{(m_time%3600)//60:02d}:{m_time%60:02d}" if m_time >= 3600 else f"{m_time//60:02d}:{m_time%60:02d}"
        pace_v = f"{int((m_time/dist_km)//60)}:{int((m_time/dist_km)%60):02d}" if dist_km > 0 else "0:00"
        hr_v = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"

        col1, col2 = st.columns(2)
        with col1:
            bg_f = st.file_uploader("배경 사진 (가로 사진도 자동 세로 크롭)", type=['jpg','png','jpeg'])
            log_f = st.file_uploader("로고 아이콘", type=['jpg','png','jpeg'])
        with col2:
            v_act = st.text_input("활동명", a['name'])
            v_date = st.text_input("날짜", a['start_date_local'][:16].replace("T", " "))
            v_dist = st.text_input("거리(km)", f"{dist_km:.2f}")
            v_pace = st.text_input("페이스", pace_v)
            v_hr = st.text_input("심박(bpm)", hr_v)
            v_weather = st.text_input("날씨", "")

        if bg_f:
            # 🌟 가로 사진도 세로(1080x1920)로 강제 크롭 배치
            orig = ImageOps.exif_transpose(Image.open(bg_f))
            canvas = ImageOps.fit(orig.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
            overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            f_t, f_d, f_n, f_l = load_custom_font(selected_font, t_sz), load_custom_font(selected_font, d_sz), load_custom_font(selected_font, n_sz), load_custom_font(selected_font, l_sz)

            # 박스 & 지도
            draw.rectangle([rx, ry, rx+rw, ry+rh], fill=(0,0,0,alpha))
            poly = a.get('map', {}).get('summary_polyline', "")
            if poly:
                pts = polyline.decode(poly)
                lats, lons = [p[0] for p in pts], [p[1] for p in pts]
                mi_la, ma_la, mi_lo, ma_lo = min(lats), max(lats), min(lons), max(lons)
                m_img = Image.new("RGBA", (rw, rh), (0,0,0,0))
                m_draw = ImageDraw.Draw(m_img)
                def sc(p):
                    x = (p[1]-mi_lo)/(ma_lo-mi_lo+1e-9)*(rw*0.7) + (rw*0.15)
                    y = (rh*0.7)-(p[0]-mi_la)/(ma_la-mi_la+1e-9)*(rh*0.7) + (rh*0.15)
                    return (x, y)
                m_draw.line([sc(p) for p in pts], fill=(255,215,0,m_alpha), width=8)
                canvas.paste(m_img, (rx, ry), m_img)

            # 텍스트 정보 (km, bpm 소문자)
            draw.text((rx+50, ry+40), v_act, font=f_t, fill=main_color)
            draw.text((rx+rw-50, ry+40+t_sz+5), v_date, font=f_d, fill=num_color, anchor="ra")
            
            items = [("DISTANCE", f"{v_dist} km"), ("AVG PACE", f"{v_pace} /km"), ("AVG HR", f"{v_hr} bpm")]
            if v_weather: items.append(("WEATHER", v_weather))
            
            y_start = ry + t_sz + d_sz + 60
            gap = (rh - (y_start-ry) - 40) / len(items)
            for i, (lab, val) in enumerate(items):
                draw.text((rx+60, y_start + i*gap), lab, font=f_l, fill="#AAAAAA")
                draw.text((rx+60, y_start + i*gap + l_sz + 2), val, font=f_n, fill=num_color)

            if log_f:
                logo = get_circle_logo(log_f)
                canvas.paste(logo, (910, 60), logo)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, use_container_width=True)
            buf = io.BytesIO()
            final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 사진 저장", buf.getvalue(), "garmin.jpg")

