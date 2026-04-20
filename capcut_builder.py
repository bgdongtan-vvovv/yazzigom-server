#!/usr/bin/env python3
"""
CapCut draft_content.json 빌더
- 이미지 N장 + TTS 오디오 N개 + 자막 트랙을 조립
- macOS CapCut 데스크탑 프로젝트 폴더에 직접 주입 가능

⚠️ 주의: CapCut은 공식 JSON import API를 제공하지 않음.
이 모듈은 역공학된 draft_content.json 구조를 기반으로 함.
CapCut 버전에 따라 인식 실패할 수 있으며, 복잡한 이펙트는 지원하지 않음.

검증된 CapCut 데스크탑 범위: macOS 4.x ~ 5.x (2025~2026 기준)
"""

import json
import uuid
import shutil
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from mutagen.mp3 import MP3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


# ── 상수 (마이크로초 단위) ─────────────────────────────
MICRO = 1_000_000  # 1초 = 1,000,000 마이크로초

# CapCut 쇼츠 포맷 (9:16)
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_FPS = 30


def _new_id() -> str:
    """CapCut이 쓰는 UUID (대문자 하이픈 포함)"""
    return str(uuid.uuid4()).upper()


def _get_image_size(path: Path) -> tuple[int, int]:
    if HAS_PIL:
        try:
            with Image.open(path) as img:
                return img.size  # (width, height)
        except Exception:
            pass
    # fallback
    return (DEFAULT_WIDTH, DEFAULT_HEIGHT)


def _get_audio_duration_us(path: Path) -> int:
    """MP3 길이를 마이크로초로 반환"""
    if HAS_MUTAGEN:
        try:
            audio = MP3(str(path))
            return int(audio.info.length * MICRO)
        except Exception:
            pass
    return 3 * MICRO  # fallback: 3초


# ── 재료(materials) 빌더 ──────────────────────────────

def _build_photo_material(image_path: Path) -> dict:
    """이미지 재료 블록"""
    w, h = _get_image_size(image_path)
    return {
        "id": _new_id(),
        "type": "photo",
        "path": str(image_path.absolute()),
        "file_Path": str(image_path.absolute()),
        "material_name": image_path.name,
        "width": w,
        "height": h,
        "duration": 10_800_000_000,  # 이미지의 가상 길이 (3시간, 충분히 크게)
        "create_time": 0,
        "crop": {
            "lower_left_x": 0.0, "lower_left_y": 1.0,
            "lower_right_x": 1.0, "lower_right_y": 1.0,
            "upper_left_x": 0.0, "upper_left_y": 0.0,
            "upper_right_x": 1.0, "upper_right_y": 0.0,
        },
        "crop_ratio": "free",
        "crop_scale": 1.0,
        "category_id": "",
        "category_name": "local",
        "check_flag": 63,
        "formula_id": "",
        "has_audio": False,
        "intensifies_audio_path": "",
        "intensifies_path": "",
        "local_id": "",
        "local_material_id": "",
        "reverse_intensifies_path": "",
        "reverse_path": "",
        "source": 0,
        "source_platform": 0,
        "stable": {"matrix_path": "", "stable_level": 0, "time_range": {"duration": 0, "start": 0}},
        "team_id": "",
        "video_algorithm": {
            "algorithms": [], "deflicker": None, "motion_blur_config": None,
            "noise_reduction": None, "path": "", "quality_enhance": None,
            "time_range": None,
        },
    }


def _build_audio_material(audio_path: Path, duration_us: int) -> dict:
    """오디오 재료 블록"""
    return {
        "id": _new_id(),
        "type": "extract_music",
        "path": str(audio_path.absolute()),
        "file_Path": str(audio_path.absolute()),
        "name": audio_path.stem,
        "music_id": _new_id(),
        "duration": duration_us,
        "category_id": "",
        "category_name": "local",
        "check_flag": 1,
        "source_platform": 0,
        "text_id": "",
        "tone_category_id": "",
        "tone_category_name": "",
        "tone_effect_id": "",
        "tone_effect_name": "",
        "tone_platform": "",
        "tone_speaker": "",
        "tone_type": "",
        "wave_points": [],
        "intensifies_path": "",
        "local_material_id": "",
        "app_id": 0,
        "app_cmd_id": "",
        "copyright_limit_type": "none",
        "effect_id": "",
        "formula_id": "",
        "is_ai_clone_tone": False,
        "is_text_edit_overdub": False,
        "is_ugc": False,
        "resource_id": "",
        "search_id": "",
        "team_id": "",
    }


