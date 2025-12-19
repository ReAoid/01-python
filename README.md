# 01-python

## 克隆仓库
```shell
git clone https://github.com/ReAoid/01-python.git
```

## 安装依赖
```shell
conda create -n 01-python python=3.12
conda activate 01-python
cd backend
pip install -r requirements.txt
```

## 系统环境变量
请确保设置以下环境变量，或者配置 `core_config.json` 文件：
```bash
# 大模型
## 聊天大模型
export LLM__DEFAULT_MODEL="模型名称"
export API__LLM_API_KEY="模型 apikey"
export API__LLM_BASE_URL="模型请求地址"

# MCP 工具
## SERPAPI搜索工具
export API__SERPAPI_API_KEY="serpapi 的调用 apikey"
```

# 待执行计划
- [x] 初始化项目
- [x] 创建 core 文件夹
- [x] 构建基础 mcp 框架
- [x] 构建基础 memory 框架
- [ ] 构建基础 chat 流程（Session 管理）
- [ ] 构建基础 agent 框架
- [ ] 热切换Session（文本模型根据轮数+Token来自动切换，语音和视频根据连接时间例如60s来自动切换）切换时会总结历史记录