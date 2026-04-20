#!/usr/bin/env python3
"""
야찌곰 자동화 서버 v2.10
- v2.02 기능 모두 유지
- 추가: TTS (ElevenLabs) + CapCut JSON 자동 조립

실행: python3 server.py
접속: http://localhost:8888
"""

import os, json, re, threading, time, urllib.request
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import anthropic
import fal_client
from youtube_transcript_api import YouTubeTranscriptApi
import feedparser

try:
    from pytrends.request import TrendReq
    PYTRENDS_OK = True
except Exception:
    PYTRENDS_OK = False

# v2.10 추가 모듈
from tts_module import (
    parse_scenes_from_md,
    tts_generate_batch,
    get_voice_list,
    DEFAULT_MODEL as TTS_DEFAULT_MODEL,
)
from capcut_builder import (
    inject_project,
    export_as_zip,
    get_capcut_projects_dir,
)

app = Flask(__name__)
CORS(app)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

state = {
    "status": "idle", "step": 0, "step_name": "", "logs": [],
    "images": [], "md_content": "", "ideas": [], "transcript": "", "topic": "",
    # v2.10 추가
    "audio_files": [],
    "capcut_project_path": "",
}


def log(msg, type="info"):
    state["logs"].append({
        "msg": msg, "type": type, "time": time.strftime("%H:%M:%S")
    })
    print(f"[{type.upper()}] {msg}")


def reset():
    state.update({
        "status": "idle", "step": 0, "step_name": "", "logs": [],
        "images": [], "md_content": "", "ideas": [],
        "transcript": "", "topic": "",
        "audio_files": [], "capcut_project_path": "",
    })


def extract_video_id(url):
    m = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else None


@app.route('/')
def index():
    return send_file('index.html')


@app.route('/state')
def get_state():
    return jsonify(state)


@app.route('/get-transcript', methods=['POST'])
def get_transcript_route():
    urls = request.json.get('urls', [])
    results, combined = [], ""
    for url in urls:
        vid = extract_video_id(url)
        if not vid:
            results.append({"url": url, "ok": False, "error": "URL 오류"})
            continue
        try:
            t = YouTubeTranscriptApi.get_transcript(vid, languages=['ko', 'en'])
            text = ' '.join([x['text'] for x in t])
            combined += f"\n\n[{url}]\n{text}"
            results.append({"url": url, "ok": True, "length": len(text)})
        except Exception as e:
            results.append({"url": url, "ok": False, "error": str(e)})
    state["transcript"] = combined
    return jsonify({"results": results, "total": len(combined)})


