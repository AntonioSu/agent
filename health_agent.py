import streamlit as st
import logging
import traceback
from datetime import datetime
from phi.agent import Agent
from phi.model.google import Gemini
from phi.model.openai import OpenAIChat
import argparse
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
# 尝试从 Streamlit secrets 读取 API 密钥，如果没有则从环境变量读取
try:
    api_key = st.secrets["api_keys"]["API_KEY"]
    logging.info(f"已成功从 secrets.toml 加载API密钥")
except (KeyError, FileNotFoundError):
    # 如果 secrets.toml 中没有，则尝试从环境变量读取
    api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.error(
            "请在 secrets.toml 中设置 API_KEY 或设置环境变量 API_KEY/OPENAI_API_KEY！"
        )
    else:
        logging.info(f"已从环境变量加载API密钥")

st.set_page_config(
    page_title="AI 健康与健身规划器",
    page_icon="🏋️‍♂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f0fff4;
        border: 1px solid #9ae6b4;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fffaf0;
        border: 1px solid #fbd38d;
    }
    div[data-testid="stExpander"] div[role="button"] p {
        font-size: 1.1rem;
        font-weight: 600;
    }
    </style>
""",
    unsafe_allow_html=True,
)


def display_dietary_plan(plan_content):
    with st.expander("📋 您的个性化饮食计划", expanded=True):
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### 🎯 为什么这个计划有效")
            st.info(plan_content.get("why_this_plan_works", "信息不可用"))
            st.markdown("### 🍽️ 膳食计划")
            st.write(plan_content.get("meal_plan", "计划不可用"))

        with col2:
            st.markdown("### ⚠️ 重要注意事项")
            considerations = plan_content.get("important_considerations", "").split(
                "\n"
            )
            for consideration in considerations:
                if consideration.strip():
                    st.warning(consideration)


def display_fitness_plan(plan_content):
    with st.expander("💪 您的个性化健身计划", expanded=True):
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### 🎯 目标")
            st.success(plan_content.get("goals", "未指定目标"))
            st.markdown("### 🏋️‍♂️ 锻炼日程")
            st.write(plan_content.get("routine", "日程不可用"))

        with col2:
            st.markdown("### 💡 专业提示")
            tips = plan_content.get("tips", "").split("\n")
            for tip in tips:
                if tip.strip():
                    st.info(tip)


def display_sidebar():
    with st.sidebar:
        st.header("🔑 模型配置")
        # 模型提供商选择
        model_provider = st.selectbox(
            "选择模型提供商",
            options=["Gemini", "OpenAI"],
            help="选择您要使用的 AI 模型提供商",
        )

        if model_provider == "Gemini":
            st.subheader("🤖 Gemini 配置")
            base_url = st.text_input(
                "API Base URL",
                value="https://aistudio.google.com/apikey",
                help="API URL",
            )
            api_key = st.text_input(
                "Gemini API 密钥", type="password", help="输入您的 Gemini API 密钥"
            )

            model_name = st.selectbox(
                "Gemini 模型",
                options=[
                    "gemini-2.5-flash-preview-05-20",
                    "gemini-1.5-pro",
                    "gemini-1.5-flash",
                    "gemini-pro",
                ],
                help="选择要使用的 Gemini 模型",
            )

            if not api_key:
                st.warning("⚠️ 请输入您的 Gemini API 密钥以继续")
                st.markdown(
                    "[在此处获取您的 API 密钥](https://aistudio.google.com/apikey)"
                )
                return None, None, None, None

        elif model_provider == "OpenAI":
            st.subheader("🤖 OpenAI 配置")
            api_key = st.text_input(
                "OpenAI API 密钥", type="password", help="输入您的 OpenAI API 密钥"
            )
            base_url = st.text_input(
                "API Base URL", value="https://api.openai.com/v1", help="API URL"
            )
            model_name = st.selectbox(
                "OpenAI 模型",
                options=[
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4-turbo",
                    "gpt-3.5-turbo",
                    "deepseek-v3",
                    "glm",
                ],
                help="选择要使用的 OpenAI 模型",
            )
            if model_name == "deepseek-v3":
                model_name = "deepseek-v3-241226-volces"
            elif model_name == "glm":
                model_name = "glm-4-flash"

            if not api_key:
                st.warning("⚠️ 请输入您的 OpenAI API 密钥以继续")
                st.markdown(
                    "[在此处获取您的 API 密钥](https://platform.openai.com/api-keys)"
                )
                return None, None, None, None

        st.success(f"✅ {model_provider} 配置完成！")
    return model_provider, model_name, base_url, api_key


def args_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_provider", type=str, default="Gemini")
    parser.add_argument(
        "--model_name", type=str, default="gemini-2.5-flash-preview-05-20"
    )
    parser.add_argument("--base_url", type=str, default="https://api.openai.com/v1")
    parser.add_argument("--api_key", type=str, default="EMPTY")
    parser.add_argument("--type", type=int, default=1, help="1: Gemini, 2: OpenAI")
    return parser.parse_args()


def main():
    # 应用启动日志
    startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"AI 健康与健身规划器启动 - 时间: {startup_time}")

    if "dietary_plan" not in st.session_state:
        st.session_state.dietary_plan = {}
        st.session_state.fitness_plan = {}
        st.session_state.qa_pairs = []
        st.session_state.plans_generated = False
        logging.info("会话状态初始化完成")

    st.title("🏋️‍♂️ AI 健康与健身规划器")
    st.markdown(
        """
        <div style='
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 15px;
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
            text-align: center;
            font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, sans-serif;
        '>
            <h3 style='
                margin: 0 0 1rem 0;
                font-size: 1.5rem;
                font-weight: 600;
                text-shadow: 0 2px 4px rgba(0,0,0,0.1);
            '>🎯 个性化健康规划助手</h3>
            <p style='
                margin: 0;
                font-size: 1.1rem;
                line-height: 1.6;
                opacity: 0.95;
                font-weight: 300;
            '>
                获取根据您的目标和偏好量身定制的个性化饮食和健身计划。<br>
                我们由人工智能驱动的系统会考虑您的独特情况，为您创建完美的计划。
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )
    args = args_parse()
    if args.type == 1:
        model_provider = "Gemini"
        model_name = args.model_name
        base_url = args.base_url
        # Use the global api_key from environment variable
        api_key_to_use = api_key
    else:
        model_provider, model_name, base_url, api_key_to_use = display_sidebar()
    logging.info(f"model_provider: {model_provider}")
    logging.info(f"model_name: {model_name}")
    logging.info(f"base_url: {base_url}")
    logging.info(f"api_key: {api_key_to_use}")
    # 初始化选定的模型
    model = None
    try:
        if model_provider == "Gemini":
            logging.info(f"开始初始化 Gemini 模型: {model_name}")
            model = Gemini(id=model_name, api_key=api_key_to_use)
            logging.info("Gemini 模型初始化成功")
        elif model_provider == "OpenAI":
            logging.info(f"开始初始化 OpenAI 兼容模型")
            logging.info(f"模型名称: {model_name}")
            logging.info(f"Base URL: {base_url}")
            logging.info(f"API Key 前缀: {api_key_to_use[:10]}...")

            st.info(f"正在初始化 OpenAI 兼容模型: {model_name}")
            st.info(f"使用 Base URL: {base_url}")

            # 清理 base_url（移除 @ 符号）
            clean_base_url = base_url.strip().replace("@", "")
            if not clean_base_url.endswith("/"):
                clean_base_url += "/"

            # 使用标准 OpenAIChat（兼容性修复已通过 deepseek_fix 模块自动应用）
            model = OpenAIChat(
                id=model_name,
                api_key=api_key_to_use,
                base_url=clean_base_url,
                max_tokens=2000,
                temperature=0.7,
            )
            logging.info("OpenAI 兼容模型初始化成功")

            # 添加 API 测试按钮
            if st.button("🧪 测试 API 连接", key="test_api"):
                with st.spinner("正在测试 API 连接..."):
                    try:
                        # 创建一个简单的测试 agent
                        test_agent = Agent(
                            name="测试助手",
                            model=model,
                            instructions=["简短回复测试消息"],
                        )
                        test_response = test_agent.run("Hello, this is a test.")

                        if test_response and hasattr(test_response, "content"):
                            st.success("✅ API 连接测试成功!")
                            st.info(f"测试响应: {test_response.content[:100]}...")
                        else:
                            st.error("❌ API 连接测试失败：响应为空")
                    except Exception as test_e:
                        st.error(f"❌ API 连接测试失败: {test_e}")

            st.info("正在验证模型配置...")

    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()

        # 详细日志记录
        logging.error(f"模型初始化失败 - 提供商: {model_provider}")
        logging.error(f"错误信息: {error_msg}")
        logging.error(f"完整堆栈跟踪:\n{error_traceback}")

        st.error(f"❌ 初始化 {model_provider} 模型时出错:")
        st.error(f"错误详情: {error_msg}")

        # 在界面上显示详细错误信息
        with st.expander("🔍 详细错误信息（用于调试）", expanded=False):
            st.code(error_traceback)

        # 提供针对性的解决建议
        if "400" in error_msg or "InvalidRequest" in error_msg:
            st.warning("**可能的解决方案:**")
            st.markdown(
                """
            - ✅ 检查 API Key 格式是否正确
            - ✅ 确认 Base URL 格式正确（不要包含 @ 符号）
            - ✅ 验证模型名称是否被 API 提供商支持
            - ✅ 确保 API Key 有足够的权限和余额
            """
            )
        elif "ModuleNotFoundError" in error_msg:
            st.warning("**依赖包缺失:**")
            st.markdown("请安装缺失的依赖包：`pip install -r requirements.txt`")
        return

    if not model:
        print(f"error model: {model}")
        st.error(f"❌ 无法初始化 {model_provider} 模型")
        return

    st.header("👤 您的个人资料")

    col1, col2 = st.columns(2)

    with col1:
        age = st.number_input(
            "年龄", min_value=18, max_value=100, step=1, help="输入您的年龄"
        )
        height = st.number_input(
            "身高 (cm)", min_value=150.0, max_value=250.0, step=0.1
        )
        activity_level = st.selectbox(
            "活动水平",
            options=["久坐", "轻度活跃", "中度活跃", "非常活跃", "极度活跃", "不运动"],
            help="选择您通常的活动水平",
        )
        dietary_preferences = st.selectbox(
            "饮食偏好",
            options=["素食", "荤素搭配", "生酮", "无麸质", "低碳水", "无乳制品"],
            help="选择您的饮食偏好",
        )

    with col2:
        weight = st.number_input("体重 (kg)", min_value=30.0, max_value=300.0, step=0.1)
        sex = st.selectbox("性别", options=["女性", "男性", "其他"])
        fitness_goals = st.selectbox(
            "健身目标",
            options=["减肥", "增肌", "耐力", "保持健康", "力量训练", "塑形"],
            help="您想实现什么目标？",
        )

    if st.button("🎯 生成我的个性化计划", use_container_width=True):
        with st.spinner(
            "正在为您创建完美的健康和健身日程，此过程需要2-3分钟哦，请耐心等待..."
        ):
            try:
                dietary_agent = Agent(
                    name="饮食专家",
                    model=model,
                    # 使用 system_prompt 而不是 instructions 和 role
                    system_prompt="""你是一位专业的饮食专家。请根据用户的个人信息提供个性化饮食建议：
                    - 考虑用户的输入，包括饮食限制和偏好
                    - 建议一天的详细膳食计划，包括早餐、午餐、晚餐和零食
                    - 简要解释为什么该计划适合用户的目标
                    - 注重建议的清晰性、连贯性和质量
                    请用中文回复。""",
                )

                fitness_agent = Agent(
                    name="健身专家",
                    model=model,
                    # 使用 system_prompt 而不是 instructions 和 role
                    system_prompt="""你是一位专业的健身专家。请根据用户的个人信息提供个性化健身建议：
                    - 提供根据用户目标量身定制的锻炼计划
                    - 包括热身、主要锻炼和冷却运动
                    - 解释每项推荐锻炼的好处
                    - 确保计划具有可操作性和详细性
                    请用中文回复。""",
                )
                logging.info(f"++++++++")
                user_profile = f"""
                年龄: {age}
                体重: {weight}kg
                身高: {height}cm
                性别: {sex}
                活动水平: {activity_level}
                饮食偏好: {dietary_preferences}
                健身目标: {fitness_goals}
                """
                logging.info(f"user_profile: {user_profile}")
                logging.info(f"++++++++")


                # 生成饮食计划
                st.info("🍽️ 正在生成个性化饮食计划...")
                dietary_plan_response = dietary_agent.run(user_profile)

                if not dietary_plan_response or not hasattr(
                    dietary_plan_response, "content"
                ):
                    raise Exception("饮食计划生成失败，API 响应为空")

                dietary_plan = {
                    "why_this_plan_works": "高蛋白、健康脂肪、适量碳水化合物和热量平衡",
                    "meal_plan": dietary_plan_response.content,
                    "important_considerations": """
                    - 补水：全天多喝水
                    - 电解质：监测钠、钾和镁的水平
                    - 纤维：通过蔬菜和水果确保摄入足量
                    - 倾听身体的声音：根据需要调整份量
                    """,
                }

                # 生成健身计划
                st.info("💪 正在生成个性化健身计划...")
                fitness_plan_response = fitness_agent.run(user_profile)

                if not fitness_plan_response or not hasattr(
                    fitness_plan_response, "content"
                ):
                    raise Exception("健身计划生成失败，API 响应为空")

                fitness_plan = {
                    "goals": "增强力量、提高耐力并保持整体健康",
                    "routine": fitness_plan_response.content,
                    "tips": """
                    - 定期跟踪您的进展
                    - 锻炼之间保证适当的休息
                    - 注重正确的姿势
                    - 坚持您的日常锻炼
                    """,
                }

                st.session_state.dietary_plan = dietary_plan
                st.session_state.fitness_plan = fitness_plan
                st.session_state.plans_generated = True
                st.session_state.qa_pairs = []

                display_dietary_plan(dietary_plan)
                display_fitness_plan(fitness_plan)
                logging.info("计划生成成功，已保存到会话状态")
            except Exception as e:
                error_msg = str(e)
                error_traceback = traceback.format_exc()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 详细日志记录
                logging.error(f"计划生成失败 - 时间: {timestamp}")
                logging.error(
                    f"用户配置: 年龄={age}, 体重={weight}, 身高={height}, 性别={sex}"
                )
                logging.error(f"错误信息: {error_msg}")
                logging.error(f"完整堆栈跟踪:\n{error_traceback}")

                st.error(f"❌ 生成计划时发生错误:")
                st.error(f"错误详情: {error_msg}")

                # 在界面上显示详细错误信息
                with st.expander("🔍 详细错误信息（用于调试）", expanded=False):
                    st.code(error_traceback)
                    st.markdown(f"**时间戳:** {timestamp}")
                    st.markdown(
                        f"**用户配置:** 年龄={age}, 体重={weight}, 身高={height}, 性别={sex}"
                    )

                # 根据错误类型提供具体的解决建议
                if "400" in error_msg or "InvalidRequest" in error_msg:
                    st.warning("**API 请求错误 - 可能的解决方案:**")
                    st.markdown(
                        """
                    1. **检查 API 配置:**
                       - API Key 格式: `sk-`开头的字符串
                       - Base URL: `https://api.openai.com/v1` (不要包含 @ 符号)
                       - 模型名称: `gpt-4o`
                    
                    2. **验证 API 服务:**
                       - 确认 API 服务可用
                       - 检查 API Key 是否有效且有足够余额
                       - 验证模型名称是否正确
                    
                    3. **网络连接:**
                       - 检查网络连接是否正常
                       - 确认防火墙没有阻止请求
                    """
                    )
                elif (
                    "timeout" in error_msg.lower() or "connection" in error_msg.lower()
                ):
                    st.warning("**网络连接问题 - 解决方案:**")
                    st.markdown(
                        "- 检查网络连接\n- 尝试重新运行\n- 确认 API 服务地址正确"
                    )
                else:
                    st.warning("**通用解决方案:**")
                    st.markdown(
                        "- 检查所有配置参数\n- 重新启动应用\n- 联系 API 提供商确认服务状态"
                    )

                # 记录详细错误到日志文件
                try:
                    with open("logs", "a", encoding="utf-8") as f:
                        f.write(f"\n[{timestamp}] 计划生成错误: {error_msg}\n")
                        f.write(f"堆栈跟踪: {error_traceback}\n")
                        f.write("-" * 50 + "\n")
                except Exception as log_error:
                    logging.error(f"写入日志文件失败: {log_error}")

    if st.session_state.plans_generated:
        st.header("❓ 对您的计划有疑问吗？")
        question_input = st.text_input("您想知道什么？")

        if st.button("获取答案"):
            if question_input:
                with st.spinner("正在为您寻找最佳答案..."):
                    dietary_plan = st.session_state.dietary_plan
                    fitness_plan = st.session_state.fitness_plan

                    context = f"饮食计划: {dietary_plan.get('meal_plan', '')}\n\n健身计划: {fitness_plan.get('routine', '')}"
                    full_context = f"{context}\n用户问题: {question_input}"

                    try:
                        agent = Agent(
                            model=model,
                            system_prompt="你是一位健康和健身专家。请根据提供的饮食和健身计划回答用户的问题。用中文回复。",
                        )
                        run_response = agent.run(full_context)

                        if hasattr(run_response, "content"):
                            answer = run_response.content
                        else:
                            answer = "抱歉，目前无法生成回应。"

                        st.session_state.qa_pairs.append((question_input, answer))
                    except Exception as e:
                        st.error(f"❌ 获取答案时发生错误: {e}")

        if st.session_state.qa_pairs:
            st.header("💬 问答历史")
            for question, answer in st.session_state.qa_pairs:
                st.markdown(f"**问:** {question}")
                st.markdown(f"**答:** {answer}")


if __name__ == "__main__":
    main()
