import streamlit as st
import os
import json
import time
from ai_grader import AIGrader

# 设置页面标题和布局
st.set_page_config(
    page_title="AI智能阅卷系统",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    color: #1E88E5;
    text-align: center;
    margin-bottom: 0.5rem;
    font-family: "Microsoft YaHei", "微软雅黑", sans-serif;
}
.main-header-icon {
    font-size: 3rem;
    color: #1E88E5;
    margin-bottom: 0.5rem;
}
.sub-title {
    font-size: 1.1rem;
    color: #666;
    text-align: center;
    margin-bottom: 2rem;
    font-family: "Microsoft YaHei", "微软雅黑", sans-serif;
}
.decorative-line {
    height: 3px;
    background: linear-gradient(90deg, rgba(30,136,229,0), rgba(30,136,229,1), rgba(30,136,229,0));
    margin: 1rem auto;
    width: 200px;
}
.sub-header {
    font-size: 1.5rem;
    color: #424242;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.sub-header-icon {
    color: #1E88E5;
}
.result-card {
    padding: 1.5rem;
    border-radius: 10px;
    background-color: #f8f9fa;
    margin-bottom: 1rem;
    border-left: 5px solid #1E88E5;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.score-box {
    background-color: #e3f2fd;
    padding: 1rem;
    border-radius: 8px;
    text-align: center;
    margin: 0.5rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    transition: transform 0.2s;
}
.score-box:hover {
    transform: translateY(-2px);
}
.score-label {
    font-weight: bold;
    color: #424242;
}
.score-value {
    font-size: 2rem;
    color: #1E88E5;
    font-weight: bold;
}
.level-indicator {
    font-size: 1.5rem;
    font-weight: bold;
    text-align: center;
    padding: 0.5rem;
    border-radius: 8px;
    margin: 0.5rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.level-0 {
    background-color: #eeeeee;
    color: #616161;
}
.level-1 {
    background-color: #ffcdd2;
    color: #c62828;
}
.level-2 {
    background-color: #fff9c4;
    color: #f57f17;
}
.level-3 {
    background-color: #c8e6c9;
    color: #2e7d32;
}
.level-4 {
    background-color: #bbdefb;
    color: #1565c0;
}
.level-5 {
    background-color: #e1bee7;
    color: #6a1b9a;
}
.comment-box {
    background-color: white;
    padding: 1.5rem;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    margin-top: 1rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.stButton>button {
    background-color: #1E88E5;
    color: white;
    font-weight: bold;
    padding: 0.5rem 2rem;
    border-radius: 8px;
    border: none;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
}
.stButton>button:hover {
    background-color: #1565C0;
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}
</style>
""", unsafe_allow_html=True)

# 创建AIGrader实例
@st.cache(allow_output_mutation=True)
def load_grader():
    return AIGrader()

grader = load_grader()
# 显示页面标题
# st.markdown('<div style="text-align: center;"><span class="main-header-icon">📝</span></div>', unsafe_allow_html=True)
st.markdown('<h1 class="main-header">LLM驱动的智能阅卷系统</h1>', unsafe_allow_html=True)
st.markdown('<div class="decorative-line"></div>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">基于大模型的智能评分系统 | 专业 · 高效 · 准确</p>', unsafe_allow_html=True)

# 创建侧边栏配置
with st.sidebar:
    st.markdown('### ⚙️ 系统设置')
    
    st.markdown('#### 🤖 评分模型配置')
    model_option = st.selectbox(
        "评分模型",
        ["deepseek-chat"],
        index=0
    )
    
    temperature = st.slider(
        "输出多样性 (Temperature)",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.1,
        help="值越低，输出结果越确定；值越高，结果越多样化"
    )
    
    st.markdown("---")
    
    st.markdown('#### 📚 评分组件库信息')
    component_types = [f"- {ctype}" for ctype in grader.question_types]
    st.markdown("**可用题目类型：**")
    st.markdown("\n".join(component_types))
    
    st.markdown("---")
    
    st.markdown("### ℹ️ 关于")
    st.markdown("""
    本系统基于评分组件库构建，通过分析大量人工评分样本提取评分规则和标准，实现自动化评分。
    
    **特点：**
    - 🎯 准确的评分标准
    - 🔄 实时的反馈
    - 📊 详细的分析报告
    """)

# 主界面
col1, col2 = st.columns([3, 4])

with col1:
    st.markdown('<h2 class="sub-header">📋 试题信息</h2>', unsafe_allow_html=True)
    
    # 题目输入
    title = st.text_area(
        "试题题目",
        height=100,
        placeholder="请输入完整的试题题目..."
    )
    
    # 预设题目类型选择
    use_predefined_type = st.checkbox("✨ 指定题目类型（可选）", value=False)
    
    if use_predefined_type:
        predefined_type = st.selectbox(
            "选择题目类型",
            grader.question_types,
            index=0
        )
    else:
        predefined_type = None
    
    # 答案输入
    st.markdown('<h2 class="sub-header">📝 学生答案</h2>', unsafe_allow_html=True)
    
    answer = st.text_area(
        "粘贴学生答案",
        height=300,
        placeholder="请输入或粘贴学生答案内容..."
    )
    
    # 评分按钮
    if st.button("🚀 开始评分", type="primary", use_container_width=True):
        if not title or not answer:
            st.error("请填写完整的题目和答案内容！")
        else:
            with st.spinner("AI正在评分中，请稍候..."):
                # 保存评分配置到会话状态
                st.session_state.grading_config = {
                    "model": model_option,
                    "temperature": temperature
                }
                
                # 打印调试信息
                print(f"使用评分模型: {model_option}, 温度参数: {temperature}")
                
                # 调用评分函数
                result = grader.grade_answer(
                    title=title, 
                    answer=answer,
                    question_type=predefined_type,
                    model=model_option,
                    temperature=temperature
                )
                
                # 保存结果到会话状态
                st.session_state.result = result
                st.session_state.title = title
                st.session_state.answer = answer
                
            st.success("评分完成！")

with col2:
    st.markdown('<h2 class="sub-header">评分结果</h2>', unsafe_allow_html=True)
    
    # 显示评分结果
    if 'result' in st.session_state:
        result = st.session_state.result
        
        # 打印调试信息
        print("评分结果:")
        print(f"- 题目类型: {result.get('题目类型', '未知')}")
        print(f"- 内容分数: {result.get('内容分数', 0)}")
        print(f"- 语言分数: {result.get('语言分数', 0)}")
        print(f"- 组织分数: {result.get('组织分数', 0)}")
        print(f"- 等级: {result.get('等级', '未知')}")
        
        with st.container():
            # st.markdown('<div class="result-card">', unsafe_allow_html=True)
            
            # 题目类型
            st.markdown(f"**题目类型：** {result.get('题目类型', '未知')}")
            
            # 分数栏
            score_cols = st.columns(4)
            
            with score_cols[0]:
                st.markdown(f"""
                <div class="score-box">
                    <div class="score-label">内容分数</div>
                    <div class="score-value">{result.get('内容分数', 0)}/6</div>
                </div>
                """, unsafe_allow_html=True)
                
            with score_cols[1]:
                st.markdown(f"""
                <div class="score-box">
                    <div class="score-label">语言分数</div>
                    <div class="score-value">{result.get('语言分数', 0)}/6</div>
                </div>
                """, unsafe_allow_html=True)
                
            with score_cols[2]:
                st.markdown(f"""
                <div class="score-box">
                    <div class="score-label">组织分数</div>
                    <div class="score-value">{result.get('组织分数', 0)}/6</div>
                </div>
                """, unsafe_allow_html=True)
                
            with score_cols[3]:
                level = result.get('等级', '未知')
                level_num = '0'
                if level == 'Unclassified':
                    level_num = '0'
                elif 'LEVEL 1' in level or 'LEVEL1' in level:
                    level_num = '1'
                elif 'LEVEL 2' in level or 'LEVEL2' in level:
                    level_num = '2'
                elif 'LEVEL 3' in level or 'LEVEL3' in level:
                    level_num = '3'
                elif 'LEVEL 4' in level or 'LEVEL4' in level:
                    level_num = '4'
                elif 'LEVEL 5' in level or 'LEVEL5' in level:
                    level_num = '5'
                
                st.markdown(f"""
                <div class="level-indicator level-{level_num}">
                    {level}
                </div>
                """, unsafe_allow_html=True)
            
            # 评语
            st.markdown("**评语：**")
            comment_text = result.get('评语', '无评语').replace('\n', '<br>')
            st.markdown(f"""
            <div class="comment-box">
                {comment_text}
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 显示题目和答案信息
            with st.expander("查看题目和答案原文"):
                st.markdown("**题目：**")
                st.markdown(st.session_state.title)
                st.markdown("**答案：**")
                st.markdown(st.session_state.answer)
    else:
        st.info("请在左侧查看题目和答案，然后点击「开始评分」按钮获取评分结果。")
        
        # 示例展示
        with st.expander("查看评分示例"):
            st.markdown("""
            ### 示例评分结果
            
            **题目类型：** 应用文(信函)
            
            **评分：**
            - 内容分数：4/6
            - 语言分数：5/6
            - 组织分数：4/6
            - 等级：LEVEL 3
            
            **评语：**
            信件基本完成了写作任务，包含了邀请函的主要信息：活动主题、时间、地点等。语言表达总体流畅，但存在一些不够正式的表达。结构大体合理，但开头和结尾的处理可以更加符合邀请函的格式要求。建议加强对正式邀请函格式的学习，特别是开头的称呼和结尾的客套语部分。
            """)

# 页脚
st.markdown("---")
