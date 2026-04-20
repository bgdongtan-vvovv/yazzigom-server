#!/usr/bin/env python3
"""
야찌곰 LoRA 적용 이미지 자동 생성기
사용법: python3 generate_images_lora.py 야지곰_현대차_인도_쇼츠.md
"""

import os
import re
import sys
import time
import urllib.request

import fal_client

# ── 야찌곰 LoRA URL (학습 완료된 모델) ──────────────────────────
LORA_URL = "https://v3b.fal.media/files/b/0a967354/026xTQy_0glfwRTC-dRJ7_pytorch_lora_weights.safetensors"
TRIGGER_WORD = "YAZZIGOM"


def extract_image_prompts(md_path: str) -> list[dict]:
    """md 파일에서 이미지 생성 명령어 섹션만 추출"""
    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"## 이미지 생성 명령어(.+?)(?=## 영상 생성|$)", content, re.DOTALL)
    if not match:
        print("❌ '이미지 생성 명령어' 섹션을 찾을 수 없어요.")
        sys.exit(1)

    section = match.group(1)
    scenes = re.split(r"### 장면 \d+", section)
    scenes = [s.strip() for s in scenes if s.strip()]

    prompts = []
    for i, scene in enumerate(scenes, 1):
        lines = scene.split("\n")
        prompt_lines = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("**대본:**") or line == "---":
                continue
            prompt_lines.append(line)
        prompt = " ".join(prompt_lines).strip()
        if prompt:
            # 트리거 단어를 프롬프트 앞에 추가
            full_prompt = f"{TRIGGER_WORD} {prompt}"
            prompts.append({"scene": i, "prompt": full_prompt})

    return prompts


def generate_image(prompt: str, scene_num: int, output_dir: str) -> str:
    """LoRA 적용 이미지 생성"""
    print(f"  🎨 장면 {scene_num} 생성 중...")

    result = fal_client.subscribe(
        "fal-ai/flux-lora",
        arguments={
            "prompt": prompt,
            "loras": [
                {
                    "path": LORA_URL,
                    "scale": 1.0,   # LoRA 강도 (0.8~1.2 권장)
                }
            ],
            "image_size": "portrait_16_9",
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "num_images": 1,
            "enable_safety_checker": True,
        },
    )

    image_url = result["images"][0]["url"]
    filename = f"scene_{scene_num:02d}.png"
    filepath = os.path.join(output_dir, filename)
    urllib.request.urlretrieve(image_url, filepath)
    return filepath


def main():
    # API 키 확인
    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        print("❌ FAL_KEY 환경변수가 없어요.")
        print('   export FAL_KEY="your_api_key_here"')
        sys.exit(1)

    # md 파일 경로
    if len(sys.argv) < 2:
        print("사용법: python3 generate_images_lora.py <md파일경로>")
        sys.exit(1)

    md_path = sys.argv[1]
    if not os.path.exists(md_path):
        print(f"❌ 파일을 찾을 수 없어요: {md_path}")
        sys.exit(1)

    # 출력 폴더
    base_name = os.path.splitext(os.path.basename(md_path))[0]
    output_dir = os.path.join(os.path.dirname(md_path), f"{base_name}_lora_images")
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 저장 폴더: {output_dir}")

    # 프롬프트 추출
    prompts = extract_image_prompts(md_path)
    print(f"✅ 장면 {len(prompts)}개 발견\n")

    # 이미지 생성
    saved_files = []
    for item in prompts:
        try:
            filepath = generate_image(item["prompt"], item["scene"], output_dir)
            saved_files.append(filepath)
            print(f"  ✅ 저장: {os.path.basename(filepath)}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  ❌ 장면 {item['scene']} 실패: {e}")

    print(f"\n🎉 완료! {len(saved_files)}/{len(prompts)}개 생성됨")
    print(f"📂 {output_dir}")


if __name__ == "__main__":
    main()
