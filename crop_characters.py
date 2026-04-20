#!/usr/bin/env python3
"""
야찌곰 캐릭터 시트 자동 크롭기
그린스크린 배경에서 개별 캐릭터를 잘라내어 저장합니다.

사용법: python3 crop_characters.py
"""

import os
import sys
from pathlib import Path

from PIL import Image
import numpy as np


def find_character_sheets(folder: str) -> list[Path]:
    """폴더에서 캐릭터 시트 이미지 찾기"""
    folder = Path(folder)
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    images = [f for f in folder.iterdir() if f.suffix.lower() in extensions]
    return sorted(images)


def remove_green_screen(img: Image.Image) -> Image.Image:
    """그린스크린 제거 후 투명 배경으로 변환"""
    img = img.convert("RGBA")
    data = np.array(img, dtype=np.float32)

    r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]

    # 그린스크린 감지 (초록이 빨강·파랑보다 충분히 밝은 픽셀)
    green_mask = (g > 80) & (g > r * 1.3) & (g > b * 1.3)

    data[:, :, 3] = np.where(green_mask, 0, 255)
    return Image.fromarray(data.astype(np.uint8), "RGBA")


def find_character_blobs(alpha: np.ndarray, min_area: int = 3000) -> list[tuple]:
    """알파 채널에서 캐릭터 영역(bounding box) 찾기"""
    from PIL import ImageFilter

    # 알파를 PIL 이미지로 변환 후 팽창(dilate)으로 근접 영역 합치기
    alpha_img = Image.fromarray(alpha)
    dilated = alpha_img.filter(ImageFilter.MaxFilter(61))  # 60px 범위 합치기
    dilated_arr = np.array(dilated)

    visited = np.zeros_like(dilated_arr, dtype=bool)
    blobs = []
    h, w = dilated_arr.shape

    def bfs(sy, sx):
        """BFS로 연결된 픽셀 영역 탐색"""
        queue = [(sy, sx)]
        visited[sy, sx] = True
        min_y, max_y, min_x, max_x = sy, sy, sx, sx
        count = 0
        while queue:
            cy, cx = queue.pop()
            count += 1
            min_y, max_y = min(min_y, cy), max(max_y, cy)
            min_x, max_x = min(min_x, cx), max(max_x, cx)
            for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                ny, nx = cy+dy, cx+dx
                if 0 <= ny < h and 0 <= nx < w and not visited[ny,nx] and dilated_arr[ny,nx] > 0:
                    visited[ny, nx] = True
                    queue.append((ny, nx))
        return count, (min_x, min_y, max_x, max_y)

    for y in range(0, h, 4):  # 4픽셀 간격으로 스캔 (속도)
        for x in range(0, w, 4):
            if dilated_arr[y, x] > 0 and not visited[y, x]:
                count, bbox = bfs(y, x)
                area = (bbox[2]-bbox[0]) * (bbox[3]-bbox[1])
                if area >= min_area:
                    blobs.append(bbox)

    return blobs


def crop_and_save(img_rgba: Image.Image, bbox: tuple, output_path: Path, padding: int = 20):
    """캐릭터 영역을 패딩 포함해서 크롭 후 저장"""
    w, h = img_rgba.size
    x1 = max(0, bbox[0] - padding)
    y1 = max(0, bbox[1] - padding)
    x2 = min(w, bbox[2] + padding)
    y2 = min(h, bbox[3] + padding)
    cropped = img_rgba.crop((x1, y1, x2, y2))
    cropped.save(output_path, "PNG")


def process_sheet(image_path: Path, output_dir: Path, sheet_index: int) -> int:
    """시트 하나를 처리해서 개별 캐릭터 저장"""
    print(f"\n📄 처리 중: {image_path.name}")

    img = Image.open(image_path)
    print(f"   크기: {img.size}")

    # 그린스크린 제거
    img_rgba = remove_green_screen(img)
    alpha = np.array(img_rgba)[:, :, 3]

    # 캐릭터 영역 찾기
    blobs = find_character_blobs(alpha)
    print(f"   캐릭터 {len(blobs)}개 발견")

    # 크기순 정렬 (큰 것부터)
    blobs.sort(key=lambda b: (b[2]-b[0]) * (b[3]-b[1]), reverse=True)

    saved = 0
    for i, bbox in enumerate(blobs):
        area = (bbox[2]-bbox[0]) * (bbox[3]-bbox[1])
        if area < 5000:  # 너무 작은 건 노이즈
            continue
        filename = output_dir / f"character_s{sheet_index:02d}_{i+1:02d}.png"
        crop_and_save(img_rgba, bbox, filename)
        print(f"   ✅ 저장: {filename.name} (영역: {bbox})")
        saved += 1

    return saved


def main():
    # DavidYoutube 폴더 기준
    base_dir = Path(__file__).parent

    # 캐릭터 시트 폴더 (현재 폴더에서 찾기)
    sheets = []
    for f in base_dir.iterdir():
        if f.suffix.lower() in {".png", ".jpg", ".jpeg"} and "scene" not in f.name.lower():
            sheets.append(f)

    if not sheets:
        print("❌ 캐릭터 시트 이미지를 찾을 수 없어요.")
        print(f"   현재 폴더: {base_dir}")
        print("   .png/.jpg 파일을 같은 폴더에 넣어주세요.")
        sys.exit(1)

    print(f"🐻 캐릭터 시트 {len(sheets)}개 발견:")
    for s in sheets:
        print(f"   - {s.name}")

    # 출력 폴더 생성
    output_dir = base_dir / "lora_training_images"
    output_dir.mkdir(exist_ok=True)
    print(f"\n📁 저장 폴더: {output_dir}")

    # 각 시트 처리
    total = 0
    for i, sheet in enumerate(sheets, 1):
        total += process_sheet(sheet, output_dir, i)

    print(f"\n🎉 완료! 총 {total}개 캐릭터 이미지 저장됨")
    print(f"📂 {output_dir}")
    print("\n다음 단계: 저장된 이미지 중 품질 좋은 15~20개 선택 후 LoRA 학습")


if __name__ == "__main__":
    main()
