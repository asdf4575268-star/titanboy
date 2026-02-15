# --- [6. 미리보기 렌더링 (메인 화면 하단)] ---
with col_main:
    st.subheader("🖼️ PREVIEW")
    
    # 배경 사진 유무와 관계없이 데이터만 있으면 즉시 렌더링
    data_ready = (mode == "DAILY" and a) or (mode == "WEEKLY" and weekly_data) or (mode == "MONTHLY" and monthly_data)
    
    if data_ready:
        try:
            CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
            
            # [사용자 지정 크기 고정] 활동명: 70, 날짜: 20, 숫자: 45, 유닛: 23
            f_t = load_font(sel_font, 70)  # 활동명
            f_d = load_font(sel_font, 20)  # 날짜
            f_n = load_font(sel_font, 45)  # 숫자
            f_l = load_font(sel_font, 23)  # 유닛(라벨)
            
            # 그래프용 폰트 경로 (크기 70 기준)
            f_path = f"font_{sel_font}_70.ttf"
            
            # 사진이 없으면 기본 검은색 배경 사용
            canvas = make_smart_collage(bg_files, (CW, CH)) if bg_files else Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
            overlay = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # [데이터 및 단위 소문자 처리]
            items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]

            if st.checkbox("데이터 박스 보기", value=True):
                if box_orient == "Vertical":
                    draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0, 0, 0, box_alpha))
                    draw_styled_text(draw, (rx + 40, ry + 30), v_act, f_t, m_color, use_shadow)
                    draw_styled_text(draw, (rx + 40, ry + 125), v_date, f_d, "#AAAAAA", use_shadow)
                    y_c = ry + 190
                    for lab, val in items:
                        draw_styled_text(draw, (rx + 40, y_c), lab.lower(), f_l, "#AAAAAA", use_shadow)
                        v_s = val.lower() # km, bpm 소문자 고정
                        draw_styled_text(draw, (rx + 40, y_c + 35), v_s, f_n, sub_color, use_shadow)
                        y_c += 100
                else:
                    draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0, 0, 0, box_alpha))
                    t_x = rx + (rw - draw.textlength(v_act, font=f_t)) // 2
                    draw_styled_text(draw, (t_x, ry + 35), v_act, f_t, m_color, use_shadow)
                    d_x = rx + (rw - draw.textlength(v_date, font=f_d)) // 2
                    draw_styled_text(draw, (d_x, ry + 130), v_date, f_d, "#AAAAAA", use_shadow)
                    
                    sec_w = rw // 4
                    for i, (lab, val) in enumerate(items):
                        cx = rx + (i * sec_w) + (sec_w // 2)
                        v_s = val.lower()
                        draw_styled_text(draw, (cx - draw.textlength(lab.lower(), font=f_l) // 2, ry + 185), lab.lower(), f_l, "#AAAAAA", use_shadow)
                        draw_styled_text(draw, (cx - draw.textlength(v_s, font=f_n) // 2, ry + 230), v_s, f_n, sub_color, use_shadow)

            # [지도 및 그래프 렌더링]
            if st.checkbox("지도/그래프 보기", value=True):
                if mode == "DAILY" and a and a.get('map', {}).get('summary_polyline'):
                    # ... (DAILY 지도 로직 동일)
                    pass
                elif mode in ["WEEKLY", "MONTHLY"] and (weekly_data or monthly_data):
                    d_obj = weekly_data if mode == "WEEKLY" else monthly_data
                    # MONTHLY 오류 해결된 차트 함수 호출
                    chart_img = create_bar_chart(d_obj['dists'], m_color, mode=mode, labels=d_obj.get('labels'), font_path=f_path)
                    vis_sz = vis_sz_adj
                    vis_layer = chart_img.resize((vis_sz, int(chart_img.size[1] * (vis_sz / chart_img.size[0]))), Image.Resampling.LANCZOS)
                    vis_layer.putalpha(vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255)))
                    overlay.paste(vis_layer, ((CW - vis_layer.width) // 2, CH - vis_layer.height - 80), vis_layer)

            final = Image.alpha_composite(canvas, overlay).convert("RGB")
            st.image(final, width=300)
            
            buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
            st.download_button(f"📸 {mode} DOWNLOAD", buf.getvalue(), f"{mode.lower()}.jpg", use_container_width=True)
            
        except Exception as e:
            st.error(f"렌더링 오류: {e}")
    else:
        st.info("데이터를 선택하면 즉시 미리보기가 나타납니다.")
