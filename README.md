# 컬러 팔레트 매니저

프리미어 프로 등 어떤 프로그램에서든 클립보드 붙여넣기(Ctrl+V)로 바로 색상을 적용할 수 있도록 만든
자주 쓰는 색상 관리 도구입니다.

## 기능

- **5개 세트 × 5개 색상 슬롯**: 상단 버튼으로 세트 전환 (더블클릭하면 세트 이름 변경)
- **클릭 한 번으로 클립보드 복사**: 색상을 클릭하면 `#RRGGBB` 형식으로 자동 복사됩니다.
  프리미어 프로 Lumetri 색상창의 색상 코드 입력란에 Ctrl+V로 바로 붙여넣기 가능합니다.
- **색상 지정 두 가지 방법** (슬롯 우클릭):
  1. 팔레트에서 선택 (일반 색상 선택창)
  2. **스포이드로 화면에서 추출**: 버튼을 누르면 화면 전체가 캡처되고, 원하는 지점을 클릭하면
     그 픽셀의 색상을 그대로 가져옵니다. (브라우저, 다른 프로그램 화면 등 어디서든 가능)
- **자동 저장**: `colors_data.json` 파일에 실시간 저장되어 프로그램을 껐다 켜도 유지됩니다.

## ⭐ exe 빌드 방법 (파이썬 설치 필요 없음 — GitHub Actions 사용)

내 컴퓨터에 아무것도 설치하지 않고, 브라우저만으로 진짜 Windows exe를 만들 수 있습니다.
(빌드는 GitHub이 무료로 제공하는 클라우드 Windows 서버에서 진행됩니다.)

1. https://github.com 에서 무료 계정 가입 (이미 있으면 로그인)
2. 오른쪽 위 **+** 버튼 → **New repository** 클릭 → 이름 아무거나 입력 (예: `color-tool`) → Public 선택 → **Create repository**
3. 생성된 저장소 페이지에서 **Add file → Upload files** 클릭
4. 이 압축파일(`color_palette_manager.zip`)의 압축을 풀어서, **폴더 안의 파일 전체**(`.github` 폴더 포함)를
   드래그 앤 드롭으로 업로드 → 아래 **Commit changes** 클릭
   - ⚠️ `.github` 폴더도 반드시 같이 올라가야 합니다 (숨김 폴더처럼 보이지만 웹 업로드 시 자동 포함됩니다)
5. 상단 메뉴의 **Actions** 탭 클릭 → "Build EXE" 워크플로우가 자동으로 실행 중일 거예요
   (안 보이면 왼쪽에서 "Build EXE" 클릭 → **Run workflow** 버튼 클릭)
6. 노란 점(진행 중) → 초록 체크(완료)로 바뀔 때까지 1~2분 대기
7. 완료된 실행 결과 클릭 → 맨 아래 **Artifacts** 항목에서 `ColorPaletteManager-exe` 다운로드
8. 압축 풀면 `ColorPaletteManager.exe` 완성! 이제 이 파일만 배포하면 되고, 받는 사람도 파이썬 필요 없습니다.

---

## 실행 방법 (개발/테스트용, Python 필요)

```bash
pip install -r requirements.txt
python main.py
```

## exe로 빌드하는 방법 (Windows에서 진행)

⚠️ **exe 빌드는 반드시 Windows PC에서 실행해야 합니다.** (PyInstaller는 실행 중인 운영체제용
실행 파일만 만들 수 있어서, Mac/Linux에서는 Windows용 exe를 만들 수 없습니다.)

1. Windows PC에 [Python](https://www.python.org/downloads/) 설치 (설치 시 "Add to PATH" 체크)
2. 이 폴더 전체를 Windows PC로 복사
3. `build.bat` 더블클릭
   - 또는 직접 명령어 실행:
     ```
     pip install -r requirements.txt
     pyinstaller --onefile --noconsole --name "ColorPaletteManager" main.py
     ```
4. 빌드가 끝나면 `dist` 폴더 안에 `ColorPaletteManager.exe` 생성됨
5. 이 exe 파일만 원하는 곳에 복사해서 사용하면 됩니다 (같은 폴더에 `colors_data.json`이 자동 생성됨)

## 파일 구성

- `main.py` — 프로그램 본체
- `requirements.txt` — 필요 라이브러리 목록
- `build.bat` — exe 자동 빌드 스크립트 (Windows용)
- `colors_data.json` — 저장된 색상 데이터 (최초 실행 시 자동 생성)

## 참고 / 한계

- 스포이드 기능은 현재 **주 모니터 기준**으로 캡처합니다. 멀티 모니터 환경에서 다른 모니터의 색을
  뽑아야 한다면 알려주세요 — 전체 가상 화면을 캡처하도록 확장할 수 있습니다.
- 프리미어 프로 자체에 패널로 뜨는 확장 프로그램(CEP/UXP) 방식이 아니라, **클립보드 복사 → 붙여넣기**
  방식으로 연동합니다. 프리미어 안에서 직접 패널로 띄우고 싶어지면 별도로 확장 프로그램을 만들 수
  있습니다 (개발 난이도가 훨씬 높아짐).