# ── 타겟별 관심사 정의 ────────────────────────────────
TARGET_PROFILES = {
    "20대": {
        "label": "20대",
        "keywords": ["취업", "알바", "월세", "부업", "코인", "인스타", "연애", "대출"],
        "rss": [
            "https://rss.donga.com/economy.xml",
            "https://www.khan.co.kr/rss/rssdata/economy_news.xml",
            "https://www.mk.co.kr/rss/40300001/",
            "https://rss.etnews.com/Section901.xml",
        ],
        "google_kw": ["취업 현실 2024", "청년 부업", "20대 재테크", "청년 정책 혜택", "월세 대출"],
        "desc": "취업·부업·월세·코인에 민감한 20대",
        "angle": "취업난, 돈 없는 현실, 정부 혜택 꿀팁, 부업으로 탈출하는 법",
    },
    "30대": {
        "label": "30대",
        "keywords": ["직장", "육아", "내집마련", "이직", "주식", "부동산", "워라밸", "어린이집"],
        "rss": [
            "https://rss.donga.com/economy.xml",
            "https://www.mk.co.kr/rss/30100041/",
            "https://land.naver.com/news/rss.nhn",
            "https://www.khan.co.kr/rss/rssdata/economy_news.xml",
        ],
        "google_kw": ["30대 내집마련", "전세 사기 예방", "이직 연봉 협상", "육아휴직 현실", "주식 투자"],
        "desc": "내집마련·이직·육아 고민하는 30대 직장인",
        "angle": "전세 사기, 내집마련 현실, 이직 시장, 워라밸 vs 연봉",
    },
    "40대": {
        "label": "40대",
        "keywords": ["자녀교육", "입시", "부동산", "건강검진", "노후준비", "중간관리자", "명예퇴직"],
        "rss": [
            "https://rss.donga.com/economy.xml",
            "https://www.mk.co.kr/rss/30100041/",
            "https://health.chosun.com/rss/news.xml",
            "https://edu.chosun.com/rss/news.xml",
        ],
        "google_kw": ["40대 명예퇴직", "자녀 입시 현실", "부동산 세금", "건강보험료", "노후자금"],
        "desc": "자녀교육·노후준비·명예퇴직 걱정하는 40대",
        "angle": "회사에서 밀려나는 현실, 입시 전쟁, 부동산 세금 폭탄, 건강 적신호",
    },
    "50대": {
        "label": "50대",
        "keywords": ["국민연금", "은퇴", "건강", "자녀독립", "재취업", "귀농", "노인복지"],
        "rss": [
            "https://health.chosun.com/rss/news.xml",
            "https://www.mk.co.kr/rss/30000001/",
            "https://rss.donga.com/economy.xml",
            "https://www.hankyung.com/feed/economy",
        ],
        "google_kw": ["국민연금 수령액", "50대 재취업", "노후 건강관리", "은퇴 후 생활비", "귀농 현실"],
        "desc": "연금·건강·은퇴 후 삶 준비하는 50대",
        "angle": "연금 덜 받는 현실, 재취업 벽, 건강보험료 폭탄, 노후자금 얼마나 필요한가",
    },
}


def fetch_google_trends(keywords, geo='KR', max=10):
    if not PYTRENDS_OK:
        return []
    try:
        pt = TrendReq(hl='ko-KR', tz=540, timeout=(10, 25))
        pt.build_payload(keywords[:5], geo=geo, timeframe='now 1-d')
        related = pt.related_queries()
        topics = []
        for kw in keywords[:3]:
            if kw in related and related[kw]['top'] is not None:
                for _, row in related[kw]['top'].head(3).iterrows():
                    topics.append(row['query'])
        return topics[:max]
    except Exception:
        return []


def fetch_rss_headlines(urls, max_per_feed=5):
    headlines = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get('title', '').strip()
                if title and len(title) > 5:
                    headlines.append(title)
        except Exception:
            continue
    return headlines[:15]


@app.route('/get-trends', methods=['POST'])
def get_trends_route():
    data = request.json
    target = data.get('target', '30대')
    profile = TARGET_PROFILES.get(target, TARGET_PROFILES['30대'])
    
    result = {"target": target, "sources": {}}
    result["sources"]["rss"] = fetch_rss_headlines(profile['rss'])
    result["sources"]["google_trends"] = fetch_google_trends(profile['google_kw'])
    return jsonify(result)


