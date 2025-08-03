#!/usr/bin/env python3
"""
Streamlit GUI 실행 스크립트

사용법:
    python run_gui.py

또는 직접:
    streamlit run gui/streamlit_app.py
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    # 프로젝트 루트 디렉토리로 이동
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Streamlit 앱 경로
    app_path = "gui/streamlit_app.py"
    
    if not Path(app_path).exists():
        print(f"오류: {app_path} 파일을 찾을 수 없습니다.")
        sys.exit(1)
    
    print("🚀 Crypto Trading Bot GUI 시작 중...")
    print(f"📍 앱 경로: {app_path}")
    print("🌐 브라우저에서 http://localhost:8501 로 접속하세요")
    print("🔄 GUI는 자동으로 새로고침됩니다")
    print("⚠️  봇이 실행 중이어야 실시간 데이터를 볼 수 있습니다")
    print("\n" + "="*50 + "\n")
    
    try:
        # Streamlit 실행
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", app_path,
            "--server.runOnSave", "true",
            "--server.address", "localhost",
            "--server.port", "8501"
        ])
    except KeyboardInterrupt:
        print("\n\n👋 GUI를 종료합니다.")
    except Exception as e:
        print(f"❌ GUI 실행 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()