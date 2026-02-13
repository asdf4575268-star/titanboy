import streamlit as st
from PIL import Image, ImageOps
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import os
import requests
import polyline
from datetime import datetime, timedelta

# --- [1. 기본 설정] ---
CLIENT_ID = '202275'
CLIENT_SECRET = '41f311299a14de733155c6c6e71505d3063fc31c'
st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# --- [2. 콜라주 생성 함수 (개수에 따라 자동 조절)] ---
def create_fixed_collage(image_files, canvas_size=(1080, 1080)):
# --- [2. 유틸리티 함수] ---
@st.cache_resource
def load_custom_font(font_type, size):
    fonts = {
        "Impact(BlackHan)": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "Gothic(DoHyeon)": "https://github.com/google/fonts/raw/main/ofl/dohyeon/DoHyeon-Regular.ttf",
        "Stylish(Jua)": "https://github.com/google/fonts/raw/main/ofl/jua/Jua-Regular.ttf",
        "Clean(Noto)": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"
    }
    font_url = fonts[font_type]
    font_path = f"{font_type.split('(')[0]}.ttf"
    if not os.path.exists(font_path):
        res = requests.get(font_url)
        with open(font_path, "wb") as f: f.write(res.content)
    return ImageFont.truetype(font_path, int(size))

def get_circle_logo(img_file, size=(130, 130)):
    img = Image.open(img_file).convert("RGBA")
    img = ImageOps.fit(img, size, centering=(0.5, 0.5))
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    img.putalpha(mask)
    return img

