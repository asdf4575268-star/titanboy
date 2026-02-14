import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline

# --- [기본 설정] ---
st.set_page_config(page_title="Garmin Photo Dashboard", layout="wide")

# 활동명 90, 날짜 30, 숫자 60 고정
T_SZ, D_SZ, N_SZ, L_SZ = 90, 30, 60, 20

# 폰트 로드 함수 (로컬 폰트 미사용)
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

# --- [UI 레이아웃 구성] ---
# 요청하신 대로 OCR/커스텀 설정은 사이드로 빼고 사진 확인 위주로 구성
with st.sidebar:
    st.header("⚙️ CUSTOM SETTING")
    show_box = st.checkbox("로그 박스 표시", value=True)
    box_orient = st.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
    sel_font = st.selectbox("폰트 선택", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
    m_color = st.color_picker("포인트 컬러 (활동명)", "#FFD700")
    sub_color = st.color_picker("서브 컬러 (데이터)", "#FFFFFF")
    box_alpha = st.slider("박스 투명도", 0, 255, 110)
    
    st.divider()
    st.header("🔍 OCR MENU (준비 중)")
    st.info("이미지에서 텍스트를 추출하는 기능이 이곳에 배치될 예정입니다.")

# 메인 화면: 데이터 입력과 사진 확인
col1, col2 = st.columns([1, 1.5], gap="large")

with col1:
    st.header("📸 DATA INPUT")
    bg_file = st.file_uploader("배경 사진 업로드", type=['jpg', 'jpeg', 'png'])
    log_file = st.file_uploader("원형 로고 업로드", type=['jpg', 'jpeg', 'png'])
    
    st.divider()
    # 직접 입력 가능한 칸 제공
    v_act = st.text_input("활동명 (Title)", "MORNING RUN")
    v_date = st.text_input("날짜 (Date)", "2026.02.14")
    
    c1, c2 = st.columns(2)
    v_dist = c1.text_input("거리 (km)", "5.00")
    v_time = c2.text_input("시간 (Time)", "00:25:00")
    
    c3, c4 = st.columns(2)
    v_pace = c3.text_input("페이스 (Pace)", "5'00\"")
    v_hr = c4.text_input("심박 (bpm)", "150")

    # 박스 위치 수동 조절
    d_rx, d_ry, d_rw, d_rh = (70, 1600, 940, 260) if box_orient == "Horizontal" else (70, 1250, 480, 600)
    rx = st.number_input("박스 X 위치", 0, 1080, d_rx)
    ry = st.number_input("박스 Y 위치", 0, 1920, d_ry)
    rw = st.number_input("박스 너비", 100, 1080, d_rw)
    rh = st.number_input("박스 높이", 100, 1920, d_rh)

with col2:
    st.header("🖼️ PREVIEW")
    if bg_file:
        try:
            # 폰트 불러오기
            f_t, f_d, f_n, f_l = load_font(sel_font, T_SZ), load_font(sel_font, D_SZ), load_font(sel_font, N_SZ), load_font(sel_font, L_SZ)
            
            # 이미지 캔버스 생성 (9:16 비율)
            img = ImageOps.exif_transpose(Image.open(bg_file))
            canvas = ImageOps.fit(img.convert("RGBA"), (1080, 1920))
            overlay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            if show_box:
                # 박스 그리기
                draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0, 0, 0, box_alpha))
                
                # 데이터 라벨링 (요청하신 km, bpm 소문자 적용)
                items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
                
                if box_orient == "Horizontal":
                    # 활동명 (90)
                    tw = draw.textlength(v_act, font=f_t)
                    draw.text((rx + (rw//2) - (tw//2), ry + 30), v_act, font=f_t, fill=m_color)
                    # 날짜 (30)
                    dw = draw.textlength(v_date, font=f_d)
                    draw.text((rx + (rw//2) - (dw//2), ry + 30 + T_SZ + 5), v_date, font=f_d, fill="#AAAAAA")
                    
                    # 하단 데이터 (60)
                    sec_w = (rw - 80) // 4
                    for i, (lab, val) in enumerate(items):
                        ix = rx + 40 + (i * sec_w)
                        draw.text((ix, ry + T_SZ + D_SZ + 60), lab, font=f_l, fill="#AAAAAA")
                        draw.text((ix, ry + T_SZ + D_SZ + 60 + L_SZ + 5), val, font=f_n, fill=sub_color)
                else:
                    # 세로 모드 레이아웃
                    draw.text((rx + 40, ry + 40), v_act, font=f_t, fill=m_color)
                    draw.text((rx + 40, ry + 40 + T_SZ + 10), v_date, font=f_d, fill="#AAAAAA")
                    curr_y = ry + T_SZ + D_SZ + 100
                    for lab, val in items:
                        draw.text((rx + 40, curr_y), lab, font=f_l, fill="#AAAAAA")
                        draw.text((rx + 40, curr_y + L_SZ + 5), val, font=f_n, fill=sub_color)
                        curr_y += (N_SZ + L_SZ + 35)

            # 로고 합성
            if log_file:
                l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (100, 100))
                mask = Image.new('L', (100, 100), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 100, 100), fill=255)
                l_img.putalpha(mask)
                overlay.paste(l_img, (rx + rw - 130, ry + 30), l_img)

            # 최종 결과물 표시
            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, use_container_width=True)
            
            # 다운로드 버튼
            buf = io.BytesIO()
            final.save(buf, format="JPEG", quality=95)
            st.download_button("📸 사진 저장하기", buf.getvalue(), "workout_result.jpg", use_container_width=True)
            
        except Exception as e:
            st.error(f"렌더링 에러: {e}")
    else:
        st.info("왼쪽에서 배경 사진을 업로드하면 이곳에 결과가 나타납니다.")
