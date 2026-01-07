import os
import json
import time
from openai import OpenAI
import pandas as pd
import re 

API_KEY = "sk-7de92824eafb4f4eb90a23b767608f69"
BASE_URL = "https://api.deepseek.com/v1" 

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)
# 定义评分组件库的路径
COMPONENT_LIBRARY_PATH = "评分组件库/评分组件库_全量.json"
print("AI客户端和组件库路径已配置。")

class AIGrader:
    def __init__(self):
        """
        初始化AIGrader实例，加载评分组件库。
        """
        self.component_library = self._load_component_library()
        self.question_types = self.component_library.get("题目类型", [])
        self.components = self.component_library.get("组件库", {})

        if not self.question_types or not self.components:
            print("警告: 评分组件库加载不完整或为空。请检查路径和文件内容。")
            print(f"  - 加载的题目类型: {self.question_types}")
            print(f"  - 加载的组件数量: {len(self.components)}")
        else:
            print(f"评分组件库加载成功，包含 {len(self.question_types)} 种题目类型。")

    def _load_component_library(self):
        """
        从指定路径加载JSON格式的评分组件库。
        包含错误处理机制。
        """
        try:
            with open(COMPONENT_LIBRARY_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"成功从 {COMPONENT_LIBRARY_PATH} 加载评分组件库数据。")
                return data
        except FileNotFoundError:
            print(f"错误: 评分组件库文件 {COMPONENT_LIBRARY_PATH} 未找到。")
            return {"题目类型": [], "组件库": {}}
        except json.JSONDecodeError:
            print(f"错误: 评分组件库文件 {COMPONENT_LIBRARY_PATH} JSON格式无效。")
            return {"题目类型": [], "组件库": {}}
        except Exception as e:
            print(f"加载评分组件库时发生未知错误: {e}")
            return {"题目类型": [], "组件库": {}}

    # 实例化AIGrader并测试组件库加载：
    # grader_instance = AIGrader()
    # 执行后，您应该能看到组件库加载成功的消息，或者相应的错误提示。
    def query_llm(self, messages, model="deepseek-chat", temperature=0.2, max_retries=3, retry_delay=2):
        print(f"准备调用LLM (模型: {model}, 温度: {temperature})...")
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    messages=messages,
                    model=model,  # 确保这个模型名称是你的API Key有权限访问的
                    temperature=temperature,
                    stream=False,
                )
                content = response.choices[0].message.content
                print(f"LLM调用成功 (尝试 {attempt + 1}/{max_retries}).")
                return content
            except Exception as e:
                print(f"LLM调用错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    print("LLM调用达到最大重试次数，返回错误信息。")
                    return f"API调用失败: {str(e)}"  # 返回错误信息而不是抛出，方便上层统一处理

    def identify_question_type(self, title, answer=None, model="deepseek-chat", temperature=0.2):
        """
        识别题目类型。
        参数:
        - title (str): 题目描述。
        - answer (str, optional): 学生答案，辅助判断，当前版本prompt未显式使用，可按需加入。
        - model (str): 使用的LLM模型。
        - temperature (float): LLM温度参数。
        返回:
        - str: 识别出的题目类型（简体中文），如果失败则返回默认类型。
        """
        # 预定义的题目类型列表，应与评分组件库中的 '题目类型' 一致
        # self.question_types 是在 __init__ 中从组件库加载的

        system_prompt = "你是一个专业的教育评估专家，擅长分析各类题目的类型。请以JSON格式回应，使用简体中文。"
        user_prompt_template = f"""
请分析以下题目描述的类型。
题目描述: {title}

请仅返回一个最匹配的题目类型，从以下类型中选择一个:
{json.dumps(self.question_types, ensure_ascii=False)}

请以以下JSON格式返回结果:
{{
    "question_type": "这里填写题目类型（使用简体中文）"
}}

只返回JSON格式，不要包含其他解释。
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt_template}
        ]

        response_text = self.query_llm(messages, model=model, temperature=temperature).strip()

        # 繁体到简体的简单映射 (仅包含题目类型中可能出现的字)
        # 实际应用中可以考虑引入更完备的简繁转换库
        t2s_dict = {
            '其': '其', '他': '他', '博': '博', '客': '客', '文': '文', '章': '章',
            '分': '分', '析': '析', '题': '题', '创': '创', '意': '意', '写': '写', '作': '作',
            '应': '应', '用': '用', '信': '信', '函': '函', '报': '报', '告': '告',
            '新': '新', '闻': '闻', '稿': '稿', '演': '演', '讲': '讲', '评': '评', '论': '论',
            '记': '记', '叙': '叙', '说': '说', '明': '明', '类': '类', '型': '型'
        }

        def t2s(text):
            """简单的繁体转简体函数"""
            if not isinstance(text, str):  # 确保输入是字符串
                return ""
            for t_char, s_char in t2s_dict.items():
                text = text.replace(t_char, s_char)
            return text

        extracted_type = ""
        try:
            # 尝试从响应中提取JSON部分
            # LLM 可能返回被markdown代码块包裹的JSON，或者带有额外文本
            match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if not match:
                match = re.search(r'(\{.*?\})', response_text, re.DOTALL)

            if match:
                json_str = match.group(1)
                result = json.loads(json_str)
                extracted_type = result.get("question_type", "")
            else:  # 如果没有找到花括号包裹的JSON，直接尝试解析整个响应
                try:
                    result = json.loads(response_text)
                    extracted_type = result.get("question_type", "")
                except json.JSONDecodeError:
                    print(f"题目类型识别：响应非标准JSON，尝试直接从文本中匹配。响应: {response_text[:200]}...")
                    # 如果JSON解析失败，直接在原始文本中（转换为简体后）查找类型名称
                    # 这种方式容错性更强，但不如JSON精确
                    pass  # 下面的逻辑会处理 extracted_type 为空的情况

        except json.JSONDecodeError as e:
            print(f"题目类型识别：JSON解析失败 - {e}。响应: {response_text[:200]}...")
        except Exception as e:  # 其他可能的错误
            print(f"题目类型识别：发生意外错误 - {e}。响应: {response_text[:200]}...")

        # 转换为简体中文
        question_type_simple = t2s(extracted_type.strip())

        # 验证并返回类型
        if question_type_simple and question_type_simple in self.question_types:
            print(f"识别出的题目类型 (来自JSON, 简体): {question_type_simple}")
            return question_type_simple

        # 如果JSON中的类型无效或为空，尝试从整个响应文本中（简体化后）进行模糊匹配
        print(f"题目类型识别：JSON提取类型 '{question_type_simple}' 无效或未在库中，尝试文本模糊匹配...")
        response_simple_full = t2s(response_text)
        for qt_candidate in self.question_types:
            if qt_candidate in response_simple_full:  # qt_candidate本身就是简体
                print(f"识别出的题目类型 (来自文本模糊匹配, 简体): {qt_candidate}")
                return qt_candidate

        default_type = self.question_types[0] if self.question_types else "未知类型"
        print(f"题目类型识别：无法可靠识别类型，返回默认类型: {default_type}")
        return default_type

    # 测试 identify_question_type 方法的示例代码：
    # grader_instance = AIGrader() # 确保已实例化并加载了组件库
    # example_title = "请写一篇关于环境保护的议论文。"
    # identified_type = grader_instance.identify_question_type(example_title)
    # print(f"测试 - 题目: '{example_title}', 识别类型: {identified_type}")

    # example_title_2 = "Write a letter to your friend telling him about your summer vacation."
    # identified_type_2 = grader_instance.identify_question_type(example_title_2)
    # print(f"测试 - 题目: '{example_title_2}', 识别类型: {identified_type_2}")
    def check_ai_content(self, answer, model="deepseek-chat", temperature=0.2):
        """
        检测学生答案是否为AI生成的内容或乱写的内容。
        参数:
        - answer (str): 学生提交的答案。
        - model (str): 使用的LLM模型。
        - temperature (float): LLM温度参数。
        返回:
        - dict: 包含检测结果的字典。
        """
        system_prompt = """你是一个AI内容检测专家。你的任务是判断学生作业是否为AI生成或乱写的内容。请谨慎判断，避免过度严格。

判断标准（请综合考虑多个特征，不要仅凭单一特征判断）：

1. AI生成内容特征（需要同时满足多个特征才判定为AI）：
   - 完全没有语法错误和表达不自然
   - 大段文字过于完美流畅
   - 使用了超出学生水平的专业词汇
   - 内容极其全面但缺乏具体个人经历
   - 所有段落转换都过于完美
   - 完全看不出个人写作风格
   - 回答过于模板化或制式化

2. 乱写内容特征（需要有明显的多个特征）：
   - 大量明显的语法错误
   - 文章结构完全混乱
   - 内容与题目要求完全无关
   - 多处明显的逻辑矛盾
   - 大段文字重复或毫无意义
   - 完全无法理解作者表达的意思

3. 真实学生作文特征（符合以下特征即可判定为真实作文）：
   - 有个人观点和真实例子
   - 存在合理的语法错误
   - 有清晰的思路发展过程
   - 词汇使用符合学生水平
   - 有具体的生活经验描述
   - 段落间有适当的转换
   - 文章有个人风格特色
   - 内容虽不完美但真实自然

重要提示：
1. 宁可错放也不可错判，如有疑虑应判定为真实作文
2. 学生可能会参考范文，但只要有个人改写痕迹就不应判为AI
3. 轻微的语法错误和表达不完美是正常现象
4. 需要特别注意学生的年级水平，不同年级的判断标准应有所不同

请严格按照以下格式返回，确保是合法的JSON：
{
    "is_ai_or_nonsense": false,
    "is_nonsense": false,
    "confidence": 0.85,
    "reason": "这是一个示例理由",
    "feedback": "这是给学生的建议"
}

格式要求：
1. 必须完全按照上述JSON格式输出
2. 不要添加任何额外的文字、符号或空行
3. is_ai_or_nonsense和is_nonsense必须是布尔值(true/false)，不能带引号
4. confidence必须是0到1之间的数值，不能带引号
5. reason和feedback必须是字符串，必须带引号
6. 所有字段名必须完全匹配，不能更改
7. 确保所有引号都是英文双引号(")，不能用中文引号
8. 字段之间使用英文逗号分隔
9. 最外层必须用大括号包裹
"""
        # 为避免prompt过长和token限制，只取答案的前2000字符进行分析
        # 如果答案很长，可以考虑分块或者更智能的摘要方法
        user_prompt_content = f"""请分析以下学生答案并返回JSON格式结果：

{answer[:2000]}{"..." if len(answer) > 2000 else ""}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt_content}
        ]

        response_text = self.query_llm(messages, model=model, temperature=temperature)

        default_result = {
            "is_ai_or_nonsense": False,
            "is_nonsense": False,
            "confidence": 0,  # 默认低置信度
            "reason": "无法解析AI内容检测结果，预设为非AI/非乱写内容。",
            "feedback": "系统AI内容检测模块未能成功解析响应，请学生继续努力独立完成作业。"
        }

        try:
            # 清理响应文本，移除可能的markdown代码块标记和"json"前缀
            cleaned_response = response_text.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[len('```json'):].strip()
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[len('```'):].strip()
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-len('```')].strip()

            # 尝试直接解析清理后的响应
            try:
                result = json.loads(cleaned_response)
            except json.JSONDecodeError:
                # 如果直接解析失败，尝试从原始文本中提取更宽松的JSON部分
                print(f"AI内容检测：直接解析失败，尝试提取JSON。响应: {response_text[:200]}...")
                match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    result = json.loads(json_str)
                else:
                    raise ValueError("在响应中无法找到有效的JSON结构。")

            # 严格验证JSON结构和类型
            if not isinstance(result.get("is_ai_or_nonsense"), bool):
                raise ValueError("'is_ai_or_nonsense' 字段必须是布尔值。")
            if not isinstance(result.get("is_nonsense"), bool):
                raise ValueError("'is_nonsense' 字段必须是布尔值。")
            if not (isinstance(result.get("confidence"), (int, float)) and \
                    0 <= result.get("confidence") <= 1):
                raise ValueError("'confidence' 字段必须是0到1之间的数值。")
            if not isinstance(result.get("reason"), str):
                raise ValueError("'reason' 字段必须是字符串。")
            if not isinstance(result.get("feedback"), str):
                raise ValueError("'feedback' 字段必须是字符串。")

            print("AI内容检测成功。")
            return result

        except (json.JSONDecodeError, ValueError) as e:
            print(f"AI内容检测结果解析或验证失败: {e}")
            print(f"原始响应内容 (前200字符): {response_text[:200]}...")
            return default_result
        except Exception as e:  # 其他未知错误
            print(f"AI内容检测时发生未知错误: {e}")
            print(f"原始响应内容 (前200字符): {response_text[:200]}...")
            return default_result

    def grade_answer(self, title, answer, question_type=None, model="deepseek-chat", temperature=0.2):
        """
        对学生答案进行评分，并生成评语。
        参数:
        - title (str): 题目。
        - answer (str): 学生答案。
        - question_type (str, optional): 题目类型，如果提供则跳过类型识别。
        - model (str): 使用的LLM模型。
        - temperature (float): LLM温度参数。
        返回:
        - dict: 包含分数、等级、评语和题目类型的字典。
        """
        print(f"开始对题目 \"{title[:50]}...\" 的答案进行评分...")

        # 1. AI内容检测
        ai_check_result = self.check_ai_content(answer, model=model, temperature=temperature)

        # 阈值可以根据实际效果调整
        ai_threshold = 0.85
        if ai_check_result.get("is_ai_or_nonsense", False) and \
                ai_check_result.get("confidence", 0) >= ai_threshold:

            reason = ai_check_result.get("reason", "AI检测模块判定内容可能非原创或无效。")
            is_nonsense = ai_check_result.get("is_nonsense", False)

            if is_nonsense:
                comment = (f"AI Detection: {reason}\n"
                           "1. 同学，我建议你先仔细阅读题目要求，理解题目的重点和目的。可以先列出大纲，整理思路，再用自己的话表达。\n"
                           "2. 内容不予置评。Your work cannot be graded due to its nature.")
            else:  # AI generated
                comment = (f"AI Detection: {reason}\n"
                           "1. 请同学尽量尝试自己写作，才有机会运用上课技巧及句式。同学可以参考AI范文，再自己套用笔记句式，但绝对不是照抄AI！\n"
                           "2. 内容不予置评。Your work cannot be graded as it appears to be largely AI-generated.")

            print("AI内容检测判定为AI生成或乱写，直接返回0分。")
            return {
                "评语": comment,
                "内容分数": 0, "语言分数": 0, "组织分数": 0,
                "等级": "Unclassified",
                "题目类型": question_type if question_type else self.identify_question_type(title, answer, model=model,
                                                                                            temperature=temperature),
                # 尝试获取类型
                "ai_detection": {
                    "is_ai_content": not is_nonsense,
                    "is_nonsense": is_nonsense,
                    "reason": ai_check_result.get("reason"),
                    "feedback": ai_check_result.get("feedback")
                }
            }

        # 2. 识别题目类型 (如果未提供)
        if not question_type:
            question_type = self.identify_question_type(title, answer, model=model, temperature=temperature)
        print(f"用于评分的题目类型: {question_type}")

        # 3. 获取评分组件
        scoring_component = self.components.get(question_type)
        if not scoring_component:
            print(f"警告: 未找到题目类型 '{question_type}' 对应的评分组件。")
            return {
                "评语": f"无法对类型为 '{question_type}' 的题目进行评分：未找到相应的评分组件。",
                "内容分数": 0, "语言分数": 0, "组织分数": 0,
                "等级": "Unclassified", "题目类型": question_type
            }

        # 4. 构建评分提示词
        system_prompt_grading = """你是一个专业的教育评估专家，以下是你的评分任务指南：

1. 评分维度及范围：
   - 内容分数：0-6分，评估内容的深度、准确性、相关性和完整性。
   - 语言分数：0-6分，评估语言运用的准确性、流畅度、词汇丰富性和表达效果。
   - 组织分数：0-6分，评估文章结构的合理性、逻辑的清晰度和段落的连贯性。

2. 评语风格要求（极其重要）：
   - 评语使用中文
   - 不需要刻意解释英文术语，视为自然用法。
   - 不建议使用括号来标注英文，除非是特定的引用。
   - 评语语气需专业且具建设性，模仿资深教师的口吻。
   - 避免使用过于口语化或网络化的表达，也避免纯粹的AI式总结性词语（如"总而言之"、"综上所述"等应融入教师口吻）。

3. 输出格式：
   必须严格按照以下JSON格式输出，包含所有指定字段：
   {{
       "评语": "（此处填写符合上述评语风格要求的评语）",
       "内容分数": (0-6之间的整数或小数),
       "语言分数": (0-6之间的整数或小数),
       "组织分数": (0-6之间的整数或小数),
       "等级": "（根据分数和评分等级逻辑自动判断，例如LEVEL 1, LEVEL 2, ..., LEVEL 5, 或 Unclassified）"
   }}
   所有分数应为数值型。等级为字符串。

记住：你的核心任务是模拟一位经验丰富的老师进行评分和书写评语。评语风格是首要的，必须地道自然。
"""
        answer_snippet = answer[:2500] + ("..." if len(answer) > 2500 else "")
        user_prompt_grading_template = f"""
请根据以下信息，对提供的学生答案进行评分：

题目：{title}
学生答案 (部分内容，注意分析整体表现)：
{answer_snippet}

当前正在使用的题目类型："{question_type}"
该类型的评分标准如下：
内容标准：{json.dumps(scoring_component.get("评分标准", {}).get("内容", []), ensure_ascii=False)}
语言标准：{json.dumps(scoring_component.get("评分标准", {}).get("语言", []), ensure_ascii=False)}
组织标准：{json.dumps(scoring_component.get("评分标准", {}).get("组织", []), ensure_ascii=False)}

评分等级逻辑参考 (你需要根据实际打出的三维分数，从这些逻辑中推断出最合适的等级)：
{json.dumps(scoring_component.get("评分等级逻辑", []), ensure_ascii=False)}

常见强项关键词参考 (可在评语中酌情使用，但不要生硬套用)：
{json.dumps(scoring_component.get("常见强项关键词", []), ensure_ascii=False)}

常见弱项关键词参考 (可在评语中酌情指出，但不要生硬套用)：
{json.dumps(scoring_component.get("常见弱项关键词", []), ensure_ascii=False)}

评语模板参考 (仅为风格和结构参考，内容需根据实际答案生成，避免直接复制模板中的占位符)：
{json.dumps(scoring_component.get("评语模板", []), ensure_ascii=False)}

特殊等级说明：
- Unclassified：通常在三项维度分数均为0时使用（例如，内容完全离题、AI代写被初步过滤后仍需标记等）。
- LEVEL 5：通常在三项维度分数均接近或达到满分6分时使用，代表卓越表现。

请严格按照指定的JSON格式返回你的评分结果和具有教师风格的中文评语。
"""
        # 截取答案，避免过长
        answer_snippet = answer[:2500] + ("..." if len(answer) > 2500 else "")

        messages_grading = [
            {"role": "system", "content": system_prompt_grading},
            {"role": "user", "content": user_prompt_grading_template}
        ]

        # 5. 调用LLM获取评分结果
        response_grading = self.query_llm(messages_grading, model=model, temperature=temperature)
        print(f"评分API原始响应 (前100字符): {response_grading[:100]}...")

        # 6. 解析和处理评分结果
        default_grading_result = {
            "评语": "评分处理失败：无法解析来自LLM的评分结果。",
            "内容分数": 0, "语言分数": 0, "组织分数": 0,
            "等级": "Unclassified", "题目类型": question_type,
            "原始响应": response_grading  # 包含原始响应便于调试
        }

        try:
            # 尝试提取和解析JSON
            match = re.search(r'```json\s*(\{.*?\})\s*```', response_grading, re.DOTALL)
            if not match:
                match = re.search(r'(\{.*?\})', response_grading, re.DOTALL)

            if match:
                json_str = match.group(1)
                result = json.loads(json_str)
                print("评分JSON解析成功。")
            else:
                try:  # 如果没有markdown块，尝试直接解析
                    result = json.loads(response_grading)
                    print("评分JSON直接解析成功。")
                except json.JSONDecodeError:
                    raise ValueError("在评分响应中无法找到或解析JSON结构。")

            # 标准化和验证字段
            standardized_result = {}
            field_mapping = {
                '评语': '评语', 'comment': '评语', '评语': '评语',
                '内容分数': '内容分数', 'content_score': '内容分数', '内容分数': '内容分数',
                '语言分数': '语言分数', 'language_score': '语言分数', '语言分数': '语言分数',
                '组织分数': '组织分数', 'organization_score': '组织分数', '组织分数': '组织分数',
                '等级': '等级', 'level': '等级', '等级': '等级'
            }

            valid_result = True
            for raw_key, value in result.items():
                std_key = field_mapping.get(raw_key.lower(), raw_key)  # 尝试小写匹配
                if not std_key in field_mapping.values() and not std_key in result:  # 处理LLM可能返回非预期字段名
                    std_key = field_mapping.get(raw_key, raw_key)

                if std_key in ['内容分数', '语言分数', '组织分数']:
                    try:
                        score = float(value)
                        if not (0 <= score <= 6):
                            print(f"警告: 分数 {std_key} ({score}) 超出0-6范围，将修正。")
                            score = max(0, min(6, score))
                        standardized_result[std_key] = score
                    except ValueError:
                        print(f"错误: 分数 {std_key} ({value}) 不是有效数值。")
                        standardized_result[std_key] = 0  # 设为0
                        valid_result = False
                elif std_key == '评语':
                    if not isinstance(value, str):
                        print(f"错误: 评语不是字符串。")
                        standardized_result[std_key] = "评语格式错误"
                        valid_result = False
                    else:
                        standardized_result[std_key] = value
                elif std_key == '等级':
                    if not isinstance(value, str) or not value.startswith("LEVEL") and value != "Unclassified":
                        print(f"警告: 等级 '{value}' 格式不规范。将尝试基于分数重新推断。")
                        # 等级将在后续基于分数推断，这里暂存或忽略LLM给的等级
                    standardized_result[std_key] = value  # 暂存，后续可能覆盖
                else:  # 保留其他可能的字段
                    standardized_result[std_key] = value

            if not valid_result:  # 如果分数解析等出现问题，可能需要返回错误
                print("评分结果中存在字段错误，可能影响准确性。")

            # 确保核心分数键存在
            for core_key in ['内容分数', '语言分数', '组织分数']:
                if core_key not in standardized_result:
                    print(f"警告: 核心分数 '{core_key}' 未在LLM响应中找到，设为0。")
                    standardized_result[core_key] = 0

            # 根据分数重新判断等级（如果LLM未提供或提供不规范）
            # 注意：这里的等级判断逻辑应该与评分组件库中的 `评分等级逻辑` 相匹配
            # 这是一个简化的兜底逻辑，实际项目中应调用一个辅助函数来精确匹配组件库中的等级规则
            c_score = standardized_result.get('内容分数', 0)
            l_score = standardized_result.get('语言分数', 0)
            o_score = standardized_result.get('组织分数', 0)

            current_grade_from_llm = standardized_result.get('等级', "")
            if not current_grade_from_llm or not (
                    current_grade_from_llm.startswith("LEVEL") or current_grade_from_llm == "Unclassified"):
                if c_score == 0 and l_score == 0 and o_score == 0:
                    standardized_result['等级'] = "Unclassified"
                elif c_score >= 5.5 and l_score >= 5.5 and o_score >= 5.5:  # 示例高级别
                    standardized_result['等级'] = "LEVEL 5"
                elif c_score >= 4 and l_score >= 4 and o_score >= 4:  # 示例中等级
                    standardized_result['等级'] = "LEVEL 4"
                elif c_score >= 2.5 and l_score >= 2.5 and o_score >= 2.5:
                    standardized_result['等级'] = "LEVEL 3"
                elif c_score >= 1 and l_score >= 1 and o_score >= 1:
                    standardized_result['等级'] = "LEVEL 2"
                else:
                    standardized_result['等级'] = "LEVEL 1"  # 示例低级别
                print(f"根据分数重新推断等级为: {standardized_result['等级']}")
            else:
                print(f"使用LLM提供的等级: {current_grade_from_llm}")

            standardized_result["题目类型"] = question_type
            # 将AI检测模块的原始信息也加入最终结果，方便追溯
            standardized_result["ai_detection_details"] = ai_check_result
            return standardized_result

        except (json.JSONDecodeError, ValueError) as e:
            print(f"评分结果JSON解析或验证失败: {e}")
            print(f"原始评分响应 (前200字符): {response_grading[:200]}...")
            default_grading_result["原始响应"] = response_grading  # 更新原始响应
            return default_grading_result
        except Exception as e:
            print(f"评分时发生未知错误: {e}")
            print(f"原始评分响应 (前200字符): {response_grading[:200]}...")
            default_grading_result["原始响应"] = response_grading  # 更新原始响应
            return default_grading_result