def _build_text_material(content: str) -> dict:
    """자막 텍스트 재료 블록"""
    # CapCut은 자막 스타일을 content 안에 직접 JSON으로 박음
    content_json = json.dumps({
        "text": content,
        "styles": [{
            "fill": {
                "content": {"solid": {"color": [1.0, 1.0, 1.0]}},
                "alpha": 1.0,
            },
            "font": {"path": "", "id": ""},
            "size": 15.0,
            "bold": True,
            "italic": False,
            "range": [0, len(content)],
            "strokes": [{
                "content": {"solid": {"color": [0.0, 0.0, 0.0]}},
                "width": 0.08,
                "alpha": 1.0,
            }],
        }],
    }, ensure_ascii=False)
    
    return {
        "id": _new_id(),
        "type": "text",
        "content": content_json,
        "text_size": 15,
        "text_color": "#FFFFFF",
        "font_id": "",
        "font_path": "",
        "font_name": "",
        "font_resource_id": "",
        "font_size": 15.0,
        "font_source_platform": 0,
        "font_team_id": "",
        "font_title": "none",
        "font_url": "",
        "alignment": 1,  # 중앙 정렬
        "background_alpha": 1.0,
        "background_color": "",
        "background_color_alpha": 1.0,
        "background_height": 0.14,
        "background_horizontal_offset": 0.0,
        "background_round_radius": 0.0,
        "background_style": 0,
        "background_vertical_offset": 0.0,
        "background_width": 0.14,
        "base_content": "",
        "bold_width": 0.0,
        "border_alpha": 1.0,
        "border_color": "",
        "border_width": 0.08,
        "caption_template_info": {
            "category_id": "", "category_name": "", "effect_id": "",
            "is_new": False, "path": "", "request_id": "",
            "resource_id": "", "resource_name": "", "source_platform": 0,
        },
        "check_flag": 7,
        "combo_info": {"text_templates": []},
        "fixed_height": -1.0,
        "fixed_width": -1.0,
        "force_apply_line_max_number": False,
        "global_alpha": 1.0,
        "group_id": "",
        "has_shadow": False,
        "initial_scale": 1.0,
        "inner_padding": -1.0,
        "is_rich_text": False,
        "italic_degree": 0,
        "ktv_color": "",
        "language": "",
        "layer_weight": 1,
        "letter_spacing": 0.0,
        "line_feed": 1,
        "line_max_width": 0.82,
        "line_spacing": 0.02,
        "preset_category": "",
        "preset_category_id": "",
        "preset_has_set_alignment": False,
        "preset_id": "",
        "preset_index": 0,
        "preset_name": "",
        "recognize_task_id": "",
        "recognize_type": 0,
        "relevance_segment": [],
        "shadow_alpha": 0.9,
        "shadow_angle": -45.0,
        "shadow_color": "",
        "shadow_distance": 8.0,
        "shadow_point": {"x": 1.0182337649086284, "y": -1.0182337649086284},
        "shadow_smoothing": 0.45,
        "shape_clip_x": False,
        "shape_clip_y": False,
        "source_from": "",
        "style_name": "",
        "sub_type": 0,
        "subtitle_keywords": None,
        "subtitle_template_original_fontsize": 0.0,
        "text_alpha": 1.0,
        "text_curve": None,
        "text_preset_resource_id": "",
        "text_to_audio_ids": [],
        "tts_auto_update": False,
        "typesetting": 0,
        "underline": False,
        "underline_offset": 0.22,
        "underline_width": 0.05,
        "use_effect_default_color": True,
        "words": {"end_time": [], "start_time": [], "text": []},
    }


# ── 세그먼트(segments) 빌더 ────────────────────────────

