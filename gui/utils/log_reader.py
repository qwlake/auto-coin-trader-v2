import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

def get_recent_logs(max_lines: int = 100) -> List[Dict]:
    """최근 로그 읽기"""
    try:
        # 로그 파일 경로 찾기
        log_dir = Path("storage")
        log_files = list(log_dir.glob("*.log"))
        
        if not log_files:
            return [{"timestamp": datetime.now(), "level": "INFO", "message": "로그 파일을 찾을 수 없습니다."}]
        
        # 가장 최근 로그 파일
        latest_log = max(log_files, key=os.path.getmtime)
        
        logs = []
        with open(latest_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # 최근 라인들만 가져오기
        recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines
        
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue
                
            # 간단한 로그 파싱 (실제로는 더 정교한 파싱 필요)
            try:
                parts = line.split(" - ")
                if len(parts) >= 3:
                    timestamp_str = parts[0]
                    level = parts[1]
                    message = " - ".join(parts[2:])
                    
                    logs.append({
                        "timestamp": timestamp_str,
                        "level": level,
                        "message": message
                    })
                else:
                    logs.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "level": "INFO",
                        "message": line
                    })
            except:
                logs.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "level": "INFO", 
                    "message": line
                })
        
        return logs
        
    except Exception as e:
        return [{"timestamp": datetime.now(), "level": "ERROR", "message": f"로그 읽기 오류: {e}"}]

def get_trading_logs(max_lines: int = 50) -> List[Dict]:
    """거래 관련 로그만 필터링"""
    all_logs = get_recent_logs(max_lines * 2)  # 더 많이 읽어서 필터링
    
    trading_keywords = ["LONG", "SHORT", "BUY", "SELL", "order", "position", "PnL", "signal", "VWAP", "OBI"]
    
    trading_logs = []
    for log in all_logs:
        message = log["message"].lower()
        if any(keyword.lower() in message for keyword in trading_keywords):
            trading_logs.append(log)
            
        if len(trading_logs) >= max_lines:
            break
    
    return trading_logs