# 야찌곰 v2.10 적용 가이드

v2.02 → v2.10 업데이트 (TTS + CapCut 자동 조립)

## 파일 목록

이 폴더의 파일을 `/Users/davidkingair/Desktop/DavidYoutube`에 복사:

| 파일 | 작업 |
|---|---|
| `tts_module.py` | 새로 추가 |
| `capcut_builder.py` | 새로 추가 |
| `server.py` | **기존 파일 덮어쓰기** (v2.02 기능 모두 포함됨) |
| `requirements.txt` | **덮어쓰기** (mutagen, Pillow, requests 추가) |
| `index_patch.html` | 기존 `index.html`에 **복사해서 붙여넣기** |

---

## 설치 및 실행

### 1. 의존성 설치
```bash
cd /Users/davidkingair/Desktop/DavidYoutube
pip install -r requirements.txt
```

### 2. index.html 패치 적용
기존 `index.html`을 에디터로 열고:
- `index_patch.html`의 **HTML 부분** (`<div class="card" id="tts-card">` ~ 두 번째 카드 끝)을 복사
- 이미지 생성 카드 바로 다음에 붙여넣기
- `<script>` 블록은 기존 `</body>` 직전에 붙여넣기

### 3. 로컬 테스트
```bash
python3 server.py
```
브라우저에서 `http://localhost:8888` 열기.

### 4. 작동 확인 순서
1. 기존 1~4단계로 이미지까지 생성
2. **5단계 TTS**: ElevenLabs 키 입력 → "내 Voice 목록 불러오기" → 중년남성 Voice 선택 → "장면별 TTS 생성"
3. **6단계 CapCut**: 프로젝트 이름 입력 → "CapCut에 직접 주입" 선택 → "CapCut 프로젝트 조립"
4. CapCut 완전 종료 (Cmd+Q) → 재실행 → 프로젝트 목록에서 확인

---

## Railway 배포 주의사항

⚠️ **CapCut 주입 기능은 Railway에서 작동하지 않음**

- Railway는 Linux 컨테이너이므로 macOS의 CapCut 폴더(`~/Movies/CapCut/...`)에 접근 불가
- 대신 **ZIP 다운로드 모드** 사용: `inject=False` 옵션으로 ZIP을 받아서 수동 배치

### Railway 배포 시
- TTS 기능은 그대로 작동 (ElevenLabs API 호출만 함)
- CapCut 기능은 **ZIP 모드만 노출**되도록 UI 조건부 처리 필요
  - `/check-capcut-path`가 `found: false`면 "ZIP 다운로드" 라디오만 표시
  - 이미 위 `index_patch.html`의 `checkCapCutPath()` 함수가 이 분기를 보여줌

### Railway 환경변수 추가
선택적으로 API 키를 서버에 박아둘 수도 있음 (매번 입력 귀찮을 때):
```
ELEVEN_API_KEY=sk_...
ELEVEN_VOICE_ID=...
```
이 경우 `server.py`의 TTS 엔드포인트에서 `data.get('eleven_key') or os.getenv('ELEVEN_API_KEY')` 방식으로 fallback 처리 가능 (지금 코드엔 미적용, 필요하면 추가).

---

## 트러블슈팅

### ❌ "CapCut 프로젝트 폴더를 찾지 못했어요"
- CapCut을 최소 한 번은 실행해서 초기 폴더 구조를 만들어야 함
- 경로 수동 확인:
  ```bash
  ls ~/Movies/CapCut/User\ Data/Projects/com.lveditor.draft/
  ```

### ❌ CapCut을 재실행해도 프로젝트 목록에 안 나옴
가능성 1: CapCut 버전이 최신이라 JSON 스키마가 바뀜  
가능성 2: 한국어 프로젝트명의 인코딩 문제

**디버깅**:
```bash
# CapCut이 기존에 생성한 draft_content.json 하나 복사해서 비교
cp ~/Movies/CapCut/User\ Data/Projects/com.lveditor.draft/기존프로젝트명/draft_content.json /tmp/reference.json
cp ~/Movies/CapCut/User\ Data/Projects/com.lveditor.draft/야찌곰_XXX/draft_content.json /tmp/ours.json
# 루트 키 비교
python3 -c "import json; r=json.load(open('/tmp/reference.json')); print(sorted(r.keys()))"
python3 -c "import json; o=json.load(open('/tmp/ours.json')); print(sorted(o.keys()))"
```
누락된 키가 있으면 `capcut_builder.py`에 추가 필요.

### ❌ ElevenLabs "quota_exceeded"
- 무료 플랜: 10,000 chars/월
- 한국어 50초 대본 × 20편 ≈ 30,000 chars → 유료 플랜 필요

### ❌ TTS 음성이 이상함 (영어 발음으로 나옴)
- 모델을 `eleven_multilingual_v2`로 변경 (기본값)
- `eleven_monolingual_v1`은 영어 전용

---

## 구조 요약

```
DavidYoutube/
├── server.py              ← v2.10 (엔드포인트 8개 추가)
├── tts_module.py          ← 새로 추가
├── capcut_builder.py      ← 새로 추가
├── index.html             ← UI 패치 적용됨
├── requirements.txt       ← mutagen, Pillow, requests 추가
├── output/
│   ├── 야지곰_xxx_images/     (기존 이미지)
│   ├── 야지곰_xxx_audio/      ← 새로 생김 (TTS MP3들)
│   └── 야지곰_xxx.md          (기존 대본)
└── (Railway 배포 파일들: Procfile, railway.json 그대로)
```

---

## v2.11에서 할 것 (다음 단계 제안)

1. **자막 자동 세분화**: 지금은 장면별 나레이션 전체를 한 번에 자막으로 넣음. 단어/구 단위로 잘라서 오디오 싱크 맞추면 더 자연스러움 (whisper 또는 ElevenLabs의 timestamps API 활용)
2. **BGM 자동 선택**: 톤에 맞는 배경음악 자동 매칭
3. **썸네일 자동 생성**: 제목 + 이미지 합성
4. **YouTube 자동 업로드**: YouTube Data API로 최종 MP4 업로드