def _build_video_segment(
    material_id: str,
    start_us: int,
    duration_us: int,
) -> dict:
    """비디오 트랙 세그먼트 (이미지 한 장)"""
    return {
        "id": _new_id(),
        "material_id": material_id,
        "target_timerange": {"start": start_us, "duration": duration_us},
        "source_timerange": {"start": 0, "duration": duration_us},
        "extra_material_refs": [],
        "clip": {
            "alpha": 1.0,
            "flip": {"horizontal": False, "vertical": False},
            "rotation": 0.0,
            "scale": {"x": 1.0, "y": 1.0},
            "transform": {"x": 0.0, "y": 0.0},
        },
        "enable_adjust": True,
        "enable_color_curves": True,
        "enable_color_wheels": True,
        "enable_lut": True,
        "enable_smart_color_adjust": False,
        "last_nonzero_volume": 1.0,
        "render_index": 0,
        "reverse": False,
        "speed": 1.0,
        "track_attribute": 0,
        "track_render_index": 0,
        "uniform_scale": {"on": True, "value": 1.0},
        "visible": True,
        "volume": 1.0,
        "cartoon": False,
        "common_keyframes": [],
        "enable_adjust_mask": False,
        "group_id": "",
        "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
        "intensifies_audio": False,
        "is_placeholder": False,
        "is_tone_modify": False,
        "keyframe_refs": [],
        "responsive_layout": {
            "enable": False, "horizontal_pos_layout": 0,
            "size_layout": 0, "target_follow": "", "vertical_pos_layout": 0,
        },
        "template_id": "",
        "template_scene": "default",
    }


def _build_audio_segment(
    material_id: str,
    start_us: int,
    duration_us: int,
) -> dict:
    """오디오 트랙 세그먼트"""
    return {
        "id": _new_id(),
        "material_id": material_id,
        "target_timerange": {"start": start_us, "duration": duration_us},
        "source_timerange": {"start": 0, "duration": duration_us},
        "extra_material_refs": [],
        "clip": None,
        "enable_adjust": False,
        "enable_color_curves": True,
        "enable_color_wheels": True,
        "enable_lut": False,
        "enable_smart_color_adjust": False,
        "last_nonzero_volume": 1.0,
        "render_index": 0,
        "reverse": False,
        "speed": 1.0,
        "track_attribute": 0,
        "track_render_index": 0,
        "uniform_scale": None,
        "visible": True,
        "volume": 1.0,
        "cartoon": False,
        "common_keyframes": [],
        "enable_adjust_mask": False,
        "group_id": "",
        "intensifies_audio": False,
        "is_placeholder": False,
        "is_tone_modify": False,
        "keyframe_refs": [],
        "responsive_layout": {
            "enable": False, "horizontal_pos_layout": 0,
            "size_layout": 0, "target_follow": "", "vertical_pos_layout": 0,
        },
        "template_id": "",
        "template_scene": "default",
    }


def _build_text_segment(
    material_id: str,
    start_us: int,
    duration_us: int,
) -> dict:
    """자막 트랙 세그먼트"""
    return {
        "id": _new_id(),
        "material_id": material_id,
        "target_timerange": {"start": start_us, "duration": duration_us},
        "source_timerange": None,
        "extra_material_refs": [],
        "clip": {
            "alpha": 1.0,
            "flip": {"horizontal": False, "vertical": False},
            "rotation": 0.0,
            "scale": {"x": 1.0, "y": 1.0},
            "transform": {"x": 0.0, "y": -0.78},  # 화면 하단
        },
        "enable_adjust": False,
        "enable_color_curves": True,
        "enable_color_wheels": True,
        "enable_lut": False,
        "enable_smart_color_adjust": False,
        "last_nonzero_volume": 1.0,
        "render_index": 14000,
        "reverse": False,
        "speed": 1.0,
        "track_attribute": 0,
        "track_render_index": 1,
        "uniform_scale": {"on": True, "value": 1.0},
        "visible": True,
        "volume": 1.0,
        "cartoon": False,
        "common_keyframes": [],
        "enable_adjust_mask": False,
        "group_id": "",
        "intensifies_audio": False,
        "is_placeholder": False,
        "is_tone_modify": False,
        "keyframe_refs": [],
        "responsive_layout": {
            "enable": False, "horizontal_pos_layout": 0,
            "size_layout": 0, "target_follow": "", "vertical_pos_layout": 0,
        },
        "template_id": "",
        "template_scene": "default",
    }


# ── 메인 빌더 ─────────────────────────────────────────

