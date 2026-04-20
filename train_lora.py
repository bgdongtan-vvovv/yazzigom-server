#!/usr/bin/env python3
"""
야찌곰 LoRA 학습기
사용법: python3 train_lora.py
"""

import os
import sys
import fal_client


def main():
    # ── API 키 확인 ─────────────────────────────────────────────
    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        print("❌ FAL_KEY 환경변수가 없어요.")
        print('   export FAL_KEY="your_api_key_here"')
        sys.exit(1)

    # ── zip 파일 업로드 ─────────────────────────────────────────
    zip_path = os.path.expanduser(
        "/Users/davidkingair/Desktop/DavidYoutube/yazzigom_lora_v2.zip"
    )

    if not os.path.exists(zip_path):
        print(f"❌ zip 파일을 찾을 수 없어요: {zip_path}")
        sys.exit(1)

    print("📤 학습 이미지 업로드 중...")
    with open(zip_path, "rb") as f:
        data = f.read()
    zip_url = fal_client.upload(data, "application/zip")
    print(f"✅ 업로드 완료: {zip_url}")

    # ── LoRA 학습 시작 ──────────────────────────────────────────
    print("\n🏋️  LoRA 학습 시작... (5~15분 소요)")
    print("   트리거 단어: YAZZIGOM")

    result = fal_client.subscribe(
        "fal-ai/flux-lora-fast-training",
        arguments={
            "images_data_url": zip_url,
            "trigger_word": "YAZZIGOM",          # 나중에 이 단어로 캐릭터 호출
            "steps": 1000,                        # 학습 스텝 (18장 기준 최적)
            "learning_rate": 0.0004,
            "multiresolution_training": True,
            "subject_crop": False,                # 이미 크롭된 이미지라 불필요
        },
        with_logs=True,
        on_queue_update=lambda update: print(f"   ⏳ {update}") 
            if hasattr(update, "logs") else None,
    )

    # ── 결과 저장 ───────────────────────────────────────────────
    lora_url = result.get("diffusers_lora_file", {}).get("url", "")
    config_url = result.get("config_file", {}).get("url", "")

    print("\n🎉 LoRA 학습 완료!")
    print(f"   LoRA URL: {lora_url}")
    print(f"   Config URL: {config_url}")

    # URL을 파일로 저장
    result_path = "/Users/davidkingair/Desktop/DavidYoutube/lora_result.txt"
    with open(result_path, "w") as f:
        f.write(f"lora_url={lora_url}\n")
        f.write(f"config_url={config_url}\n")
        f.write("trigger_word=YAZZIGOM\n")

    print(f"\n📄 URL 저장됨: {result_path}")
    print("\n다음 단계: generate_images.py에 LoRA URL 적용")


if __name__ == "__main__":
    main()
