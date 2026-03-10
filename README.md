<div align="center">

# JSON Translator

Desktop JSON translation tool for game/localization workflows.  
게임/로컬라이징 워크플로우를 위한 데스크톱 JSON 번역 도구입니다.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![UI](https://img.shields.io/badge/UI-Tkinter%20%2B%20ttkbootstrap-2E8B57)
![Providers](https://img.shields.io/badge/Providers-OpenAI%20%7C%20Gemini-0A66C2)
![Version](https://img.shields.io/badge/Version-1.0.0-111827)

</div>

---

> [!WARNING]
> 이 프로젝트는 **바이브 코딩(AI 보조 코딩)** 방식으로 개발되었습니다.  
> 운영/배포 전, 보안(키 관리), 예외 처리, 번역 품질, 파일 덮어쓰기 동작을 반드시 직접 검증하세요.

> [!WARNING]
> This project was developed using **vibe coding (AI-assisted coding)**.  
> Before production use, manually validate security (key handling), error handling, translation quality, and overwrite behavior.

## 한국어

### 프로젝트 소개
JSON 구조를 유지하면서 텍스트 값만 선택적으로 번역하는 도구입니다.  
키 기반 포함/제외 관리, API 키 로테이션, 자동 저장, 상세 로그 기능을 제공합니다.

### 주요 기능
- JSON 파일 로드, 미리보기, 키 분석
- Key Manager를 통한 Translate/Exclude 분류
- Provider 선택: OpenAI / Gemini
- Source Language: auto, en, ja, ko
- Target Language: ko, en, ja
- 번역 중 UI 잠금(섹션 1~4)
- API 오류 재시도(지수 백오프 + 지터)
- 연속 오류 시 다음 API 키로 자동 전환
- 번역 완료 시 자동 저장 + 로그 저장
- 자동 지정 저장 경로 덮어쓰기 확인

### 설치
```bash
pip install -r requirements.txt
```

### 실행
```bash
python main.py
```

### 빠른 사용 방법
1. JSON 파일 선택
2. Analyze Keys 실행
3. Key Manager에서 번역 대상 키 조정
4. Provider/Model/언어 설정
5. API Key Manager에 키 등록
6. Start Translation 실행

### 핵심 로직 요약
- 문자열 값(`str`)을 가진 키만 번역 후보로 추출
- 파일 변경 후 키 분석 시, 이전 분류 키는 "교집합만 유지"
- 신규 키는 자동으로 Translate에 추가
- Source가 `auto`면 텍스트 언어를 자동 감지
- Source와 Target이 같으면 API 호출 전 로컬에서 차단
- 번역은 백그라운드 스레드에서 수행되고 진행률/로그를 실시간 갱신

### 프로젝트 구조
```text
main.py             # 애플리케이션 전체 로직(UI + 번역 파이프라인)
requirements.txt    # 의존성
AI_HANDOFF.md       # AI 유지보수/개발 인수인계 문서
test_json/          # 테스트용 샘플 JSON
```

### 의존 패키지
- ttkbootstrap
- openai
- google-genai

---

## English

### Overview
This tool translates only text values in JSON while preserving overall structure.  
It includes key-based include/exclude control, API key rotation, auto-save, and detailed logs.

### Key Features
- JSON load, preview, and key analysis
- Translate/Exclude management via Key Manager
- Provider support: OpenAI / Gemini
- Source Language: auto, en, ja, ko
- Target Language: ko, en, ja
- UI lock for sections 1-4 during translation
- Retry with exponential backoff + jitter
- Automatic API key rotation after repeated failures
- Auto-save translated output + save logs
- Overwrite confirmation for auto-assigned output path

### Installation
```bash
pip install -r requirements.txt
```

### Run
```bash
python main.py
```

### Quick Start
1. Select a JSON file
2. Run Analyze Keys
3. Adjust translation target keys in Key Manager
4. Configure Provider/Model/Languages
5. Add API keys in API Key Manager
6. Start Translation

### Core Logic Summary
- Only keys with string values are treated as translatable candidates
- On new file analysis, prior key classification is retained by intersection only
- New keys are automatically added to Translate
- If source is `auto`, source language is detected from input text
- If source and target are the same, translation is blocked locally before API calls
- Translation runs in a background thread with real-time progress and logs

### Project Structure
```text
main.py             # Full app logic (UI + translation pipeline)
requirements.txt    # Dependencies
AI_HANDOFF.md       # AI handoff/maintenance document
test_json/          # Test sample JSON files
```

### Dependencies
- ttkbootstrap
- openai
- google-genai

---

## License
If you plan to publish publicly, add your preferred license file (for example, MIT).