def build_draft_content(
    scenes: list[dict],
    project_name: str = "야찌곰_자동편집",
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: int = DEFAULT_FPS,
    add_subtitles: bool = True,
) -> dict:
    """
    CapCut draft_content.json 전체 구조 생성.
    
    Args:
        scenes: [
            {
                "scene": 1,
                "image_path": "/abs/path/to/scene_01.png",
                "audio_path": "/abs/path/to/scene_01.mp3",
                "duration_sec": 3.45,  # TTS 길이
                "narration": "...",    # 자막용
            },
            ...
        ]
    
    Returns:
        dict (draft_content.json 스키마)
    """
    # 재료 생성
    photo_materials = []
    audio_materials = []
    text_materials = []
    
    # 세그먼트 생성
    video_segments = []
    audio_segments = []
    text_segments = []
    
    current_us = 0
    
    for s in scenes:
        img_path = Path(s["image_path"])
        aud_path = Path(s["audio_path"])
        
        # 오디오 길이가 곧 장면 길이
        if "duration_sec" in s:
            dur_us = int(s["duration_sec"] * MICRO)
        else:
            dur_us = _get_audio_duration_us(aud_path)
        
        # 이미지 재료 + 세그먼트
        pm = _build_photo_material(img_path)
        photo_materials.append(pm)
        video_segments.append(
            _build_video_segment(pm["id"], current_us, dur_us)
        )
        
        # 오디오 재료 + 세그먼트
        am = _build_audio_material(aud_path, dur_us)
        audio_materials.append(am)
        audio_segments.append(
            _build_audio_segment(am["id"], current_us, dur_us)
        )
        
        # 자막
        if add_subtitles and s.get("narration"):
            tm = _build_text_material(s["narration"])
            text_materials.append(tm)
            text_segments.append(
                _build_text_segment(tm["id"], current_us, dur_us)
            )
        
        current_us += dur_us
    
    total_duration = current_us
    
    # 트랙 구성
    tracks = [
        {
            "id": _new_id(),
            "type": "video",
            "attribute": 0,
            "flag": 0,
            "is_default_name": True,
            "name": "",
            "segments": video_segments,
        },
        {
            "id": _new_id(),
            "type": "audio",
            "attribute": 0,
            "flag": 0,
            "is_default_name": True,
            "name": "",
            "segments": audio_segments,
        },
    ]
    
    if add_subtitles and text_segments:
        tracks.append({
            "id": _new_id(),
            "type": "text",
            "attribute": 0,
            "flag": 0,
            "is_default_name": True,
            "name": "",
            "segments": text_segments,
        })
    
    # draft_content.json 루트
    draft = {
        "id": _new_id(),
        "name": project_name,
        "version": 360000,  # CapCut 4.x 기준 버전 코드
        "new_version": "110.0.0",
        "platform": {
            "app_id": 359289,
            "app_source": "cc",
            "app_version": "5.3.0",
            "device_id": _new_id().lower().replace("-", "")[:32],
            "hard_disk_id": _new_id().lower().replace("-", "")[:32],
            "mac_address": _new_id().lower().replace("-", "")[:32],
            "os": "mac",
            "os_version": "14.0.0",
        },
        "canvas_config": {
            "height": height,
            "width": width,
            "ratio": "9:16" if height > width else "16:9",
        },
        "config": {
            "adjust_max_index": 1,
            "attachment_info": [],
            "combination_max_index": 1,
            "export_range": None,
            "extract_audio_last_index": 1,
            "lyrics_recognition_id": "",
            "lyrics_sync": True,
            "lyrics_taskinfo": [],
            "maintrack_adsorb": True,
            "material_save_mode": 0,
            "multi_language_current": "none",
            "multi_language_list": [],
            "multi_language_main": "none",
            "multi_language_mode": "none",
            "original_sound_last_index": 1,
            "record_audio_last_index": 1,
            "sticker_max_index": 1,
            "subtitle_keywords_config": None,
            "subtitle_recognition_id": "",
            "subtitle_sync": True,
            "subtitle_taskinfo": [],
            "system_font_list": [],
            "video_mute": False,
            "zoom_info_params": None,
        },
        "cover": None,
        "create_time": 0,
        "duration": total_duration,
        "extra_info": None,
        "fps": float(fps),
        "free_render_index_mode_on": False,
        "group_container": None,
        "keyframe_graph_list": [],
        "keyframes": {
            "adjusts": [], "audios": [], "effects": [], "filters": [],
            "handwrites": [], "stickers": [], "texts": [], "videos": [],
        },
        "last_modified_platform": {
            "app_id": 359289, "app_source": "cc", "app_version": "5.3.0",
            "device_id": "", "hard_disk_id": "", "mac_address": "",
            "os": "mac", "os_version": "14.0.0",
        },
        "materials": {
            "ai_translates": [],
            "audio_balances": [],
            "audio_effects": [],
            "audio_fades": [],
            "audio_track_indexes": [],
            "audios": audio_materials,
            "beats": [],
            "canvases": [],
            "chromas": [],
            "color_curves": [],
            "digital_humans": [],
            "drafts": [],
            "effects": [],
            "flowers": [],
            "green_screens": [],
            "handwrites": [],
            "hsl": [],
            "images": [],
            "log_color_wheels": [],
            "loudnesses": [],
            "manual_deformations": [],
            "masks": [],
            "material_animations": [],
            "material_colors": [],
            "multi_language_refs": [],
            "placeholders": [],
            "plugin_effects": [],
            "primary_color_wheels": [],
            "realtime_denoises": [],
            "shapes": [],
            "smart_crops": [],
            "smart_relights": [],
            "sound_channel_mappings": [],
            "speeds": [],
            "stickers": [],
            "tail_leaders": [],
            "text_templates": [],
            "texts": text_materials,
            "time_marks": [],
            "transitions": [],
            "video_effects": [],
            "video_trackings": [],
            "videos": photo_materials,  # ← 이미지도 videos에 들어감 (CapCut 구조)
            "vocal_beautifys": [],
            "vocal_separations": [],
        },
        "mutable_config": None,
        "relationships": [],
        "render_index_track_mode_on": False,
        "retouch_cover": None,
        "source": "default",
        "static_cover_image_path": "",
        "time_marks": None,
        "tracks": tracks,
        "update_time": 0,
    }
    
    return draft