@app.route('/get-ideas', methods=['POST'])
def get_ideas():
    data = request.json
    claude_key = data.get('claude_key', '')
    transcript = data.get('transcript', '') or state.get('transcript', '')
    target = data.get('target', '30대')
    use_web = data.get('use_web', True)
    exclude = data.get('exclude', [])
    
    if not claude_key:
        return jsonify({"error": "Claude 키 필요"}), 400
    
    profile = TARGET_PROFILES.get(target, TARGET_PROFILES['30대'])
    
    def run():
        state["status"] = "running"
        state["step"] = 1
        state["step_name"] = "소재 수집 중..."
        log(f"[{target}] 타겟 소재 수집 시작...")
        
        try:
            context_lines = []
            log("RSS 뉴스 수집 중...")
            headlines = fetch_rss_headlines(profile['rss'], max_per_feed=6)
            if headlines:
                context_lines.append("[ 오늘 주요 뉴스 헤드라인 ]")
                context_lines.extend([f"- {h}" for h in headlines])
                log(f"뉴스 {len(headlines)}개 수집", "ok")
            
            if PYTRENDS_OK:
                log("Google Trends 수집 중...")
                trends = fetch_google_trends(profile['google_kw'])
                if trends:
                    context_lines.append("\n[ Google 실시간 트렌드 키워드 ]")
                    context_lines.extend([f"- {t}" for t in trends])
                    log(f"트렌드 {len(trends)}개 수집", "ok")
            
            context = "\n".join(context_lines) if context_lines else "트렌드 데이터 없음"
            exclude_str = "\n".join([f"- {e}" for e in exclude]) if exclude else "없음"
            
            log("Claude로 아이디어 생성 중...")
            client = anthropic.Anthropic(api_key=claude_key)
            system = f"""너는 야찌곰 유튜브 채널 소재 발굴 전문가야.
야찌곰은 충청도 사투리를 쓰는 피곤한 직장인 흰색 곰 캐릭터야.
타겟: {profile['desc']}
핵심 관심사: {', '.join(profile['keywords'])}
이 타겟의 핵심 각도: {profile.get('angle', '뉴스 뒤의 진짜 이야기 폭로')}
뉴스 뒤의 진짜 이야기를 폭로하는 정보성 숏츠 채널이야."""
            
            user_prompt = f"""아래 실시간 뉴스를 참고해서 {target} 타겟에 딱 맞는 야찌곰 숏츠 아이디어 10개를 만들어줘.

{context}

[{target} 타겟 핵심 관심사]
{chr(10).join([f"- {k}" for k in profile['keywords']])}

[이 타겟에 먹히는 각도]
{profile.get('angle', '뉴스 뒤의 진짜 이야기')}

조건:
- 반드시 {target} 의 일상/고민과 직결되는 주제만
- 뉴스 헤드라인을 {target} 시각으로 비틀기 ("나한테 무슨 영향?", "진짜 이유는?")
- 제목은 30자 이내, 클릭하고 싶은 형태
- 다른 연령대 관심사 주제 제외
- 이미 나온 아이디어 제외:
{exclude_str}

제목만 10개 (번호 포함):
1."""
            
            if use_web:
                tools = [{"type": "web_search_20250305", "name": "web_search"}]
                msg = client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=1500,
                    system=system,
                    tools=tools,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                full_text = ""
                tool_use_blocks = [b for b in msg.content if b.type == "tool_use"]
                if tool_use_blocks:
                    tool_results = [
                        {"type": "tool_result", "tool_use_id": b.id, "content": "검색 완료"}
                        for b in tool_use_blocks
                    ]
                    msgs = [
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": msg.content},
                        {"role": "user", "content": tool_results},
                    ]
                    msg2 = client.messages.create(
                        model="claude-sonnet-4-5",
                        max_tokens=1000,
                        system=system,
                        tools=tools,
                        messages=msgs,
                    )
                    for block in msg2.content:
                        if hasattr(block, 'text'):
                            full_text += block.text
                else:
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            full_text += block.text
                text = full_text
            else:
                msg = client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=1000,
                    system=system,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                text = msg.content[0].text
            
            ideas = [
                re.sub(r'^\d+\.\s*', '', l.strip())
                for l in text.strip().split('\n')
                if re.match(r'^\d+\.', l.strip())
            ]
            state["ideas"] = ideas[:10]
            state["status"] = "ideas_ready"
            log(f"{target} 타겟 아이디어 {len(ideas[:10])}개 완료!", "ok")
        
        except Exception as e:
            log(f"오류: {e}", "err")
            state["status"] = "error"
    
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})


