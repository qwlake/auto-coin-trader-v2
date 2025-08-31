import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta, timezone
import numpy as np
import aiosqlite



async def get_vwap_history_from_db(points_needed: int):
    """DB에서 VWAP 히스토리 데이터 조회"""
    try:
        from config.settings import settings
        
        # 필요한 포인트 수의 2배 조회 (충분한 데이터 확보)
        limit = max(points_needed * 2, 100)
        
        async with aiosqlite.connect("storage/orders.db") as db:
            cursor = await db.execute(
                """
                SELECT timestamp, vwap, upper_band, lower_band, current_price, adx
                FROM vwap_history 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (settings.SYMBOL, limit)
            )
            rows = await cursor.fetchall()
            
            if not rows:
                return None
                
            # 시간순으로 정렬 (최신이 마지막)
            rows.reverse()
            
            return [
                {
                    'timestamp': row[0],
                    'vwap': row[1],
                    'upper_band': row[2],
                    'lower_band': row[3],
                    'current_price': row[4],
                    'adx': row[5]
                }
                for row in rows
            ]
    except Exception as e:
        from utils.logger import log
        log.error(f"Error getting VWAP history: {e}")
        return None


def align_vwap_with_chart_times(chart_times, vwap_history):
    """VWAP 히스토리를 차트 시간에 맞춰 정렬"""
    if not vwap_history:
        return [], [], [], []
    
    # VWAP 히스토리 데이터를 시간 기준으로 정렬
    vwap_data = {}
    for entry in vwap_history:
        timestamp_str = entry['timestamp']
        try:
            # SQLite datetime을 파싱 (UTC 시간으로 가정)
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # 로컬 타임으로 변환
            dt = dt.astimezone()
            vwap_data[dt] = entry
        except:
            # 다른 형식 시도
            try:
                # UTC 시간으로 가정하고 로컬 타임으로 변환
                dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc).astimezone()
                vwap_data[dt] = entry
            except:
                continue
    
    if not vwap_data:
        return [], [], [], []
    
    # 차트 시간 범위 확인
    chart_start = min(chart_times)
    chart_end = max(chart_times)
    
    # 차트 시간 범위 내의 VWAP 데이터 필터링
    filtered_times = []
    filtered_vwap = []
    filtered_upper = []
    filtered_lower = []
    
    for dt, entry in sorted(vwap_data.items()):
        # 차트 시간 범위 ±10분 내의 데이터만 사용
        if chart_start - timedelta(minutes=10) <= dt <= chart_end + timedelta(minutes=10):
            filtered_times.append(dt)
            filtered_vwap.append(entry['vwap'])
            filtered_upper.append(entry['upper_band'] or entry['vwap'])
            filtered_lower.append(entry['lower_band'] or entry['vwap'])
    
    return filtered_times, filtered_vwap, filtered_upper, filtered_lower


async def get_real_ohlcv_data(state):
    """바이낸스에서 실제 OHLCV 캔들 데이터를 가져와서 반환"""
    from binance import AsyncClient
    from config.settings import settings
    
    try:
        # AsyncClient 생성
        kwargs = {
            "api_key": settings.BINANCE_API_KEY,
            "api_secret": settings.BINANCE_SECRET,
            "testnet": settings.TESTNET,
        }
        client = await AsyncClient.create(**kwargs)
        
        try:
            # 최근 50개의 1분 캔들 데이터 가져오기 (더 많은 데이터로 캔들 차트 품질 향상)
            klines = await client.futures_klines(
                symbol=settings.SYMBOL,
                interval="1m",
                limit=50
            )
            
            # OHLCV 데이터 파싱
            times = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
            
            for kline in klines:
                # kline 구조: [시작시간, 시가, 고가, 저가, 종가, 거래량, ...]
                timestamp = int(kline[0]) / 1000  # 밀리초를 초로 변환
                open_price = float(kline[1])
                high_price = float(kline[2])
                low_price = float(kline[3])
                close_price = float(kline[4])
                volume = float(kline[5])
                
                # UTC 시간을 로컬 타임으로 변환
                utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                local_time = utc_time.astimezone()
                times.append(local_time)
                opens.append(open_price)
                highs.append(high_price)
                lows.append(low_price)
                closes.append(close_price)
                volumes.append(volume)
            
            return times, opens, highs, lows, closes, volumes
            
        finally:
            await client.close_connection()
            
    except Exception as e:
        from utils.logger import log
        log.error(f"Error fetching OHLCV data from Binance: {e}")
        # 오류 발생 시 폴백: 현재 가격을 사용한 단순 데이터
        # 로컬 시간으로 생성
        now = datetime.now()
        times = [now - timedelta(minutes=i) for i in range(50, -1, -1)]
        current_price = state.current_price
        opens = [current_price] * len(times)
        highs = [current_price * 1.001] * len(times)  # 0.1% 위
        lows = [current_price * 0.999] * len(times)   # 0.1% 아래
        closes = [current_price] * len(times)
        volumes = [1000.0] * len(times)  # 임시 거래량
        return times, opens, highs, lows, closes, volumes

async def create_price_chart(state):
    """실시간 캔들스틱 차트 생성"""
    
    try:
        if state.current_price <= 0:
            return None
        
        # 1. 기본 데이터 준비
        times, opens, highs, lows, closes, volumes = await get_real_ohlcv_data(state)
        
        # 데이터 검증 및 정리
        if any(p <= 0 for p in closes):
            from utils.logger import log
            log.warning("Found non-positive prices in closes")
            # 음수나 0인 가격을 현재 가격으로 대체
            for i in range(len(closes)):
                if closes[i] <= 0:
                    closes[i] = state.current_price
                if opens[i] <= 0:
                    opens[i] = state.current_price
                if highs[i] <= 0:
                    highs[i] = state.current_price
                if lows[i] <= 0:
                    lows[i] = state.current_price
        
        # 2. 보조 지표 데이터 준비
        indicator_data = await _prepare_indicator_data(state, times)
        
        # 3. 차트 레이아웃 생성
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("캔들스틱 차트", "거래량"),
            vertical_spacing=0.1,
            row_heights=[0.7, 0.3]
        )
        
        # 4. 메인 캔들스틱 차트 추가
        _add_candlestick_chart(fig, times, opens, highs, lows, closes)
        
        # 5. 전략별 보조 지표 추가 (캔들스틱 차트에 오버레이)
        _add_strategy_indicators(fig, state, indicator_data, times)
        
        # 6. 거래량 차트 추가
        _add_volume_chart(fig, times, volumes)
        
        # 7. 차트 레이아웃 및 축 설정
        _configure_chart_layout(fig, state, highs, lows)
        
        return fig
        
    except Exception as e:
        from utils.logger import log
        log.error(f"Error creating price chart: {e}")
        log.debug(f"State data: current_price={getattr(state, 'current_price', 'N/A')}, strategy_type={getattr(state, 'strategy_type', 'N/A')}")
        log.exception("Chart creation error details:")
        return None


async def _prepare_indicator_data(state, chart_times):
    """보조 지표 데이터 준비"""
    indicator_data = {
        'vwap_history': None,
        'adx_times': [],
        'adx_values': []
    }
    
    try:
        # VWAP 히스토리 데이터 가져오기
        vwap_history = await get_vwap_history_from_db(len(chart_times))
        indicator_data['vwap_history'] = vwap_history
        
        # ADX 데이터 추출 및 시간 정렬
        if vwap_history:
            adx_times, adx_values = _extract_adx_data(vwap_history, chart_times)
            indicator_data['adx_times'] = adx_times
            indicator_data['adx_values'] = adx_values
            
    except Exception as e:
        from utils.logger import log
        log.error(f"Error preparing indicator data: {e}")
    
    return indicator_data


def _extract_adx_data(vwap_history, chart_times):
    """ADX 데이터 추출 및 시간 정렬"""
    adx_times = []
    adx_values = []
    
    # vwap_history를 시간 기준으로 딕셔너리로 변환
    vwap_data = {}
    for entry in vwap_history:
        timestamp_str = entry['timestamp']
        try:
            # SQLite datetime을 파싱 (UTC 시간으로 가정)
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # 로컬 타임으로 변환
            dt = dt.astimezone()
            vwap_data[dt] = entry
        except:
            # 다른 형식 시도
            try:
                # UTC 시간으로 가정하고 로컬 타임으로 변환
                dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc).astimezone()
                vwap_data[dt] = entry
            except:
                continue
    
    # 차트 시간 범위에 맞는 ADX 데이터만 추출
    if chart_times:
        chart_start = min(chart_times)
        chart_end = max(chart_times)
        
        for dt, entry in sorted(vwap_data.items()):
            # 차트 시간 범위 ±10분 내의 데이터만 사용하고 ADX가 있는 것만
            if (chart_start - timedelta(minutes=10) <= dt <= chart_end + timedelta(minutes=10) 
                and entry['adx'] is not None):
                adx_times.append(dt)
                adx_values.append(entry['adx'])
    
    return adx_times, adx_values


def _add_candlestick_chart(fig, times, opens, highs, lows, closes):
    """캔들스틱 차트 추가"""
    fig.add_trace(
        go.Candlestick(
            x=times,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name='OHLC',
            increasing_line_color='#26A69A',
            decreasing_line_color='#EF5350'
        ),
        row=1, col=1
    )


def _add_strategy_indicators(fig, state, indicator_data, chart_times):
    """전략별 보조 지표 추가 (캔들스틱 차트에 오버레이)"""
    # VWAP 지표 추가 (VWAP 전략인 경우)
    if state.strategy_type == "VWAP" and hasattr(state, 'vwap') and state.vwap > 0:
        _add_vwap_indicators(fig, state, indicator_data, chart_times)
    
    # ADX 지표 추가 (모든 전략에서 사용 - 캔들스틱 차트 우측 Y축에 오버레이)
    _add_adx_overlay(fig, state, indicator_data)


def _add_vwap_indicators(fig, state, indicator_data, chart_times):
    """VWAP 지표들 추가"""
    vwap_history = indicator_data.get('vwap_history')
    
    if vwap_history:
        # 히스토리 데이터를 차트 시간에 맞춰 정렬
        try:
            vwap_times, vwap_values, upper_values, lower_values = align_vwap_with_chart_times(
                chart_times, vwap_history
            )
            
            if vwap_values:
                # VWAP 라인
                fig.add_trace(
                    go.Scatter(
                        x=vwap_times,
                        y=vwap_values,
                        mode='lines',
                        name='VWAP',
                        line=dict(color='#F18F01', width=2, dash='dash')
                    ),
                    row=1, col=1
                )
                
                # 상단/하단 밴드
                if upper_values and lower_values:
                    fig.add_trace(
                        go.Scatter(
                            x=vwap_times,
                            y=upper_values,
                            mode='lines',
                            name='상단밴드',
                            line=dict(color='#E71D36', width=1, dash='dot'),
                            opacity=0.7
                        ),
                        row=1, col=1
                    )
                    
                    fig.add_trace(
                        go.Scatter(
                            x=vwap_times,
                            y=lower_values,
                            mode='lines',
                            name='하단밴드',
                            line=dict(color='#2D9D32', width=1, dash='dot'),
                            opacity=0.7,
                            fill='tonexty',
                            fillcolor='rgba(45, 157, 50, 0.1)'
                        ),
                        row=1, col=1
                    )
        except Exception as e:
            from utils.logger import log
            log.error(f"Error adding VWAP indicators: {e}")
    
    else:
        # 폴백: 현재 값으로 평평한 라인 (히스토리가 없는 경우)
        if chart_times and state.vwap > 0:
            vwap_line = [state.vwap] * len(chart_times)
            fig.add_trace(
                go.Scatter(
                    x=chart_times,
                    y=vwap_line,
                    mode='lines',
                    name='VWAP (현재)',
                    line=dict(color='#F18F01', width=2, dash='dash')
                ),
                row=1, col=1
            )


def _add_volume_chart(fig, times, volumes):
    """거래량 차트 추가"""
    fig.add_trace(
        go.Bar(
            x=times,
            y=volumes,
            name='거래량',
            marker_color='rgba(46, 134, 171, 0.6)'
        ),
        row=2, col=1
    )


def _add_adx_overlay(fig, state, indicator_data):
    """ADX 오버레이 추가 (캔들스틱 차트에 우측 Y축으로)"""
    adx_times = indicator_data.get('adx_times', [])
    adx_values = indicator_data.get('adx_values', [])
    
    try:
        if adx_values and adx_times:
            # ADX 라인 (우측 Y축 사용)
            fig.add_trace(
                go.Scatter(
                    x=adx_times,
                    y=adx_values,
                    mode='lines',
                    name='ADX',
                    line=dict(color='#2E86AB', width=1.5, dash='dot'),
                    opacity=0.8,
                    yaxis='y2'  # 우측 Y축 사용
                ),
                row=1, col=1
            )
            
            # 현재 ADX 값 강조 표시
            if hasattr(state, 'adx') and state.adx and adx_times:
                fig.add_trace(
                    go.Scatter(
                        x=[adx_times[-1]],
                        y=[state.adx],
                        mode='markers',
                        name='현재 ADX',
                        marker=dict(size=6, color='#2E86AB', symbol='circle'),
                        yaxis='y2'  # 우측 Y축 사용
                    ),
                    row=1, col=1
                )
            
            # 우측 Y축 설정 (ADX용)
            fig.update_layout(
                yaxis2=dict(
                    title="ADX",
                    overlaying='y',
                    side='right',
                    range=[0, max(50, max(adx_values) * 1.1)],
                    showgrid=False,
                    tickfont=dict(size=10),
                    titlefont=dict(size=12)
                )
            )
        else:
            # ADX 데이터가 없는 경우 현재값만 표시
            if hasattr(state, 'adx') and state.adx:
                fig.add_trace(
                    go.Scatter(
                        x=[pd.Timestamp.now()],
                        y=[state.adx],
                        mode='markers+text',
                        name='현재 ADX',
                        marker=dict(size=8, color='#2E86AB', symbol='circle'),
                        text=[f'ADX: {state.adx:.1f}'],
                        textposition='top center',
                        yaxis='y2'
                    ),
                    row=1, col=1
                )
                
                # 우측 Y축 설정
                fig.update_layout(
                    yaxis2=dict(
                        title="ADX",
                        overlaying='y',
                        side='right',
                        range=[0, 50],
                        showgrid=False,
                        tickfont=dict(size=10),
                        titlefont=dict(size=12)
                    )
                )
        
    except Exception as e:
        from utils.logger import log
        log.error(f"Error adding ADX overlay: {e}")


def _configure_chart_layout(fig, state, highs, lows):
    """차트 레이아웃 및 축 설정"""
    # 레이아웃 설정
    fig.update_layout(
        height=600,
        title_text=f"{state.strategy_type} 전략 - 캔들스틱 차트 (ADX 오버레이)",
        showlegend=True,
        xaxis_rangeslider_visible=False,
        template="plotly_white"
    )
    
    # X축 설정
    fig.update_xaxes(title_text="시간", row=2, col=1)
    
    # Y축 설정 - 캔들 데이터의 고가/저가를 기준으로 범위 설정
    all_highs = [h for h in highs if h > 0]
    all_lows = [l for l in lows if l > 0]
    
    if all_highs and all_lows:
        price_max = max(all_highs)
        price_min = min(all_lows)
        price_range = price_max - price_min
        y_margin = price_range * 0.05  # 5% 여백
        
        fig.update_yaxes(
            title_text="가격 ($)", 
            row=1, col=1,
            range=[price_min - y_margin, price_max + y_margin]
        )
    else:
        # 폴백: 현재 가격 주변으로 설정
        current_price = state.current_price
        fig.update_yaxes(
            title_text="가격 ($)", 
            row=1, col=1,
            range=[current_price * 0.99, current_price * 1.01]
        )
    
    fig.update_yaxes(title_text="거래량", row=2, col=1)

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