def build_draft_meta(project_name: str, total_duration_us: int) -> dict:
    """
    draft_meta_info.json (프로젝트 목록에서 썸네일/이름 띄우는 메타)
    """
    pid = _new_id()
    return {
        "cloud_package_completed_time": "",
        "draft_cloud_capcut_purchase_info": "",
        "draft_cloud_last_action_download": False,
        "draft_cloud_materials": [],
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": "draft_cover.jpg",
        "draft_deeplink_url": "",
        "draft_enterprise_info": {
            "draft_enterprise_extra": "",
            "draft_enterprise_id": "",
            "draft_enterprise_name": "",
            "enterprise_material": [],
        },
        "draft_fold_path": "",
        "draft_id": pid,
        "draft_is_ai_packaging_used": False,
        "draft_is_ai_shorts": False,
        "draft_is_ai_translate": False,
        "draft_is_article_video_draft": False,
        "draft_is_from_deeplink": "false",
        "draft_is_invisible": False,
        "draft_materials": [
            {"type": 0, "value": []},
            {"type": 1, "value": []},
            {"type": 2, "value": []},
            {"type": 3, "value": []},
            {"type": 6, "value": []},
            {"type": 7, "value": []},
            {"type": 8, "value": []},
        ],
        "draft_materials_copied_info": [],
        "draft_name": project_name,
        "draft_new_version": "",
        "draft_removable_storage_device": "",
        "draft_root_path": "",
        "draft_segment_extra_info": [],
        "draft_timeline_materials_size_": 0,
        "draft_type": "",
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_modified": 0,
        "tm_draft_create": 0,
        "tm_draft_modified": 0,
        "tm_draft_removed": 0,
        "tm_duration": total_duration_us,
    }


# ── CapCut 프로젝트 폴더 주입 ─────────────────────────

def get_capcut_projects_dir() -> Optional[Path]:
    """
    CapCut 데스크탑 프로젝트 폴더 경로 반환.
    macOS: ~/Movies/CapCut/User Data/Projects/com.lveditor.draft/
    Windows: %USERPROFILE%\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft\\
    """
    import platform
    system = platform.system()
    home = Path.home()
    
    if system == "Darwin":  # macOS
        p = home / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
        if p.exists():
            return p
    elif system == "Windows":
        p = home / "AppData/Local/CapCut/User Data/Projects/com.lveditor.draft"
        if p.exists():
            return p
    
    return None


