#!/usr/bin/env python
# coding: utf-8

# In[1]:


import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io
from datetime import datetime

# 设置页面配置
st.set_page_config(page_title="物流客户货量分析工具", layout="wide")

# --- 环境配置 ---
# Streamlit 云端通常自带常用中文字体，如果乱码，Streamlit 环境建议使用系统默认或通过 st.pyplot 渲染
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans'] 
plt.rcParams['axes.unicode_minus'] = False

# --- 默认客户映射 (用户可根据实际情况在界面微调或保持代码硬编码) ---
DEFAULT_MAPPING = {
    "GOFO-TEMU": "TM", "GOFO-TUBT": "TM",
    "YunExpress-LAX": "YT", "SHEIN-D2D": "SN",
    "Style Link Logistics LLC": "SN", "SHEIN-INDY": "SN",
    "Tiktokinc": "TK", "Tiktokinc4PL": "TK",
    "TiktokincGS": "TK", "TiktokincCBT全段": "TK",
}

def load_data(uploaded_file):
    """支持多格式读取，并强制保留邮编的 0 前缀"""
    try:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        if file_ext == 'csv':
            # 关键点：强制邮编列为字符串，防止 07111 变成 7111
            df = pd.read_csv(uploaded_file, encoding='utf-8', dtype={'收件邮编': str, '发件邮编': str})
        else:
            df = pd.read_excel(uploaded_file, dtype={'收件邮编': str, '发件邮编': str})

        # 时间转换
        time_col = '下单时间-北京时区(年-月-日)'
        if time_col in df.columns:
            df[time_col] = pd.to_datetime(df[time_col])

        # 货量数值化
        if '货量' in df.columns:
            df['货量'] = pd.to_numeric(df['货量'], errors='coerce').fillna(0)

        return df
    except Exception as e:
        st.error(f"读取文件失败: {e}")
        return None

def process_analysis(df, customer_mapping, zip_col):
    """处理逻辑，返回结果对象"""
    # 映射客户
    df['客户分类'] = df['客户'].apply(lambda x: customer_mapping.get(x, "其他客户"))

    # 1. 汇总分析 (Sheet1 / 饼图)
    summary = df.groupby('客户分类').agg({
        '货量': 'sum',
        '下单时间-北京时区(年-月-日)': ['min', 'max']
    }).reset_index()
    summary.columns = ['客户简称', '总货量', '最早发货时间', '最晚发货时间']

    total_qty = summary['总货量'].sum()
    summary['占比'] = (summary['总货量'] / total_qty * 100).round(2)

    # 2. 邮编维度 (Sheet2)
    zip_analysis = df.groupby([zip_col, '客户分类'])['货量'].sum().reset_index()
    zip_total = zip_analysis.groupby(zip_col)['货量'].transform('sum')
    zip_analysis['内部分数'] = (zip_analysis['货量'] / zip_total)
    zip_analysis['货量百分比'] = (zip_analysis['内部分数'] * 100).round(2).astype(str) + '%'

    return summary, zip_analysis

# --- Streamlit UI 界面 ---
st.title("📦 物流数据自动化分析系统")
st.markdown("上传原始数据，系统将自动进行客户分类、邮编分析并生成可视化报表。")

with st.sidebar:
    st.header("控制面板")
    uploaded_file = st.file_uploader("选择数据源 (CSV 或 Excel)", type=['csv', 'xlsx', 'xls'])
    zip_mode = st.selectbox("分析维度", ["收件邮编", "发件邮编"])

    st.divider()
    st.info("提示：邮编列将自动保留前导零（如 07111）。")

if uploaded_file:
    df = load_data(uploaded_file)

    if df is not None:
        # 执行分析
        summary, zip_analysis = process_analysis(df, DEFAULT_MAPPING, zip_mode)

        # --- 展示区 ---
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("📊 客户货量占比")
            fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
            labels = [f"{r['客户简称']}\n({r['占比']}%)\n首:{r['最早发货时间'].strftime('%m-%d')}" 
                      for _, r in summary.iterrows()]

            # 去除阴影 (shadow=False)
            ax.pie(summary['总货量'], labels=labels, autopct='%1.1f%%', 
                   startangle=140, colors=plt.cm.Paired.colors, shadow=False)
            ax.set_title(f'各客户货量占比及首发汇总 ({zip_mode})', fontsize=14)
            st.pyplot(fig)

            # 准备图片下载按钮
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format="png", bbox_inches='tight')
            st.download_button(
                label="🖼️ 下载占比图 (PNG)",
                data=img_buffer.getvalue(),
                file_name=f"客户占比图_{datetime.now().strftime('%Y%m%d')}.png",
                mime="image/png"
            )

        with col2:
            st.subheader("📈 汇总统计预览")
            st.dataframe(summary.style.format({'总货量': '{:.0f}', '占比': '{:.2f}%'}), use_container_width=True)

            # 准备 Excel 下载按钮
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                summary.to_excel(writer, sheet_name='客户汇总分析', index=False)
                zip_analysis.to_excel(writer, sheet_name=f'{zip_mode}明细', index=False)

            st.download_button(
                label="📄 下载 Excel 完整分析报表",
                data=output.getvalue(),
                file_name=f"物流分析报告_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.divider()
        st.subheader("📍 邮编维度明细预览")
        st.dataframe(zip_analysis, height=400)
else:
    st.warning("请在侧边栏上传 CSV 或 Excel 文件以开始分析。")


# In[ ]:




