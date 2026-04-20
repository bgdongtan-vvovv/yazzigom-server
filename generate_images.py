#!/usr/bin/env python3
"""
야찌곰 이미지 자동 생성기
사용법: python generate_images.py 야지곰_현대차_인도_쇼츠.md
"""

import os
import re
import sys
import time
import urllib.request

import fal_client


def extract_image_prompts(md_path: str) -> list[dict]:
    """md 파일에서 이미지 생성 명령어 섹션만 추출"""
    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    # '## 이미지 생성 명령어' 섹션만 잘라냄
    match = re.search(r"## 이미지 생성 명령어(.+?)(?=## 영상 생성|$)", content, re.DOTALL)
    if not match:
        print("❌ '이미지 생성 명령어' 섹션을 찾을 수 없어요.")
        sys.exit(1)

    section = match.group(1)

    # 장면별로 분리
    scenes = re.split(r"### 장면 \d+", section)
    scenes = [s.strip() for s in scenes if s.strip()]

    prompts = []
    for i, scene in enumerate(scenes, 1):
        # **대본:** 줄 제거하고 프롬프트만 추출
        lines = scene.split("\n")
        prompt_lines = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("**대본:**") or line == "---":
                continue
            prompt_lines.append(line)
        prompt = " ".join(prompt_lines).strip()
        if prompt:
            prompts.append({"scene": i, "prompt": prompt})

    return prompts


def generate_image(prompt: str, scene_num: int, output_dir: str) -> str:
    """fal.ai nano-banana-2로 이미지 생성 후 저장"""
    print(f"  🎨 장면 {scene_num} 생성 중...")

    result = fal_client.subscribe(
        "fal-ai/nano-banana-2",
        arguments={
            "prompt": prompt,
            "image_size": "portrait_9_16",   # 9:16 세로 포맷 (쇼츠용)
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "num_images": 1,
            "enable_safety_checker": True,
        },
    )

    # 이미지 URL 추출
    image_url = result["images"][0]["url"]

    # 파일 저장
    filename = f"scene_{scene_num:02d}.png"
    filepath = os.path.join(output_dir, filename)
    urllib.request.urlretrieve(image_url, filepath)

    return filepath


def main():
    # ── 1. API 키 설정 ──────────────────────────────────────────
    # 터미널에서 실행 전에 아래 명령어로 키를 환경변수에 등록하세요:
    #   export FAL_KEY="여기에_새_API_키_입력"
    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        print("❌ FAL_KEY 환경변수가 없어요.")
        print("   터미널에서 먼저 실행하세요:")
        print('   export FAL_KEY="your_api_key_here"')
        sys.exit(1)

    os.environ["FAL_KEY"] = api_key

    # ── 2. md 파일 경로 ─────────────────────────────────────────
    if len(sys.argv) < 2:
        print("사용법: python generate_images.py <md파일경로>")
        print("예시:   python generate_images.py 야지곰_현대차_인도_쇼츠.md")
        sys.exit(1)

    md_path = sys.argv[1]
    if not os.path.exists(md_path):
        print(f"❌ 파일을 찾을 수 없어요: {md_path}")
        sys.exit(1)

    # ── 3. 출력 폴더 생성 ───────────────────────────────────────
    base_name = os.path.splitext(os.path.basename(md_path))[0]
    output_dir = os.path.join(os.path.dirname(md_path), f"{base_name}_images")
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 저장 폴더: {output_dir}")

    # ── 4. 프롬프트 추출 ────────────────────────────────────────
    prompts = extract_image_prompts(md_path)
    print(f"✅ 장면 {len(prompts)}개 발견\n")

    # ── 5. 이미지 생성 ──────────────────────────────────────────
    saved_files = []
    for item in prompts:
        try:
            filepath = generate_image(item["prompt"], item["scene"], output_dir)
            saved_files.append(filepath)
            print(f"  ✅ 저장: {os.path.basename(filepath)}")
            time.sleep(0.5)  # API 레이트 리밋 방지
        except Exception as e:
            print(f"  ❌ 장면 {item['scene']} 실패: {e}")

    # ── 6. 완료 ─────────────────────────────────────────────────
    print(f"\n🎉 완료! {len(saved_files)}/{len(prompts)}개 생성됨")
    print(f"📂 {output_dir}")


if __name__ == "__main__":
    main()
