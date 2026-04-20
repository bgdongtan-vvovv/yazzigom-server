#!/usr/bin/env python3
"""
야찌곰 TTS 모듈 (ElevenLabs)
- 장면별 대본을 MP3로 변환
- 각 MP3의 정확한 길이(초) 반환 → 타임라인 계산용
"""

import os
import re
import requests
from pathlib import Path
from mutagen.mp3 import MP3


ELEVEN_API_BASE = "https://api.elevenlabs.io/v1"

# 한국어 지원 모델 (2026.04 기준)
#  - eleven_multilingual_v2: 안정적, 29개 언어, 한국어 자연스러움 높음
#  - eleven_v3: 감정 표현 풍부 (alpha 단계, API 접근은 가능)
DEFAULT_MODEL = "eleven_multilingual_v2"


def parse_scenes_from_md(md_content: str) -> list[dict]:
    """
    대본 MD에서 장면별 나레이션 추출.
    
    현재 server.py가 만드는 MD 구조:
        ### 장면 1
        **대본:** [해당 장면 대본]
        [이미지 프롬프트]
    
    Returns:
        [{"scene": 1, "narration": "...", "prompt": "..."}, ...]
    """
    sec_match = re.search(
        r'## 이미지 생성 명령어([\s\S]+?)(?=## 영상 생성|$)',
        md_content
    )
    if not sec_match:
        return []
    
    section = sec_match.group(1)
    # 장면 단위로 split
    parts = re.split(r'### 장면 (\d+)', section)
    
    scenes = []
    # parts = ['', '1', '내용1', '2', '내용2', ...]
    for i in range(1, len(parts), 2):
        scene_no = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ""
        
        # **대본:** 뒤의 줄이 나레이션
        narr_match = re.search(r'\*\*대본:\*\*\s*(.+?)(?:\n|$)', body)
        narration = narr_match.group(1).strip() if narr_match else ""
        # [ ... ] 대괄호 안 placeholder 제거
        narration = re.sub(r'\[.*?\]', '', narration).strip()
        
        # 나머지 줄 = 이미지 프롬프트
        prompt_lines = [
            l.strip() for l in body.split('\n')
            if l.strip()
            and not l.strip().startswith('**대본:**')
            and l.strip() != '---'
        ]
        prompt = ' '.join(prompt_lines)
        
        if narration:  # 나레이션 있는 장면만
            scenes.append({
                "scene": scene_no,
                "narration": narration,
                "prompt": prompt,
            })
    
    return scenes


def tts_generate(
    text: str,
    voice_id: str,
    api_key: str,
    output_path: Path,
    model_id: str = DEFAULT_MODEL,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
) -> dict:
    """
    ElevenLabs로 TTS 생성.
    
    Returns:
        {"ok": True, "path": "...", "duration_sec": 3.45, "size": 55000}
        또는 {"ok": False, "error": "..."}
    """
    url = f"{ELEVEN_API_BASE}/text-to-speech/{voice_id}"
    
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    
    body = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": True,
        },
    }
    
    try:
        r = requests.post(url, headers=headers, json=body, timeout=60)
        
        if r.status_code != 200:
            # ElevenLabs 에러는 JSON으로 돌아옴
            try:
                err = r.json()
                return {
                    "ok": False,
                    "error": f"HTTP {r.status_code}: {err.get('detail', err)}",
                }
            except Exception:
                return {
                    "ok": False,
                    "error": f"HTTP {r.status_code}: {r.text[:200]}",
                }
        
        # MP3 저장
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(r.content)
        
        # 정확한 길이 측정 (mutagen)
        try:
            audio = MP3(str(output_path))
            duration = float(audio.info.length)
        except Exception as e:
            return {
                "ok": False,
                "error": f"MP3 길이 측정 실패: {e}",
            }
        
        return {
            "ok": True,
            "path": str(output_path),
            "duration_sec": round(duration, 3),
            "size": len(r.content),
        }
    
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "ElevenLabs API 타임아웃 (60s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tts_generate_batch(
    scenes: list[dict],
    voice_id: str,
    api_key: str,
    output_dir: Path,
    model_id: str = DEFAULT_MODEL,
    on_progress=None,
) -> list[dict]:
    """
    장면 리스트를 일괄 TTS 변환.
    
    Args:
        scenes: parse_scenes_from_md() 결과
        on_progress: callback(scene_no, result) - 진행 로깅용
    
    Returns:
        [{"scene": 1, "narration": "...", "audio_path": "...", 
          "duration_sec": 3.45, "ok": True}, ...]
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    
    for s in scenes:
        out = output_dir / f"scene_{s['scene']:02d}.mp3"
        r = tts_generate(
            text=s["narration"],
            voice_id=voice_id,
            api_key=api_key,
            output_path=out,
            model_id=model_id,
        )
        
        item = {
            "scene": s["scene"],
            "narration": s["narration"],
            **r,
        }
        if r.get("ok"):
            item["audio_path"] = r["path"]
        
        results.append(item)
        if on_progress:
            on_progress(s["scene"], item)
    
    return results


def get_voice_list(api_key: str) -> dict:
    """
    사용자 계정에 등록된 Voice 목록 조회.
    Returns: {"ok": True, "voices": [{"voice_id": "...", "name": "..."}]}
    """
    url = f"{ELEVEN_API_BASE}/voices"
    headers = {"xi-api-key": api_key}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        
        data = r.json()
        voices = [
            {
                "voice_id": v["voice_id"],
                "name": v["name"],
                "category": v.get("category", "unknown"),
                "preview_url": v.get("preview_url", ""),
            }
            for v in data.get("voices", [])
        ]
        return {"ok": True, "voices": voices}
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    # 간단 테스트
    import sys
    
    if len(sys.argv) < 3:
        print("사용법: python tts_module.py <API_KEY> <VOICE_ID>")
        sys.exit(1)
    
    api_key = sys.argv[1]
    voice_id = sys.argv[2]
    
    result = tts_generate(
        text="안녕하세유. 야찌곰이여. 오늘은 뭔 얘기 할까유.",
        voice_id=voice_id,
        api_key=api_key,
        output_path=Path("test_output.mp3"),
    )
    print(result)
