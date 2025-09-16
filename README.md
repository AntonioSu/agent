# AI 健康与健身规划器 - 部署说明

## 修改内容

本次修改主要解决了多用户并发访问的问题，确保应用能支持多人同时使用而不需要等待。

### 主要改进

1. **移除命令行参数依赖**
   - 删除了`argparse`相关代码
   - 改为使用环境变量或默认配置
   - 支持通过侧边栏手动配置模型

2. **实现异步计划生成**
   - 使用`ThreadPoolExecutor`进行异步任务处理
   - 饮食计划和健身计划并行生成
   - 实时进度跟踪和状态显示

3. **优化用户会话管理**
   - 每个用户分配唯一ID
   - 独立的session state管理
   - 用户数据完全隔离

4. **增强用户体验**
   - 实时进度条显示
   - 异步状态跟踪
   - 重新生成计划功能
   - 更好的错误处理和提示

### 部署要求

- **启动命令**: `streamlit run health_agent.py`
- **不需要额外参数**: 应用会自动使用环境变量或提供配置界面
- **API密钥配置**: 
  - 环境变量: `API_KEY` 或 `OPENAI_API_KEY`
  - 或在应用界面手动配置

### 并发支持

- ✅ 支持多用户同时访问
- ✅ 每个用户独立的会话状态
- ✅ 异步任务处理，不会阻塞其他用户
- ✅ 实时进度跟踪
- ✅ 用户数据隔离

### 技术实现

1. **异步任务处理**
   ```python
   # 使用ThreadPoolExecutor进行异步处理
   executor = ThreadPoolExecutor(max_workers=10)
   future = executor.submit(generate_plan_async, ...)
   ```

2. **会话状态管理**
   ```python
   # 每个用户独立的ID和状态
   st.session_state.user_id = str(uuid.uuid4())
   st.session_state.generation_status = "idle"
   ```

3. **实时状态更新**
   ```python
   # 自动刷新机制
   if st.session_state.generation_status == "generating":
       st.rerun()
   ```

### 使用方法

1. 启动应用：
   ```bash
   streamlit run health_agent.py
   ```

2. 访问应用（通常是 http://localhost:8501）

3. 如果有环境变量API密钥，应用会自动使用Gemini模型

4. 如果没有，会显示配置界面让用户手动配置

5. 多个用户可以同时访问，互不干扰

### 注意事项

- 确保安装了所有依赖包：`pip install -r requirements.txt`
- API密钥可以通过环境变量或界面配置
- 应用支持Gemini和OpenAI兼容的模型
- 每个用户的数据完全独立，不会相互影响

## 测试建议

1. 打开多个浏览器窗口或标签页
2. 同时在不同窗口中生成计划
3. 验证每个用户的进度和结果独立
4. 测试重新生成和问答功能
