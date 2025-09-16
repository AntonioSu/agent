import streamlit as st
import logging
import traceback
from datetime import datetime
from phi.agent import Agent
from phi.model.google import Gemini
from phi.model.openai import OpenAIChat
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
import asyncio

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
# 全局线程池将在主函数中初始化

# 获取API密钥的函数
def get_api_key():
    try:
        api_key = st.secrets["api_keys"]["API_KEY"]
        logging.info(f"已成功从 secrets.toml 加载API密钥")
        return api_key
    except (KeyError, FileNotFoundError):
        # 如果 secrets.toml 中没有，则尝试从环境变量读取
        api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logging.error(
                "请在 secrets.toml 中设置 API_KEY 或设置环境变量 API_KEY/OPENAI_API_KEY！"
            )
        else:
            logging.info(f"已从环境变量加载API密钥")
        return api_key

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


# 异步生成计划的函数
def generate_plan_async(user_profile, model_provider, model_name, base_url, api_key, plan_type):
    """异步生成饮食或健身计划"""
    try:
        # 初始化模型
        model = None
        if model_provider == "Gemini":
            model = Gemini(id=model_name, api_key=api_key)
        elif model_provider == "OpenAI":
            clean_base_url = base_url.strip().replace("@", "")
            if not clean_base_url.endswith("/"):
                clean_base_url += "/"
            model = OpenAIChat(
                id=model_name,
                api_key=api_key,
                base_url=clean_base_url,
                max_tokens=2000,
                temperature=0.7,
            )
        
        if plan_type == "dietary":
            agent = Agent(
                name="饮食专家",
                model=model,
                system_prompt="""你是一位专业的饮食专家。请根据用户的个人信息提供个性化饮食建议：
                - 考虑用户的输入，包括饮食限制和偏好
                - 建议一天的详细膳食计划，包括早餐、午餐、晚餐和零食
                - 简要解释为什么该计划适合用户的目标
                - 注重建议的清晰性、连贯性和质量
                请用中文回复。""",
            )
        else:  # fitness
            agent = Agent(
                name="健身专家",
                model=model,
                system_prompt="""你是一位专业的健身专家。请根据用户的个人信息提供个性化健身建议：
                - 提供根据用户目标量身定制的锻炼计划
                - 包括热身、主要锻炼和冷却运动
                - 解释每项推荐锻炼的好处
                - 确保计划具有可操作性和详细性
                请用中文回复。""",
            )
        
        response = agent.run(user_profile)
        
        if not response or not hasattr(response, "content"):
            return None
            
        return response.content
        
    except Exception as e:
        logging.error(f"生成{plan_type}计划时出错: {str(e)}")
        return None

# 初始化session state的函数
def init_session_state():
    """初始化用户会话状态"""
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    
    if "executor" not in st.session_state:
        st.session_state.executor = ThreadPoolExecutor(max_workers=10)
    
    if "dietary_plan" not in st.session_state:
        st.session_state.dietary_plan = {}
        st.session_state.fitness_plan = {}
        st.session_state.qa_pairs = []
        st.session_state.plans_generated = False
        st.session_state.generation_status = "idle"  # idle, generating, completed, error
        st.session_state.generation_progress = 0
        st.session_state.current_task = ""
        logging.info(f"用户 {st.session_state.user_id} 会话状态初始化完成")


