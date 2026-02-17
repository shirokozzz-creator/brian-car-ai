import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def render_commute_battle():
    st.markdown("## ⚔️ 林口坡戰役：Hybrid vs. Gas")
    st.caption("場景：林口 ⇄ 松山機場 (往返 55km) | 去程下坡 (Glide) | 回程上坡 (Climb)")

    # --- 參數設定區 (Sidebar or Top) ---
    col1, col2 = st.columns(2)
    with col1:
        gas_price = st.number_input("目前 95 無鉛油價 (TWD/L)", value=31.5, step=0.1)
    with col2:
        commute_days = st.number_input("每月通勤天數", value=22, step=1)

    # --- 核心數據 (Hardcoded based on real-world analysis) ---
    # Prius 3 (1.8 Hybrid)
    p3_eff_down = 3.1 # L/100km
    p3_eff_up = 5.7   # L/100km
    p3_avg_kml = 22.73

    # Camry 2.4 (2.4 NA)
    c24_eff_down = 7.4  # L/100km (Est 13.5 km/L)
    c24_eff_up = 13.3   # L/100km (Est 7.5 km/L)
    c24_avg_kml = 9.63

    dist = 55.0

    # --- 計算邏輯 ---
    # 每日耗油量 (L)
    daily_fuel_p3 = dist / p3_avg_kml
    daily_fuel_c24 = dist / c24_avg_kml

    # 每日成本 (TWD)
    daily_cost_p3 = daily_fuel_p3 * gas_price
    daily_cost_c24 = daily_fuel_c24 * gas_price
    daily_diff = daily_cost_c24 - daily_cost_p3

    # --- 1. 每日成本視覺化 (Metric & Progress) ---
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Prius 3 每日油資", f"${daily_cost_p3:.0f}", delta="勝利", delta_color="normal")
    m2.metric("Camry 2.4 每日油資", f"${daily_cost_c24:.0f}", delta="-高耗能", delta_color="inverse")
    m3.metric("每日節省 (Daily Save)", f"${daily_diff:.0f}", "純利潤")

    # --- 2. 長期持有成本分析 (TCO Projection) ---
    years = 5
    months = years * 12
    
    # 建立數據框
    data = []
    accumulated_p3 = 0
    accumulated_c24 = 0
    accumulated_invest = 0 # Naval style: 複利效應
    
    for m in range(1, months + 1):
        monthly_save = daily_diff * commute_days
        accumulated_p3 += daily_cost_p3 * commute_days
        accumulated_c24 += daily_cost_c24 * commute_days
        
        # 假設省下的錢拿去投資 (年化 5% / 12)
        accumulated_invest = (accumulated_invest + monthly_save) * (1 + 0.05/12)
        
        data.append({
            "Month": m,
            "Prius 3 累積油資": accumulated_p3,
            "Camry 2.4 累積油資": accumulated_c24,
            "資金缺口 (Gap)": accumulated_c24 - accumulated_p3
        })

    df = pd.DataFrame(data)

    st.subheader(f"📊 {years} 年通勤成本累積")
    
    # 使用 Streamlit 原生圖表 (互動性較佳)
    st.line_chart(
        df, 
        x="Month", 
        y=["Prius 3 累積油資", "Camry 2.4 累積油資"],
        color=["#00CC96", "#EF553B"] # Green for Prius, Red for Camry
    )

    # --- 3. 結論與 Naval 觀點 ---
    total_diff = df.iloc[-1]["資金缺口 (Gap)"]
    invest_value = accumulated_invest

    st.info(f"""
    **💡 數據洞察 (Data Insight):**
    
    在 {years} 年的週期內，選擇 Prius 3 比 Camry 2.4 節省了 **${total_diff:,.0f} TWD**。
    
    **🚀 Naval 的槓桿思維：**
    如果你將每個月省下的油錢 ({daily_diff * commute_days:.0f} 元) 投入年化 5% 的指數基金，
    5 年後這筆資金將成長為 **${invest_value:,.0f} TWD**。
    
    這不只是省錢，這是**資本配置 (Capital Allocation)** 的勝利。
    """)

# 在主程式中呼叫
if __name__ == "__main__":
    render_commute_battle()