@app.route('/generate-script', methods=['POST'])
def generate_script():
    data = request.json
    claude_key = data.get('claude_key', '')
    topic = data.get('topic', '')
    transcript = data.get('transcript', '') or state.get('transcript', '')
    
    if not claude_key or not topic:
        return jsonify({"error": "키/주제 필요"}), 400
    state["topic"] = topic
    
    def run():
        state["status"] = "running"
        state["step"] = 2
        state["step_name"] = "대본 생성 중..."
        log(f"주제: {topic} | 대본 생성 중...")
        
        try:
            client = anthropic.Anthropic(api_key=claude_key)
            system = "너는 야찌곰 유튜브 PD야. 충청도 사투리(~겨,~거든,~인겨), 피곤한 곰 직장인 캐릭터, 뉴스 뒤 진짜 이야기 폭로 톤."
            ref = f"\n\n참고 자막:\n{transcript[:1500]}" if transcript else ""
            user = f"""주제: {topic}{ref}

아래 형식으로 정확히 출력해:

# 야지곰 | {topic}

---

## 주제
{topic}

## 형식
유튜브 쇼츠 (35~45초)

---

## 대본 (단어수)
[충청도 사투리 대본. 35~45초 분량]

---

## 이미지 생성 명령어

### 장면 1

**대본:** [해당 장면 대본]

[A chubby white polar bear cartoon character wearing a black tie, [장면 묘사], 2D sketch style character composited over realistic photo background, vertical 9:16 format / camera angle: [각도] / lighting: [조명] / mood: [분위기] / action: [동작]]

---

### 장면 2

**대본:** [해당 장면 대본]

[프롬프트]

---

### 장면 3

**대본:** [해당 장면 대본]

[프롬프트]

---

### 장면 4

**대본:** [해당 장면 대본]

[프롬프트]

---

### 장면 5

**대본:** [해당 장면 대본]

[프롬프트]

---

### 장면 6

**대본:** [해당 장면 대본]

[프롬프트]"""
            
            msg = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            md = msg.content[0].text
            state["md_content"] = md
            state["status"] = "script_ready"
            log("대본 생성 완료!", "ok")
            
            safe = re.sub(r'[^\w가-힣]', '', topic)[:20]
            (OUTPUT_DIR / f"야지곰_{safe}.md").write_text(md, encoding='utf-8')
            log(f"MD 저장 완료", "ok")
        
        except Exception as e:
            log(f"오류: {e}", "err")
            state["status"] = "error"
    
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})


@app.route('/generate-images', methods=['POST'])
def generate_images():
    data = request.json
    fal_key = data.get('fal_key', '')
    lora_url = data.get('lora_url', '')
    md = data.get('md_content', '') or state.get('md_content', '')
    
    if not fal_key or not md:
        return jsonify({"error": "FAL키/MD 필요"}), 400
    
    def run():
        state["status"] = "running"
        state["step"] = 3
        state["step_name"] = "이미지 생성 중..."
        state["images"] = []
        os.environ["FAL_KEY"] = fal_key
        
        sec = re.search(r'## 이미지 생성 명령어([\s\S]+?)(?=## 영상 생성|$)', md)
        if not sec:
            log("이미지 섹션 없음", "err")
            state["status"] = "error"
            return
        
        scenes = re.split(r'### 장면 \d+', sec.group(1))
        prompts = []
        for i, s in enumerate(scenes, 1):
            if not s.strip():
                continue
            lines = [
                l.strip() for l in s.split('\n')
                if l.strip()
                and not l.startswith('**대본:**')
                and l.strip() != '---'
            ]
            p = 'YAZZIGOM ' + ' '.join(lines)
            if len(p) > 15:
                prompts.append({"scene": i, "prompt": p})
        
        log(f"프롬프트 {len(prompts)}개", "ok")
        safe = re.sub(r'[^\w가-힣]', '', state.get('topic', '영상'))[:20]
        img_dir = OUTPUT_DIR / f"야지곰_{safe}_images"
        img_dir.mkdir(exist_ok=True)
        
        for item in prompts:
            log(f"장면 {item['scene']} 생성 중...")
            try:
                r = fal_client.subscribe(
                    "fal-ai/flux-lora",
                    arguments={
                        "prompt": item["prompt"],
                        "loras": [{"path": lora_url, "scale": 1.0}],
                        "image_size": "portrait_16_9",
                        "num_inference_steps": 28,
                        "guidance_scale": 3.5,
                        "num_images": 1,
                        "enable_safety_checker": True,
                    },
                )
                url = r["images"][0]["url"]
                urllib.request.urlretrieve(url, img_dir / f"scene_{item['scene']:02d}.png")
                state["images"].append(url)
                log(f"장면 {item['scene']} 완료", "ok")
                time.sleep(0.5)
            except Exception as e:
                log(f"장면 {item['scene']} 실패: {e}", "err")
        
        state["status"] = "done"
        state["step"] = 4
        log(f"🎉 완료! {len(state['images'])}장", "ok")
    
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})


