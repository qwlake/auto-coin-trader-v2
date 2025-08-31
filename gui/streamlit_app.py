import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import time
from datetime import datetime, timedelta, timezone
import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.data_broker import data_broker, db_reader
from gui.components.charts import create_price_chart, create_pnl_chart
from gui.components.tables import create_positions_table, create_trades_table
from gui.components.widgets import create_metrics_widgets, create_status_widgets

# 페이지 설정
st.set_page_config(
    page_title="Crypto Trading Bot Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 설정
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .positive { color: #00ff00; }
    .negative { color: #ff0000; }
    .neutral { color: #ffa500; }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("🚀 Crypto Trading Bot Monitor")
    
    # 사이드바
    with st.sidebar:
        st.header("⚙️ 설정")
        
        # 자동 새로고침 설정
        auto_refresh = st.checkbox("자동 새로고침", value=True)
        refresh_interval = st.slider("새로고침 간격 (초)", 1, 10, 2)
        
        st.divider()
        
        # 수동 새로고침 버튼
        if st.button("🔄 지금 새로고침", use_container_width=True):
            st.rerun()
        
        st.divider()
        
        # 현재 시간
        st.write(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 데이터 로드
    state = data_broker.get_state()
    daily_stats = db_reader.get_daily_stats()
    active_positions = db_reader.get_active_positions()
    closed_positions = db_reader.get_closed_positions(limit=20)
    connection_stats = data_broker.get_connection_stats()
    
    # 메인 대시보드
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 현재 가격",
            value=f"${state.current_price:,.2f}" if state.current_price > 0 else "N/A"
        )
    
    with col2:
        pnl_color = "normal"
        if daily_stats['total_pnl'] > 0:
            pnl_color = "normal"
        elif daily_stats['total_pnl'] < 0:
            pnl_color = "inverse"
            
        st.metric(
            label="📈 일일 PnL",
            value=f"${daily_stats['total_pnl']:,.2f}",
            delta=f"{daily_stats['total_pnl']:+.2f}",
            delta_color=pnl_color
        )
    
    with col3:
        st.metric(
            label="🎯 승률",
            value=f"{daily_stats['win_rate']:.1f}%",
            delta=f"{daily_stats['winning_trades']}/{daily_stats['total_trades']}"
        )
    
    with col4:
        st.metric(
            label="⚡ 활성 포지션",
            value=len(active_positions)
        )
    
    st.divider()
    
    # 전략 상태 섹션
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📊 전략 상태")
        
        # 전략 타입과 상태
        strategy_info = st.container()
        with strategy_info:
            scol1, scol2, scol3 = st.columns(3)
            
            with scol1:
                st.info(f"**전략**: {state.strategy_type}")
            
            with scol2:
                signal_color = "🟢" if state.signal == "LONG" else "🔴" if state.signal == "SHORT" else "⚪"
                st.info(f"**신호**: {signal_color} {state.signal or 'NONE'}")
            
            with scol3:
                halt_status = "🚨 중단됨" if state.is_halted else "✅ 활성"
                st.info(f"**상태**: {halt_status}")
    
    with col2:
        st.subheader("🔍 지표 현황")
        
        if state.strategy_type == "VWAP":
            st.write(f"**VWAP**: ${state.vwap:.2f}")
            st.write(f"**상단밴드**: ${state.upper_band:.2f}")
            st.write(f"**하단밴드**: ${state.lower_band:.2f}")
            st.write(f"**ADX**: {state.adx:.2f}")
        else:  # OBI
            st.write(f"**OBI**: {state.obi_value:.3f}")
            st.write(f"**임계값**: 0.30 / 0.70")
    
    # 차트 섹션
    st.subheader("📈 실시간 차트")
    
    chart_tab1, chart_tab2 = st.tabs(["가격 차트", "PnL 차트"])
    
    with chart_tab1:
        try:
            chart = asyncio.run(create_price_chart(state))
            if chart:
                st.plotly_chart(chart, use_container_width=True)
            else:
                st.info("차트 데이터를 로딩 중입니다...")
        except Exception as e:
            st.error(f"차트 로딩 오류: {e}")
    
    with chart_tab2:
        try:
            pnl_chart = create_pnl_chart(closed_positions)
            if pnl_chart:
                st.plotly_chart(pnl_chart, use_container_width=True)
            else:
                st.info("PnL 데이터가 없습니다.")
        except Exception as e:
            st.error(f"PnL 차트 오류: {e}")
    
    # 포지션 및 거래 테이블
    st.subheader("💼 포지션 및 거래 현황")
    
    table_tab1, table_tab2 = st.tabs(["활성 포지션", "최근 거래"])
    
    with table_tab1:
        if active_positions:
            df = pd.DataFrame(active_positions)
            # timestamp 컬럼이 있으면 UTC에서 로컬 타임으로 변환
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(None)
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "order_id": "주문 ID",
                    "symbol": "심볼",
                    "side": "방향",
                    "entry_price": st.column_config.NumberColumn("진입가", format="$%.2f"),
                    "quantity": st.column_config.NumberColumn("수량", format="%.6f"),
                    "strategy_type": "전략",
                    "timestamp": st.column_config.DatetimeColumn("시간")
                }
            )
        else:
            st.info("활성 포지션이 없습니다.")
    
    with table_tab2:
        if closed_positions:
            df = pd.DataFrame(closed_positions)
            # timestamp 컬럼이 있으면 UTC에서 로컬 타임으로 변환
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(None)
            # PnL 컬럼에 색상 적용
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "order_id": "주문 ID",
                    "symbol": "심볼", 
                    "side": "방향",
                    "entry_price": st.column_config.NumberColumn("진입가", format="$%.2f"),
                    "exit_price": st.column_config.NumberColumn("청산가", format="$%.2f"),
                    "quantity": st.column_config.NumberColumn("수량", format="%.6f"),
                    "pnl": st.column_config.NumberColumn("손익", format="$%.2f"),
                    "strategy_type": "전략",
                    "exit_reason": "청산사유",
                    "timestamp": st.column_config.DatetimeColumn("시간")
                }
            )
        else:
            st.info("거래 내역이 없습니다.")
    
    # 통계 요약
    st.subheader("📊 오늘의 통계")
    
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    
    with stat_col1:
        st.metric("총 거래", daily_stats['total_trades'])
    
    with stat_col2:
        st.metric("승리 거래", daily_stats['winning_trades'])
    
    with stat_col3:
        st.metric("평균 손익", f"${daily_stats['avg_pnl']:.2f}")
    
    with stat_col4:
        st.metric("최대 손실", f"${daily_stats['min_pnl']:.2f}")
    
    # 자동 새로고침
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()