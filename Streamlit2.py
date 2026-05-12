#!/usr/bin/env python
# coding: utf-8

# In[1]:


import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io
import platform
from datetime import datetime

# --- 页面配置 ---
st.set_page_config(page_title="客户结构可视化", layout="wide", page_icon="📦")

# --- 环境配置：解决中文字体乱码 ---
def set_chinese_font():
    """根据运行环境自动设置中文字体"""
    system_name = platform.system()
    if system_name == "Windows":
        # 本地 Windows 环境常用字体
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Tahoma']
    elif system_name == "Linux":
        # Streamlit Cloud 环境，需配合 packages.txt 安装 fonts-noto-cjk
        plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'DejaVu Sans']
    else:
        # Mac 环境
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Heiti TC']

    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

set_chinese_font()

# --- 默认客户映射 ---
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
        # 强制邮编列为字符串，防止 07111 变成 7111
        dtype_spec = {'收件邮编': str, '发件邮编': str}

        if file_ext == 'csv':
            df = pd.read_csv(uploaded_file, encoding='utf-8', dtype=dtype_spec)
        else:
            df = pd.read_excel(uploaded_file, dtype=dtype_spec)

        # 核心字段校验与转换
        time_col = '下单时间-北京时区(年-月-日)'
        if time_col in df.columns:
            df[time_col] = pd.to_datetime(df[time_col])

        if '货量' in df.columns:
            df['货量'] = pd.to_numeric(df['货量'], errors='coerce').fillna(0)

        return df
    except Exception as e:
        st.error(f"读取文件失败，请检查格式或编码: {e}")
        return None

def process_analysis(df, customer_mapping, zip_col):
    """处理聚合逻辑"""
    # 客户分类映射
    df['客户分类'] = df['客户'].apply(lambda x: customer_mapping.get(str(x), "其他客户"))

    # 1. 汇总分析 (饼图数据)
    summary = df.groupby('客户分类').agg({
        '货量': 'sum',
        '下单时间-北京时区(年-月-日)': ['min', 'max']
    }).reset_index()
    summary.columns = ['客户简称', '总货量', '最早发货时间', '最晚发货时间']

    total_qty = summary['总货量'].sum()
    summary['占比'] = (summary['总货量'] / total_qty * 100).round(2)

    # 2. 邮编明细分析
    # 容错：如果用户选的列名不在表里，给予提示
    if zip_col not in df.columns:
        st.error(f"表格中未找到列名: {zip_col}")
        return summary, pd.DataFrame()

    zip_analysis = df.groupby([zip_col, '客户分类'])['货量'].sum().reset_index()
    zip_total = zip_analysis.groupby(zip_col)['货量'].transform('sum')
    zip_analysis['货量百分比'] = (zip_analysis['货量'] / zip_total * 100).round(2).astype(str) + '%'

    return summary, zip_analysis

# --- UI 界面 ---
st.title("📦 客户结构可视化")

# 用户要求的说明文字
st.info(r"""**操作指引**：上传包含 “下单时间-北京时区(年-月-日)、收件/发件邮编、客户、货量” 字段的数据源。
系统将为您生成可视化饼图与明细报表。""")

with st.sidebar:
    st.header("⚙️ 配置中心")
    uploaded_file = st.file_uploader("上传数据源 (支持 CSV, XLSX)", type=['csv', 'xlsx', 'xls'])
    zip_mode = st.selectbox("分析维度 (Zip Code Mode)", ["收件邮编", "发件邮编"])

    st.divider()
    st.markdown("### 客户映射预览")
    st.json(DEFAULT_MAPPING)

if uploaded_file:
    df = load_data(uploaded_file)

    if df is not None:
        # 执行数据处理
        summary, zip_analysis = process_analysis(df, DEFAULT_MAPPING, zip_mode)

        # --- 数据可视化展示 ---
        col_left, col_right = st.columns([6, 4])

        with col_left:
            st.subheader("📊 客户货量分布图")
            if not summary.empty:
                fig, ax = plt.subplots(figsize=(10, 7), dpi=150)

                # 构造标签：简称 + 占比 + 首发日期
                labels = [
                    f"{row['客户简称']}\n({row['占比']}%)\n首:{row['最早发货时间'].strftime('%m-%d')}" 
                    for _, row in summary.iterrows()
                ]

                # 绘制饼图
                wedges, texts, autotexts = ax.pie(
                    summary['总货量'], 
                    labels=labels, 
                    autopct='%1.1f%%', 
                    startangle=140, 
                    colors=plt.cm.Paired.colors, 
                    shadow=False,
                    textprops={'fontsize': 9}
                )
                ax.set_title(f'客户货量占比及首发时间汇总 ({zip_mode})', fontsize=14, pad=20)

                st.pyplot(fig)

                # 图片下载
                img_buffer = io.BytesIO()
                fig.savefig(img_buffer, format="png", bbox_inches='tight')
                st.download_button(
                    label="🖼️ 下载可视化图表 (PNG)",
                    data=img_buffer.getvalue(),
                    file_name=f"GOFO_Analysis_{datetime.now().strftime('%m%d')}.png",
                    mime="image/png"
                )

        with col_right:
            st.subheader("📈 汇总统计预览")
            st.dataframe(
                summary.style.format({'总货量': '{:.0f}', '占比': '{:.2f}%'}),
                use_container_width=True,
                height=400
            )

            # Excel 下载
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                summary.to_excel(writer, sheet_name='客户汇总', index=False)
                zip_analysis.to_excel(writer, sheet_name=f'{zip_mode}明细', index=False)

            st.download_button(
                label="📄 下载完整 Excel 报表",
                data=excel_buffer.getvalue(),
                file_name=f"GOFO_Logistics_Report_{datetime.now().strftime('%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.divider()
        st.subheader(f"📍 {zip_mode} 维度明细")
        st.dataframe(zip_analysis, use_container_width=True)
else:
    st.warning("👈 请先在左侧边栏上传数据文件。")

# 底部版权声明
st.divider()
st.caption("最终解释权归 GOFO.INC 所有")


# In[ ]:




