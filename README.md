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
在backend/.env位置创建.env文件
内容为：
```dotenv
# 大模型
## 聊天大模型
LLM_MODEL_ID="模型名称"
LLM_API_KEY="模型 apikey"
LLM_BASE_URL="模型请求地址"
## EMBEDDING模型
EMBEDDING_MODEL_ID="模型名称"
EMBEDDING_API_KEY="模型 apikey"
EMBEDDING_BASE_URL="模型请求地址"
# MCP 工具
## SERPAPI搜索工具
SERPAPI_API_KEY="serpapi 的调用 apikey"
```