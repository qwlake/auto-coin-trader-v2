import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

def create_price_chart(state):
    """실시간 가격 차트 생성"""
    
    if state.current_price <= 0:
        return None
    
    # 시뮬레이션을 위한 샘플 데이터 생성 (실제로는 실시간 데이터 사용)
    now = datetime.now()
    times = [now - timedelta(minutes=i) for i in range(60, 0, -1)]
    
    # 현재 가격 기준으로 일관된 가격 데이터 생성 (고정 시드 사용)
    base_price = state.current_price
    prices = []
    
    # 시간에 기반한 고정 시드 사용 (1분 단위로 변경)
    current_minute = now.replace(second=0, microsecond=0)
    seed = int(current_minute.timestamp() / 60)  # 분 단위로 시드 변경
    np.random.seed(seed)
    
    for i in range(60):
        # 시간에 기반한 일관된 패턴 생성
        time_factor = np.sin(i * 0.1) * 0.0005  # 주기적 패턴
        random_factor = np.random.normal(0, base_price * 0.0005)  # 작은 랜덤 변동
        change = (time_factor + random_factor) * base_price
        price = base_price + change
        prices.append(price)
        base_price = price
    
    # 마지막은 현재 가격으로 설정
    prices[-1] = state.current_price
    
    # 차트 생성
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("가격 차트", "거래량"),
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3]
    )
    
    # 가격 라인
    fig.add_trace(
        go.Scatter(
            x=times,
            y=prices,
            mode='lines',
            name='가격',
            line=dict(color='#2E86AB', width=2)
        ),
        row=1, col=1
    )
    
    # VWAP 전략의 경우 추가 지표 표시
    if state.strategy_type == "VWAP" and state.vwap > 0:
        # VWAP 라인
        vwap_line = [state.vwap] * len(times)
        fig.add_trace(
            go.Scatter(
                x=times,
                y=vwap_line,
                mode='lines',
                name='VWAP',
                line=dict(color='#F18F01', width=2, dash='dash')
            ),
            row=1, col=1
        )
        
        # 상단/하단 밴드
        if state.upper_band > 0 and state.lower_band > 0:
            upper_band_line = [state.upper_band] * len(times)
            lower_band_line = [state.lower_band] * len(times)
            
            fig.add_trace(
                go.Scatter(
                    x=times,
                    y=upper_band_line,
                    mode='lines',
                    name='상단밴드',
                    line=dict(color='#E71D36', width=1, dash='dot'),
                    opacity=0.7
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=times,
                    y=lower_band_line,
                    mode='lines',
                    name='하단밴드',
                    line=dict(color='#2D9D32', width=1, dash='dot'),
                    opacity=0.7,
                    fill='tonexty',
                    fillcolor='rgba(45, 157, 50, 0.1)'
                ),
                row=1, col=1
            )
    
    # 일관된 거래량 데이터 (같은 시드 사용)
    volumes = np.random.uniform(100, 1000, len(times))
    
    fig.add_trace(
        go.Bar(
            x=times,
            y=volumes,
            name='거래량',
            marker_color='rgba(46, 134, 171, 0.6)'
        ),
        row=2, col=1
    )
    
    # 레이아웃 설정
    fig.update_layout(
        height=600,
        title_text=f"{state.strategy_type} 전략 - 실시간 차트",
        showlegend=True,
        xaxis_rangeslider_visible=False,
        template="plotly_white"
    )
    
    # X축 설정
    fig.update_xaxes(title_text="시간", row=2, col=1)
    
    # Y축 설정
    fig.update_yaxes(title_text="가격 ($)", row=1, col=1)
    fig.update_yaxes(title_text="거래량", row=2, col=1)
    
    return fig

def create_pnl_chart(closed_positions):
    """PnL 누적 차트 생성"""
    
    if not closed_positions:
        return None
    
    # 데이터프레임 생성
    df = pd.DataFrame(closed_positions)
    
    if 'pnl' not in df.columns or 'timestamp' not in df.columns:
        return None
    
    # 시간순 정렬
    df = df.sort_values('timestamp')
    
    # 누적 PnL 계산
    df['cumulative_pnl'] = df['pnl'].cumsum()
    
    # 색상 설정 (양수/음수)
    colors = ['green' if pnl >= 0 else 'red' for pnl in df['cumulative_pnl']]
    
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("누적 PnL", "개별 거래 PnL"),
        vertical_spacing=0.15,
        row_heights=[0.6, 0.4]
    )
    
    # 누적 PnL 라인 차트
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['cumulative_pnl'],
            mode='lines+markers',
            name='누적 PnL',
            line=dict(color='#2E86AB', width=3),
            marker=dict(size=6),
            fill='tonexty' if df['cumulative_pnl'].iloc[-1] >= 0 else 'tozeroy',
            fillcolor='rgba(46, 134, 171, 0.2)' if df['cumulative_pnl'].iloc[-1] >= 0 else 'rgba(231, 29, 54, 0.2)'
        ),
        row=1, col=1
    )
    
    # 0선 표시
    fig.add_hline(
        y=0, 
        line_dash="dash", 
        line_color="gray",
        row=1, col=1
    )
    
    # 개별 거래 PnL 바 차트
    bar_colors = ['rgba(45, 157, 50, 0.7)' if pnl >= 0 else 'rgba(231, 29, 54, 0.7)' for pnl in df['pnl']]
    
    fig.add_trace(
        go.Bar(
            x=df['timestamp'],
            y=df['pnl'],
            name='개별 PnL',
            marker_color=bar_colors,
            text=[f"${pnl:.2f}" for pnl in df['pnl']],
            textposition='outside'
        ),
        row=2, col=1
    )
    
    # 레이아웃 설정
    fig.update_layout(
        height=500,
        title_text="손익 현황",
        showlegend=True,
        template="plotly_white"
    )
    
    # Y축 설정
    fig.update_yaxes(title_text="누적 PnL ($)", row=1, col=1)
    fig.update_yaxes(title_text="개별 PnL ($)", row=2, col=1)
    fig.update_xaxes(title_text="시간", row=2, col=1)
    
    return fig

def create_strategy_indicator_chart(state):
    """전략별 지표 차트"""
    
    if state.strategy_type == "VWAP":
        return create_vwap_indicator_chart(state)
    else:  # OBI
        return create_obi_indicator_chart(state)

def create_vwap_indicator_chart(state):
    """VWAP 지표 차트"""
    
    # ADX 게이지 차트
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = state.adx,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "ADX (추세 강도)"},
        delta = {'reference': 20},
        gauge = {
            'axis': {'range': [None, 50]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 20], 'color': "lightgray"},
                {'range': [20, 40], 'color': "yellow"},
                {'range': [40, 50], 'color': "red"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 40
            }
        }
    ))
    
    fig.update_layout(height=300, title="VWAP 전략 지표")
    
    return fig

def create_obi_indicator_chart(state):
    """OBI 지표 차트"""
    
    # OBI 게이지 차트
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = state.obi_value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "OBI (호가 불균형)"},
        gauge = {
            'axis': {'range': [0, 1]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 0.3], 'color': "red"},
                {'range': [0.3, 0.7], 'color': "lightgray"},
                {'range': [0.7, 1], 'color': "green"}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': 0.5
            }
        }
    ))
    
    fig.update_layout(height=300, title="OBI 전략 지표")
    
    return fig