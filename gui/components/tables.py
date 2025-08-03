import streamlit as st
import pandas as pd
from datetime import datetime

def create_positions_table(positions):
    """활성 포지션 테이블 생성"""
    
    if not positions:
        st.info("활성 포지션이 없습니다.")
        return
    
    df = pd.DataFrame(positions)
    
    # 컬럼 이름 한글화
    column_mapping = {
        'order_id': '주문 ID',
        'symbol': '심볼',
        'side': '방향',
        'entry_price': '진입가',
        'quantity': '수량',
        'strategy_type': '전략',
        'vwap_at_entry': 'VWAP@진입',
        'timestamp': '시간'
    }
    
    # 존재하는 컬럼만 이름 변경
    existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_columns)
    
    # 시간 포맷팅
    if '시간' in df.columns:
        df['시간'] = pd.to_datetime(df['시간']).dt.strftime('%H:%M:%S')
    
    # 가격 포맷팅
    if '진입가' in df.columns:
        df['진입가'] = df['진입가'].apply(lambda x: f"${x:.2f}")
    
    if 'VWAP@진입' in df.columns:
        df['VWAP@진입'] = df['VWAP@진입'].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
    
    # 방향에 따라 색상 적용
    def highlight_side(val):
        if val == 'BUY':
            return 'background-color: rgba(0, 255, 0, 0.2)'
        elif val == 'SELL':
            return 'background-color: rgba(255, 0, 0, 0.2)'
        return ''
    
    if '방향' in df.columns:
        styled_df = df.style.applymap(highlight_side, subset=['방향'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

def create_trades_table(trades):
    """완료된 거래 테이블 생성"""
    
    if not trades:
        st.info("거래 내역이 없습니다.")
        return
    
    df = pd.DataFrame(trades)
    
    # 컬럼 이름 한글화
    column_mapping = {
        'order_id': '주문 ID',
        'symbol': '심볼',
        'side': '방향',
        'entry_price': '진입가',
        'exit_price': '청산가',
        'quantity': '수량',
        'pnl': '손익',
        'strategy_type': '전략',
        'exit_reason': '청산사유',
        'timestamp': '시간'
    }
    
    # 존재하는 컬럼만 이름 변경
    existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_columns)
    
    # 시간 포맷팅
    if '시간' in df.columns:
        df['시간'] = pd.to_datetime(df['시간']).dt.strftime('%m-%d %H:%M')
    
    # 가격 포맷팅
    if '진입가' in df.columns:
        df['진입가'] = df['진입가'].apply(lambda x: f"${x:.2f}")
    
    if '청산가' in df.columns:
        df['청산가'] = df['청산가'].apply(lambda x: f"${x:.2f}")
    
    # PnL 포맷팅 및 색상
    if '손익' in df.columns:
        df['손익_포맷'] = df['손익'].apply(lambda x: f"${x:+.2f}")
        
        def highlight_pnl(val):
            try:
                if float(val.replace('$', '').replace('+', '')) > 0:
                    return 'background-color: rgba(0, 255, 0, 0.3); color: green; font-weight: bold'
                elif float(val.replace('$', '').replace('+', '')) < 0:
                    return 'background-color: rgba(255, 0, 0, 0.3); color: red; font-weight: bold'
            except:
                pass
            return ''
        
        # 원본 손익 컬럼 제거하고 포맷된 컬럼 사용
        df = df.drop('손익', axis=1)
        df = df.rename(columns={'손익_포맷': '손익'})
        
        styled_df = df.style.applymap(highlight_pnl, subset=['손익'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

def create_statistics_table(stats):
    """통계 요약 테이블"""
    
    stats_data = {
        '항목': [
            '총 거래 수',
            '승리 거래',
            '승률',
            '총 손익',
            '평균 손익',
            '최대 이익',
            '최대 손실'
        ],
        '값': [
            f"{stats['total_trades']}회",
            f"{stats['winning_trades']}회",
            f"{stats['win_rate']:.1f}%",
            f"${stats['total_pnl']:+.2f}",
            f"${stats['avg_pnl']:+.2f}",
            f"${stats['max_pnl']:+.2f}",
            f"${stats['min_pnl']:+.2f}"
        ]
    }
    
    df = pd.DataFrame(stats_data)
    
    # 값에 따라 색상 적용
    def highlight_values(row):
        if '손익' in row['항목']:
            try:
                value = float(row['값'].replace('$', '').replace('+', ''))
                if value > 0:
                    return [''] + ['background-color: rgba(0, 255, 0, 0.2); color: green']
                elif value < 0:
                    return [''] + ['background-color: rgba(255, 0, 0, 0.2); color: red']
            except:
                pass
        elif '승률' in row['항목']:
            try:
                rate = float(row['값'].replace('%', ''))
                if rate >= 50:
                    return [''] + ['background-color: rgba(0, 255, 0, 0.2); color: green']
                else:
                    return [''] + ['background-color: rgba(255, 165, 0, 0.2); color: orange']
            except:
                pass
        return ['', '']
    
    styled_df = df.style.apply(highlight_values, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)