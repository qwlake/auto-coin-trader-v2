import streamlit as st
from datetime import datetime
import time

def create_metrics_widgets(state, daily_stats):
    """주요 지표 위젯 생성"""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        price_color = "normal"
        if hasattr(state, 'prev_price') and state.prev_price:
            if state.current_price > state.prev_price:
                price_color = "normal"
            elif state.current_price < state.prev_price:
                price_color = "inverse"
        
        st.metric(
            label="💰 현재 가격",
            value=f"${state.current_price:,.2f}" if state.current_price > 0 else "연결 중...",
            delta=f"{state.current_price - getattr(state, 'prev_price', state.current_price):+.2f}" if hasattr(state, 'prev_price') and state.prev_price else None,
            delta_color=price_color
        )
    
    with col2:
        pnl_color = "normal"
        if daily_stats['total_pnl'] < 0:
            pnl_color = "inverse"
        
        st.metric(
            label="📈 일일 PnL",
            value=f"${daily_stats['total_pnl']:+.2f}",
            delta=f"{daily_stats['total_trades']} 거래",
            delta_color=pnl_color
        )
    
    with col3:
        win_rate_color = "normal"
        if daily_stats['win_rate'] < 50:
            win_rate_color = "inverse"
        
        st.metric(
            label="🎯 승률",
            value=f"{daily_stats['win_rate']:.1f}%",
            delta=f"{daily_stats['winning_trades']}/{daily_stats['total_trades']}",
            delta_color=win_rate_color
        )
    
    with col4:
        st.metric(
            label="⚡ 전략",
            value=state.strategy_type,
            delta="활성" if not state.is_halted else "중단됨"
        )

def create_status_widgets(state):
    """상태 위젯 생성"""
    
    # 전략별 상태 표시
    if state.strategy_type == "VWAP":
        create_vwap_status_widget(state)
    else:
        create_obi_status_widget(state)

def create_vwap_status_widget(state):
    """VWAP 전략 상태 위젯"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 신호 상태
        signal_color = {
            "LONG": "🟢",
            "SHORT": "🔴", 
            "": "⚪"
        }.get(state.signal, "⚪")
        
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 10px; background-color: #f0f2f6; text-align: center;">
            <h4>거래 신호</h4>
            <h2>{signal_color} {state.signal or 'NONE'}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # VWAP 대비 가격 위치
        if state.vwap > 0 and state.current_price > 0:
            price_vs_vwap = ((state.current_price - state.vwap) / state.vwap) * 100
            color = "green" if price_vs_vwap > 0 else "red"
            
            st.markdown(f"""
            <div style="padding: 1rem; border-radius: 10px; background-color: #f0f2f6; text-align: center;">
                <h4>VWAP 대비</h4>
                <h2 style="color: {color};">{price_vs_vwap:+.2f}%</h2>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="padding: 1rem; border-radius: 10px; background-color: #f0f2f6; text-align: center;">
                <h4>VWAP 대비</h4>
                <h2>계산 중...</h2>
            </div>
            """, unsafe_allow_html=True)
    
    with col3:
        # ADX 상태
        adx_status = "강한 추세" if state.adx > 40 else "추세 발생" if state.adx > 20 else "횡보"
        adx_color = "red" if state.adx > 40 else "orange" if state.adx > 20 else "green"
        
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 10px; background-color: #f0f2f6; text-align: center;">
            <h4>시장 상태 (ADX: {state.adx:.1f})</h4>
            <h3 style="color: {adx_color};">{adx_status}</h3>
        </div>
        """, unsafe_allow_html=True)

def create_obi_status_widget(state):
    """OBI 전략 상태 위젯"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 신호 상태
        signal_color = {
            "BUY": "🟢",
            "SELL": "🔴",
            "": "⚪"
        }.get(state.signal, "⚪")
        
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 10px; background-color: #f0f2f6; text-align: center;">
            <h4>거래 신호</h4>
            <h2>{signal_color} {state.signal or 'NONE'}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # OBI 값
        obi_status = "매수 우세" if state.obi_value > 0.7 else "매도 우세" if state.obi_value < 0.3 else "균형"
        obi_color = "green" if state.obi_value > 0.7 else "red" if state.obi_value < 0.3 else "orange"
        
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 10px; background-color: #f0f2f6; text-align: center;">
            <h4>OBI: {state.obi_value:.3f}</h4>
            <h3 style="color: {obi_color};">{obi_status}</h3>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # 임계값 표시
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 10px; background-color: #f0f2f6; text-align: center;">
            <h4>임계값</h4>
            <div>매도: < 0.30</div>
            <div>매수: > 0.70</div>
        </div>
        """, unsafe_allow_html=True)

def create_connection_status_widget():
    """연결 상태 위젯"""
    
    # 간단한 연결 상태 표시 (실제로는 웹소켓 상태 등을 확인)
    current_time = datetime.now()
    
    st.markdown(f"""
    <div style="padding: 0.5rem; border-radius: 5px; background-color: rgba(0, 255, 0, 0.1); text-align: center; margin-bottom: 1rem;">
        🟢 <strong>연결됨</strong> | 마지막 업데이트: {current_time.strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)

def create_alert_widget(alerts=None):
    """알림 위젯"""
    
    if alerts:
        for alert in alerts:
            if alert['type'] == 'success':
                st.success(f"✅ {alert['message']}")
            elif alert['type'] == 'warning':
                st.warning(f"⚠️ {alert['message']}")
            elif alert['type'] == 'error':
                st.error(f"🚨 {alert['message']}")
            else:
                st.info(f"ℹ️ {alert['message']}")

def create_performance_summary_widget(daily_stats):
    """성과 요약 위젯"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 수익성 지표
        profit_factor = "N/A"
        if daily_stats['total_trades'] > 0:
            winning_amount = sum([t for t in [daily_stats['total_pnl']] if t > 0]) or 0
            losing_amount = abs(sum([t for t in [daily_stats['total_pnl']] if t < 0])) or 1
            profit_factor = f"{winning_amount/losing_amount:.2f}"
        
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 10px; background-color: #f0f2f6;">
            <h4>📊 성과 지표</h4>
            <div><strong>총 거래:</strong> {daily_stats['total_trades']}</div>
            <div><strong>승률:</strong> {daily_stats['win_rate']:.1f}%</div>
            <div><strong>수익 팩터:</strong> {profit_factor}</div>
            <div><strong>평균 손익:</strong> ${daily_stats['avg_pnl']:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # 리스크 지표
        max_loss_pct = "N/A"
        if daily_stats['total_pnl'] != 0:
            max_loss_pct = f"{(daily_stats['min_pnl'] / abs(daily_stats['total_pnl'])) * 100:.1f}%"
        
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 10px; background-color: #f0f2f6;">
            <h4>⚠️ 리스크 지표</h4>
            <div><strong>최대 손실:</strong> ${daily_stats['min_pnl']:.2f}</div>
            <div><strong>최대 이익:</strong> ${daily_stats['max_pnl']:.2f}</div>
            <div><strong>손실 비율:</strong> {max_loss_pct}</div>
        </div>
        """, unsafe_allow_html=True)