@app.route('/download-md')
def download_md():
    if not state["md_content"]:
        return jsonify({"error": "없음"}), 404
    tmp = OUTPUT_DIR / "download.md"
    tmp.write_text(state["md_content"], encoding='utf-8')
    return send_file(tmp, as_attachment=True, download_name="야찌곰_대본.md")


@app.route('/reset', methods=['POST'])
def reset_route():
    reset()
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════
# v2.10 추가 엔드포인트: TTS + CapCut
# ═══════════════════════════════════════════════════════

@app.route('/list-voices', methods=['POST'])
def list_voices_route():
    """ElevenLabs 등록 Voice 목록"""
    data = request.json or {}
    api_key = data.get('eleven_key', '')
    if not api_key:
        return jsonify({"error": "ElevenLabs 키 필요"}), 400
    return jsonify(get_voice_list(api_key))


@app.route('/generate-tts', methods=['POST'])
def generate_tts():
    """대본을 장면별로 TTS 일괄 생성"""
    data = request.json or {}
    eleven_key = data.get('eleven_key', '')
    voice_id = data.get('voice_id', '')
    md = data.get('md_content', '') or state.get('md_content', '')
    model_id = data.get('model_id', TTS_DEFAULT_MODEL)
    
    if not eleven_key or not voice_id:
        return jsonify({"error": "eleven_key, voice_id 필요"}), 400
    if not md:
        return jsonify({"error": "대본(md_content) 없음"}), 400
    
    def run():
        state["status"] = "running"
        state["step"] = 5
        state["step_name"] = "TTS 음성 생성 중..."
        state["audio_files"] = []
        log(f"TTS 생성 시작 (voice: {voice_id[:8]}...)")
        
        try:
            scenes = parse_scenes_from_md(md)
            if not scenes:
                log("대본에서 장면을 찾지 못했어요", "err")
                state["status"] = "error"
                return
            
            log(f"장면 {len(scenes)}개 감지")
            safe = re.sub(r'[^\w가-힣]', '', state.get('topic', '영상'))[:20]
            audio_dir = OUTPUT_DIR / f"야지곰_{safe}_audio"
            
            def on_progress(scene_no, result):
                if result.get("ok"):
                    log(f"장면 {scene_no} TTS 완료 ({result['duration_sec']}s)", "ok")
                else:
                    log(f"장면 {scene_no} TTS 실패: {result.get('error')}", "err")
            
            results = tts_generate_batch(
                scenes=scenes,
                voice_id=voice_id,
                api_key=eleven_key,
                output_dir=audio_dir,
                model_id=model_id,
                on_progress=on_progress,
            )
            
            audio_files = [
                {
                    "scene": r["scene"],
                    "narration": r["narration"],
                    "path": r["audio_path"],
                    "duration_sec": r["duration_sec"],
                }
                for r in results if r.get("ok")
            ]
            
            state["audio_files"] = audio_files
            total_sec = sum(a["duration_sec"] for a in audio_files)
            state["status"] = "tts_ready"
            log(f"TTS 완료! {len(audio_files)}개, 총 {total_sec:.1f}초", "ok")
        
        except Exception as e:
            log(f"TTS 오류: {e}", "err")
            state["status"] = "error"
    
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})


