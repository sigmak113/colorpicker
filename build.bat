@echo off
REM ColorPaletteManager.exe 빌드 스크립트
REM 이 파일을 main.py와 같은 폴더에 두고 더블클릭하면 됩니다.

echo [1/2] 필요 라이브러리 설치 중...
pip install -r requirements.txt

echo [2/2] exe 빌드 중...
pyinstaller --onefile --noconsole --name "ColorPaletteManager" main.py

echo.
echo 완료! dist 폴더 안의 ColorPaletteManager.exe 를 실행하세요.
pause