def create_collage(image_files, target_size=(1080, 1080)):
    imgs = [ImageOps.exif_transpose(Image.open(f).convert("RGB")) for f in image_files]
    count = len(imgs)
    if count == 0: return None

    # 1. 개수에 따른 최적의 행렬(Grid) 계산
    if count <= 3:
        cols, rows = count, 1
    elif count <= 4:
        cols, rows = 2, 2
    elif count <= 6:
        cols, rows = 3, 2
    elif count <= 9:
        cols, rows = 3, 3
    else:
        cols = 4
        rows = (count + cols - 1) // cols

    # 2. 한 칸당 크기 결정 (여백 없이 꽉 채우기 위해)
    cell_w = canvas_size[0] // cols
    cell_h = canvas_size[1] // rows
    
    # 3. 캔버스 생성
    collage = Image.new("RGB", canvas_size, (255, 255, 255))
    
    cols = 2 if count <= 4 else 3
    rows = (count + cols - 1) // cols
    cell_w, cell_h = target_size[0] // cols, target_size[1] // rows
    collage = Image.new("RGB", target_size, (255, 255, 255))
    for i, img in enumerate(imgs):
        # 4. ImageOps.fit을 사용하여 여백 없이 칸에 꽉 맞춤 (중앙 기준 크롭)
        img = ImageOps.fit(img, (cell_w, cell_h), centering=(0.5, 0.5))
        
        x = (i % cols) * cell_w
        y = (i // cols) * cell_h
        collage.paste(img, (x, y))
        
        collage.paste(img, ((i % cols) * cell_w, (i // cols) * cell_h))
    return collage

# --- [3. 스트라바 연동 및 메뉴] ---
def draw_route(polyline_str, route_color="white", size=(300, 300)):
    if not polyline_str: return None
    try:
        points = polyline.decode(polyline_str)
        lats, lons = [p[0] for p in points], [p[1] for p in points]
        min_lat, max_lat, min_lon, max_lon = min(lats), max(lats), min(lons), max(lons)
        route_img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(route_img)
        def scale(p):
            x = (p[1] - min_lon) / (max_lon - min_lon + 1e-9) * (size[0]-40) + 20
            y = (size[1]-40) - ((p[0] - min_lat) / (max_lat - min_lat + 1e-9) * (size[1]-40)) + 20
            return (x, y)
        draw.line([scale(p) for p in points], fill=route_color, width=6)
        return route_img
    except: return None

# --- [3. 메뉴 및 스트라바 연동] ---
app_mode = st.sidebar.radio("🚀작업 모드", ["DAILY", "WEEKLY"])

if 'access_token' not in st.session_state:
    st.link_button("🧡 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri=https://{st.context.headers.get('host')}/&scope=activity:read_all&approval_prompt=force")
    st.link_button("Strava", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri=https://{st.context.headers.get('host')}/&scope=activity:read_all&approval_prompt=force")
    if "code" in st.query_params:
        res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": st.query_params["code"], "grant_type": "authorization_code"})
        if res.status_code == 200:
            st.session_state['access_token'] = res.json()['access_token']
            st.rerun()
else:
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}

# --- [4. DAILY 모드] ---
if app_mode == "DAILY" and 'access_token' in st.session_state:
    act_res = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=10", headers=headers)
    if act_res.status_code == 200:
        acts = act_res.json()
        sel = st.selectbox("기록 선택", [f"{a['start_date_local']} - {a['name']}" for a in acts])
        a = acts[[f"{x['start_date_local']} - {x['name']}" for x in acts].index(sel)]
        raw_dist = a.get('distance', 0) / 1000
        dist_init = f"{raw_dist:.2f}"
        total_sec = a.get('moving_time', 0)
        pace_init = f"{int((total_sec/raw_dist)//60)}:{int((total_sec/raw_dist)%60):02d}" if raw_dist > 0 else "0:00"
        time_init = f"{total_sec // 60}:{total_sec % 60:02d}"
        hr_init = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
        date_init = datetime.strptime(a['start_date_local'], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y. %m. %d | %H:%M")
        map_polyline = a.get('map', {}).get('summary_polyline', "")

app_mode = st.sidebar.radio("🚀 작업 모드", ["단일 활동 인증", "주간 기록 확인 & 콜라주"])
    with st.sidebar:
        st.header("⚙️ 커스텀 설정")
        # 로그 사진 업로더 제거됨
        bg_file = st.file_uploader("1. 배경 사진", type=['jpg', 'jpeg', 'png'])
        log_file = st.file_uploader("2. 로고 아이콘", type=['jpg', 'jpeg', 'png'])
        
        st.markdown("---")
        selected_font = st.selectbox("폰트 선택", ["Impact(BlackHan)", "Gothic(DoHyeon)", "Stylish(Jua)", "Clean(Noto)"])
        
        c1, c2 = st.columns(2)
        t_color = c1.color_picker("활동명 색상", "#FFD700")
        v_color = c2.color_picker("수치/날짜 색상", "#FFFFFF")

# --- [4. 단일 활동 인증 (기존 레이아웃 유지)] ---
if app_mode == "단일 활동 인증" and 'access_token' in st.session_state:
    # ... (기존 단일 인증 로직 동일하게 유지)
    st.info("단일 인증 기능을 사용하시려면 배경 사진을 업로드하세요.")
        map_color_choice = st.radio("🗺️ 지도 색상", ["White", "Black"], horizontal=True)
        r_color = "white" if map_color_choice == "White" else "black"

# --- [5. 주간 기록 및 자동 콜라주 모드] ---
elif app_mode == "주간 기록 확인 & 콜라주" and 'access_token' in st.session_state:
    headers = {'Authorization': f"Bearer {st.session_state['access_token']}"}
        st.subheader("📏 글자 크기")
        title_size = st.slider("활동명 크기", 10, 200, 70) 
        date_size = st.slider("날짜 크기", 10, 100, 30)  
        num_size = st.slider("숫자 크기", 10, 150, 50)   
        label_size = st.slider("라벨 크기", 10, 80, 25)    
        
        st.subheader("📦 박스 설정")
        box_width = st.slider("박스 가로 길이", 300, 1080, 450)
        box_height = st.slider("박스 세로 길이", 100, 1200, 560)
        rect_x = st.slider("박스 좌우 위치", 0, 1080, 70)
        rect_y = st.slider("박스 상하 위치", 0, 1920, 1250)
        box_alpha = st.slider("박스 투명도", 0, 255, 50)
        rotate_deg = st.selectbox("배경 회전", [0, 90, 180, 270], index=0)

    if bg_file:
        st.markdown("---")
        act_v = st.text_input("활동명", "RUNNING")
        date_v = st.text_input("날짜", date_init)
        v1, v2, v3, v4 = st.columns(4)
        dist_v, pace_v, time_v, hr_v = v1.text_input("거리", dist_init), v2.text_input("페이스", pace_init), v3.text_input("시간", time_init), v4.text_input("심박", hr_init)
        
        bg_img = ImageOps.exif_transpose(Image.open(bg_file))
        if rotate_deg != 0: bg_img = bg_img.rotate(rotate_deg, expand=True)
        canvas = ImageOps.fit(bg_img.convert("RGBA"), (1080, 1920), centering=(0.5, 0.5))
        overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        draw.rectangle([rect_x, rect_y, rect_x + box_width, rect_y + box_height], fill=(0, 0, 0, box_alpha))
        f_t, f_d, f_n, f_l = load_custom_font(selected_font, title_size), load_custom_font(selected_font, date_size), load_custom_font(selected_font, num_size), load_custom_font(selected_font, label_size)
        
        draw.text((rect_x + 50, rect_y + 40), act_v, font=f_t, fill=t_color)
        line_y = rect_y + title_size + 80
        draw.text((rect_x + box_width - 50, line_y - date_size - 10), date_v, font=f_d, fill=v_color, anchor="ra")
        draw.line([(rect_x + 50, line_y), (rect_x + box_width - 50, line_y)], fill=(255, 255, 255, 100), width=3)
        
        # [km, bpm 소문자 고정]
        items = [("DISTANCE", f"{dist_v} km"), ("AVG PACE", f"{pace_v} /km"), ("TIME", time_v), ("AVG HR", f"{hr_v} bpm")]
        row_gap = (box_height - (line_y - rect_y) - 60) // 4
        for i, (lab, val) in enumerate(items):
            py = line_y + 30 + (i * row_gap)
            draw.text((rect_x + 60, py), lab, font=f_l, fill="#AAAAAA")
            draw.text((rect_x + 60, py + label_size + 5), val, font=f_n, fill=v_color)
        
        # 로고 아이콘 합성 (기존 log_file 사용)
        if log_file:
            circle_logo = get_circle_logo(log_file)
            canvas.paste(circle_logo, (900, 60), circle_logo)
        
        if map_polyline:
            route_img = draw_route(map_polyline, route_color=r_color)
            if route_img: canvas.paste(route_img, (rect_x + 50, rect_y - 320), route_img)
            
        final_img = Image.alpha_composite(canvas, overlay).convert("RGB")
        st.image(final_img, use_container_width=True)
        buf = io.BytesIO()
        final_img.save(buf, format="JPEG", quality=95)
        st.download_button("📸 DOWNLOAD", buf.getvalue(), "garmin_final.jpg")

# --- [5. WEEKLY 모드] ---
elif app_mode == "WEEKLY" and 'access_token' in st.session_state:
    after_ts = int((datetime.now() - timedelta(days=7)).timestamp())
    res = requests.get(f"https://www.strava.com/api/v3/athlete/activities?after={after_ts}", headers=headers)
    act_res = requests.get(f"https://www.strava.com/api/v3/athlete/activities?after={after_ts}", headers=headers)

    if res.status_code == 200:
        acts = res.json()
    if act_res.status_code == 200:
        acts = act_res.json()
        total_dist = sum(a.get('distance', 0) for a in acts) / 1000
        hr_list = [a.get('average_heartrate') for a in acts if a.get('average_heartrate')]
        avg_hr = sum(hr_list) / len(hr_list) if hr_list else 0
        total_time = sum(a.get('moving_time', 0) for a in acts)
        avg_hr = int(sum(h for h in [a.get('average_heartrate') for a in acts] if h) / len([h for h in [a.get('average_heartrate') for a in acts] if h])) if acts else 0
        avg_pace = f"{int((total_time/total_dist)//60)}:{int((total_time/total_dist)%60):02d}" if total_dist > 0 else "0:00"
        if total_dist > 0:
            avg_pace_raw = total_time / total_dist
            avg_pace_display = f"{int(avg_pace_raw // 60)}:{int(avg_pace_raw % 60):02d}"
        else:
            avg_pace_display = "0:00"

        st.title("📅 이번 주 운동 요약")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 거리", f"{total_dist:.2f} km")
        c2.metric("평균 페이스", f"{avg_pace} /km")
        c3.metric("평균 심박수", f"{avg_hr} bpm")
        c2.metric("평균 페이스", f"{avg_pace_display} /km")
        c3.metric("평균 심박수", f"{int(avg_hr)} bpm")
        c4.metric("활동 횟수", f"{len(acts)} 회")

        st.markdown("---")
        with st.sidebar:
            st.header("⚙️ 콜라주 설정")
            log_check = st.file_uploader("🖼️ 참고용 사진 상시 확인", type=['jpg', 'png'])

        if log_check:
            st.image(log_check, width=300, caption="상시 확인용")

        st.subheader("📸 자동 레이아웃 콜라주 생성")
        files = st.file_uploader("사진을 3장 이상 선택하세요 (자동 배치)", type=['jpg', 'png'], accept_multiple_files=True)
        
        st.subheader("📸 주간 콜라주")
        files = st.file_uploader("사진들을 선택하세요", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
        if files:
            if len(files) >= 3:
                collage_img = create_adaptive_collage(files)
                if collage_img:
                    st.image(collage_img, use_container_width=True, caption=f"{len(files)}장 자동 콜라주")
                    buf = io.BytesIO()
                    collage_img.save(buf, format="JPEG", quality=95)
                    st.download_button("📸 콜라주 저장", buf.getvalue(), "weekly_collage.jpg")
            else:
                st.warning("사진을 3장 이상 선택해야 콜라주가 생성됩니다.")


            collage = create_collage(files)
            if collage:
                st.image(collage, use_container_width=True)
                buf = io.BytesIO()
                collage.save(buf, format="JPEG", quality=95)
                st.download_button("📸 콜라주 저장", buf.getvalue(), "weekly_collage.jpg")