@app.route('/build-capcut', methods=['POST'])
def build_capcut():
    """이미지 + TTS 오디오를 CapCut 프로젝트로 조립 후 주입"""
    data = request.json or {}
    inject = data.get('inject', True)
    project_name = data.get('project_name') or f"야찌곰_{state.get('topic', '영상')}"
    
    safe = re.sub(r'[^\w가-힣]', '', state.get('topic', '영상'))[:20]
    img_dir = OUTPUT_DIR / f"야지곰_{safe}_images"
    
    if not img_dir.exists():
        return jsonify({"error": f"이미지 폴더 없음: {img_dir}"}), 400
    
    audio_files = state.get("audio_files", [])
    if not audio_files:
        return jsonify({"error": "TTS 오디오 없음. 먼저 /generate-tts 실행"}), 400
    
    scenes = []
    for audio in audio_files:
        scene_no = audio["scene"]
        img_path = img_dir / f"scene_{scene_no:02d}.png"
        
        if not img_path.exists():
            log(f"장면 {scene_no} 이미지 없음, 스킵", "err")
            continue
        
        scenes.append({
            "scene": scene_no,
            "image_path": str(img_path.absolute()),
            "audio_path": audio["path"],
            "duration_sec": audio["duration_sec"],
            "narration": audio["narration"],
        })
    
    if not scenes:
        return jsonify({"error": "매칭된 장면 없음"}), 400
    
    try:
        if inject:
            result = inject_project(
                scenes=scenes,
                project_name=project_name,
                copy_media=True,
            )
            
            if result.get("ok"):
                state["capcut_project_path"] = result["project_path"]
                state["step"] = 6
                state["status"] = "capcut_ready"
                log(f"CapCut 주입 완료: {result['project_path']}", "ok")
                log(f"총 길이: {result['total_duration_sec']:.1f}초", "ok")
                log("👉 CapCut 종료 후 재실행하면 프로젝트 목록에 나와요", "ok")
            else:
                log(f"CapCut 주입 실패: {result.get('error')}", "err")
            
            return jsonify(result)
        else:
            zip_path = OUTPUT_DIR / f"capcut_{safe}.zip"
            result = export_as_zip(
                scenes=scenes,
                project_name=project_name,
                output_zip=zip_path,
            )
            if result.get("ok"):
                log(f"CapCut ZIP 생성 완료: {zip_path}", "ok")
            return jsonify(result)
    
    except Exception as e:
        log(f"CapCut 조립 오류: {e}", "err")
        return jsonify({"error": str(e)}), 500


@app.route('/download-capcut-zip')
def download_capcut_zip():
    safe = re.sub(r'[^\w가-힣]', '', state.get('topic', '영상'))[:20]
    zip_path = OUTPUT_DIR / f"capcut_{safe}.zip"
    if not zip_path.exists():
        return jsonify({"error": "ZIP 없음. 먼저 build-capcut 실행"}), 404
    return send_file(zip_path, as_attachment=True, download_name=f"{safe}_capcut.zip")


@app.route('/check-capcut-path')
def check_capcut_path():
    """CapCut 프로젝트 폴더 자동 탐지"""
    p = get_capcut_projects_dir()
    return jsonify({
        "found": p is not None,
        "path": str(p) if p else None,
    })


if __name__ == '__main__':
    print("=" * 50)
    print("🐻 야찌곰 자동화 서버 v2.10!")
    print("   - TTS (ElevenLabs) + CapCut 자동 조립")
    print("   http://localhost:8888")
    print("=" * 50)
    
    # CapCut 경로 체크
    cc = get_capcut_projects_dir()
    if cc:
        print(f"✅ CapCut 프로젝트 폴더 감지: {cc}")
    else:
        print("⚠️  CapCut 프로젝트 폴더 미감지 (CapCut 미설치 또는 미실행)")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=8888, debug=False)