def inject_project(
    scenes: list[dict],
    project_name: str,
    copy_media: bool = True,
    capcut_dir: Optional[Path] = None,
) -> dict:
    """
    CapCut 프로젝트 폴더에 프로젝트 주입.
    
    Args:
        scenes: build_draft_content()에 넘기는 것과 동일
        project_name: 새 프로젝트 이름 (CapCut에서 보일 이름)
        copy_media: True면 이미지/음성을 프로젝트 폴더 내부로 복사
                    (권장: 경로 깨짐 방지)
        capcut_dir: 수동 지정 가능, None이면 자동 탐지
    
    Returns:
        {"ok": True, "project_path": "...", "total_duration_sec": 40.5}
        또는 {"ok": False, "error": "..."}
    """
    cc_dir = capcut_dir or get_capcut_projects_dir()
    if cc_dir is None:
        return {
            "ok": False,
            "error": "CapCut 프로젝트 폴더를 찾지 못했어요. "
                     "macOS는 ~/Movies/CapCut/..., Windows는 AppData에 있어야 해요. "
                     "CapCut 데스크탑을 한 번 실행해서 초기화해주세요.",
        }
    
    # 프로젝트 폴더 생성
    safe_name = "".join(
        c if c.isalnum() or c in "가-힣_-" else "_"
        for c in project_name
    )[:60]
    project_dir = cc_dir / safe_name
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # 미디어 파일을 프로젝트 내부로 복사 (경로 안정성)
    mutated_scenes = []
    if copy_media:
        media_dir = project_dir / "media"
        media_dir.mkdir(exist_ok=True)
        
        for s in scenes:
            new_s = dict(s)
            
            img_src = Path(s["image_path"])
            if img_src.exists():
                img_dst = media_dir / img_src.name
                shutil.copy2(img_src, img_dst)
                new_s["image_path"] = str(img_dst.absolute())
            
            aud_src = Path(s["audio_path"])
            if aud_src.exists():
                aud_dst = media_dir / aud_src.name
                shutil.copy2(aud_src, aud_dst)
                new_s["audio_path"] = str(aud_dst.absolute())
            
            mutated_scenes.append(new_s)
    else:
        mutated_scenes = scenes
    
    # JSON 두 개 생성
    draft_content = build_draft_content(mutated_scenes, project_name=project_name)
    draft_meta = build_draft_meta(project_name, draft_content["duration"])
    
    # 파일 쓰기
    content_path = project_dir / "draft_content.json"
    meta_path = project_dir / "draft_meta_info.json"
    
    content_path.write_text(
        json.dumps(draft_content, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    meta_path.write_text(
        json.dumps(draft_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    
    return {
        "ok": True,
        "project_path": str(project_dir),
        "content_json": str(content_path),
        "meta_json": str(meta_path),
        "total_duration_sec": draft_content["duration"] / MICRO,
        "scenes_count": len(mutated_scenes),
        "note": "CapCut을 재실행하면 프로젝트 목록에 나타나요. "
                "만약 안 뜨면 CapCut 종료 → 재실행 필요.",
    }


def export_as_zip(
    scenes: list[dict],
    project_name: str,
    output_zip: Path,
) -> dict:
    """
    CapCut 프로젝트 폴더에 주입하지 않고, ZIP으로 패키징.
    나중에 수동으로 압축 해제해서 쓰거나, Windows에서 주입할 때 사용.
    """
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fake_capcut = tmp_path / "capcut_draft"
        fake_capcut.mkdir()
        
        result = inject_project(
            scenes=scenes,
            project_name=project_name,
            copy_media=True,
            capcut_dir=fake_capcut,
        )
        
        if not result.get("ok"):
            return result
        
        # ZIP 생성
        shutil.make_archive(
            str(output_zip.with_suffix("")),
            "zip",
            root_dir=fake_capcut,
        )
    
    return {
        "ok": True,
        "zip_path": str(output_zip),
        "scenes_count": result["scenes_count"],
        "total_duration_sec": result["total_duration_sec"],
    }


if __name__ == "__main__":
    # 간단 테스트
    test_scenes = [
        {
            "scene": 1,
            "image_path": "/tmp/test1.png",
            "audio_path": "/tmp/test1.mp3",
            "duration_sec": 3.5,
            "narration": "첫 번째 장면입니다",
        },
    ]
    # draft = build_draft_content(test_scenes)
    # print(json.dumps(draft, ensure_ascii=False, indent=2)[:1000])
    print("capcut_builder 모듈 로드 완료")
    print(f"CapCut 경로: {get_capcut_projects_dir()}")