def main():
    # 初始化会话状态
    init_session_state()
    
    # 应用启动日志
    startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"AI 健康与健身规划器启动 - 时间: {startup_time} - 用户: {st.session_state.user_id}")

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
    
    # 默认配置 - 优先使用环境变量
    default_api_key = get_api_key()
    
    # 如果有环境变量API密钥，默认使用Gemini，否则显示侧边栏配置
    if default_api_key:
        model_provider = "Gemini"
        model_name = "gemini-2.5-flash-preview-05-20"
        base_url = "https://aistudio.google.com/apikey"
        api_key_to_use = default_api_key
        
        # 在侧边栏显示当前配置
        with st.sidebar:
            st.header("🔑 当前配置")
            st.success(f"✅ 使用 {model_provider} 模型")
            st.info(f"模型: {model_name}")
            st.info("API密钥: 已从环境变量加载")
            
            # 允许用户切换到手动配置
            if st.button("🔧 手动配置模型"):
                st.session_state.manual_config = True
                st.rerun()
    else:
        st.session_state.manual_config = True
    
    # 如果需要手动配置或用户选择手动配置
    if st.session_state.get('manual_config', False):
        config_result = display_sidebar()
        if config_result[0] is None:  # 配置不完整
            return
        model_provider, model_name, base_url, api_key_to_use = config_result
    
    logging.info(f"用户 {st.session_state.user_id} - model_provider: {model_provider}")
    logging.info(f"用户 {st.session_state.user_id} - model_name: {model_name}")
    logging.info(f"用户 {st.session_state.user_id} - base_url: {base_url}")
    logging.info(f"用户 {st.session_state.user_id} - api_key: {api_key_to_use[:10] if api_key_to_use else 'None'}...")
    
    # 显示配置状态
    if model_provider and model_name and api_key_to_use:
        st.success(f"✅ 配置完成：{model_provider} - {model_name}")
    else:
        st.error("❌ 配置不完整，请检查API密钥和模型设置")
        return

    st.header("👤 您的个人资料")

    col1, col2 = st.columns(2)

    with col1:
        age = st.number_input(
            "年龄", min_value=10, max_value=100, step=1, value=25, help="输入您的年龄"
        )
        height = st.number_input(
            "身高 (cm)", min_value=120.0, max_value=250.0, step=0.1, value=170.0
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
        weight = st.number_input("体重 (kg)", min_value=30.0, max_value=300.0, step=0.1, value=70.0)
        sex = st.selectbox("性别", options=["女性", "男性", "其他"])
        fitness_goals = st.selectbox(
            "健身目标",
            options=["减肥", "增肌", "耐力", "保持健康", "力量训练", "塑形"],
            help="您想实现什么目标？",
        )

    # 显示生成状态
    if st.session_state.generation_status == "generating":
        progress_bar = st.progress(st.session_state.generation_progress)
        st.info(f"🔄 {st.session_state.current_task}")
        
        # 检查异步任务是否完成
        if "plan_futures" in st.session_state:
            dietary_future, fitness_future = st.session_state.plan_futures
            
            if dietary_future.done() and fitness_future.done():
                try:
                    dietary_content = dietary_future.result()
                    fitness_content = fitness_future.result()
                    
                    if dietary_content and fitness_content:
                        dietary_plan = {
                            "why_this_plan_works": "高蛋白、健康脂肪、适量碳水化合物和热量平衡",
                            "meal_plan": dietary_content,
                            "important_considerations": """
                            - 补水：全天多喝水
                            - 电解质：监测钠、钾和镁的水平
                            - 纤维：通过蔬菜和水果确保摄入足量
                            - 倾听身体的声音：根据需要调整份量
                            """,
                        }
                        
                        fitness_plan = {
                            "goals": "增强力量、提高耐力并保持整体健康",
                            "routine": fitness_content,
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
                        st.session_state.generation_status = "completed"
                        st.session_state.generation_progress = 100
                        st.session_state.current_task = "✅ 计划生成完成！"
                        
                        # 清理future对象
                        del st.session_state.plan_futures
                        
                        logging.info(f"用户 {st.session_state.user_id} 计划生成成功")
                        st.rerun()
                    else:
                        st.session_state.generation_status = "error"
                        st.error("❌ 计划生成失败，请重试")
                        if "plan_futures" in st.session_state:
                            del st.session_state.plan_futures
                        
                except Exception as e:
                    st.session_state.generation_status = "error"
                    st.error(f"❌ 生成计划时发生错误: {str(e)}")
                    logging.error(f"用户 {st.session_state.user_id} 计划生成失败: {str(e)}")
                    if "plan_futures" in st.session_state:
                        del st.session_state.plan_futures
            else:
                # 更新进度
                progress = 20
                if dietary_future.done():
                    progress += 40
                if fitness_future.done():
                    progress += 40
                st.session_state.generation_progress = progress
                
                # 自动刷新页面
                time.sleep(1)
                st.rerun()
    
    # 生成计划按钮
    if st.button("🎯 生成我的个性化计划", use_container_width=True, disabled=(st.session_state.generation_status == "generating")):
        try:
            user_profile = f"""
            年龄: {age}
            体重: {weight}kg
            身高: {height}cm
            性别: {sex}
            活动水平: {activity_level}
            饮食偏好: {dietary_preferences}
            健身目标: {fitness_goals}
            """
            
            logging.info(f"用户 {st.session_state.user_id} 开始生成计划")
            logging.info(f"用户资料: {user_profile}")
            
            # 设置生成状态
            st.session_state.generation_status = "generating"
            st.session_state.generation_progress = 10
            st.session_state.current_task = "🚀 正在启动计划生成..."
            st.session_state.qa_pairs = []
            
            # 异步提交任务
            executor = st.session_state.executor
            dietary_future = executor.submit(
                generate_plan_async, 
                user_profile, model_provider, model_name, base_url, api_key_to_use, "dietary"
            )
            fitness_future = executor.submit(
                generate_plan_async, 
                user_profile, model_provider, model_name, base_url, api_key_to_use, "fitness"
            )
            
            st.session_state.plan_futures = (dietary_future, fitness_future)
            st.session_state.current_task = "🍽️ 正在生成饮食计划和健身计划..."
            st.session_state.generation_progress = 20
            
            st.rerun()
            
        except Exception as e:
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 重置状态
            st.session_state.generation_status = "error"
            if "plan_futures" in st.session_state:
                del st.session_state.plan_futures

            # 详细日志记录
            logging.error(f"用户 {st.session_state.user_id} 计划生成失败 - 时间: {timestamp}")
            logging.error(f"用户配置: 年龄={age}, 体重={weight}, 身高={height}, 性别={sex}")
            logging.error(f"错误信息: {error_msg}")
            logging.error(f"完整堆栈跟踪:\n{error_traceback}")

            st.error(f"❌ 生成计划时发生错误:")
            st.error(f"错误详情: {error_msg}")

            # 在界面上显示详细错误信息
            with st.expander("🔍 详细错误信息（用于调试）", expanded=False):
                st.code(error_traceback)
                st.markdown(f"**时间戳:** {timestamp}")
                st.markdown(f"**用户配置:** 年龄={age}, 体重={weight}, 身高={height}, 性别={sex}")

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
            elif "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                st.warning("**网络连接问题 - 解决方案:**")
                st.markdown("- 检查网络连接\n- 尝试重新运行\n- 确认 API 服务地址正确")
            else:
                st.warning("**通用解决方案:**")
                st.markdown("- 检查所有配置参数\n- 重新启动应用\n- 联系 API 提供商确认服务状态")

            # 记录详细错误到日志文件
            try:
                with open("error_logs.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n[{timestamp}] 用户 {st.session_state.user_id} 计划生成错误: {error_msg}\n")
                    f.write(f"堆栈跟踪: {error_traceback}\n")
                    f.write("-" * 50 + "\n")
            except Exception as log_error:
                logging.error(f"写入日志文件失败: {log_error}")

    # 显示已生成的计划
    if st.session_state.plans_generated and st.session_state.generation_status == "completed":
        display_dietary_plan(st.session_state.dietary_plan)
        display_fitness_plan(st.session_state.fitness_plan)
        
        # 添加重新生成按钮
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔄 重新生成计划", use_container_width=True):
                # 重置状态
                st.session_state.plans_generated = False
                st.session_state.generation_status = "idle"
                st.session_state.generation_progress = 0
                st.session_state.current_task = ""
                st.session_state.dietary_plan = {}
                st.session_state.fitness_plan = {}
                st.session_state.qa_pairs = []
                if "plan_futures" in st.session_state:
                    del st.session_state.plan_futures
                st.rerun()

    if st.session_state.plans_generated:
        st.header("❓ 对您的计划有疑问吗？")
        question_input = st.text_input("您想知道什么？")

        if st.button("获取答案"):
            if question_input:
                try:
                    dietary_plan = st.session_state.dietary_plan
                    fitness_plan = st.session_state.fitness_plan

                    context = f"饮食计划: {dietary_plan.get('meal_plan', '')}\n\n健身计划: {fitness_plan.get('routine', '')}"
                    full_context = f"{context}\n用户问题: {question_input}"

                    # 初始化问答模型
                    qa_model = None
                    if model_provider == "Gemini":
                        qa_model = Gemini(id=model_name, api_key=api_key_to_use)
                    elif model_provider == "OpenAI":
                        clean_base_url = base_url.strip().replace("@", "")
                        if not clean_base_url.endswith("/"):
                            clean_base_url += "/"
                        qa_model = OpenAIChat(
                            id=model_name,
                            api_key=api_key_to_use,
                            base_url=clean_base_url,
                            max_tokens=1000,
                            temperature=0.7,
                        )

                    agent = Agent(
                        model=qa_model,
                        system_prompt="你是一位健康和健身专家。请根据提供的饮食和健身计划回答用户的问题。用中文回复。",
                    )
                    
                    with st.spinner("正在为您寻找最佳答案..."):
                        run_response = agent.run(full_context)

                        if hasattr(run_response, "content"):
                            answer = run_response.content
                        else:
                            answer = "抱歉，目前无法生成回应。"

                        st.session_state.qa_pairs.append((question_input, answer))
                        logging.info(f"用户 {st.session_state.user_id} 问答成功")
                        
                except Exception as e:
                    st.error(f"❌ 获取答案时发生错误: {e}")
                    logging.error(f"用户 {st.session_state.user_id} 问答失败: {str(e)}")

        if st.session_state.qa_pairs:
            st.header("💬 问答历史")
            for question, answer in st.session_state.qa_pairs:
                st.markdown(f"**问:** {question}")
                st.markdown(f"**答:** {answer}")


if __name__ == "__main__":
    main()
