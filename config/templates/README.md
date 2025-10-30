# MineContext Configuration Templates

这个目录包含了为不同场景优化的配置模板。选择最适合你的情况的模板，复制到 `config/user/config.yaml`，然后根据需要进行修改。

## 📋 可用的模板

### 1. **ollama.yaml** - 本地 Ollama（推荐用于开发）
**最适合：** 本地开发、隐私优先、零成本

```bash
cp config/templates/ollama.yaml config/user/config.yaml
```

**特点：**
- ✅ 完全免费、本地运行
- ✅ 不需要API Key
- ✅ 最大隐私（无数据上传）
- ⚠️ 需要足够的本地计算资源
- ⚠️ 可能比云服务慢

**前置条件：**
```bash
# 安装 Ollama
ollama serve

# 在另一个终端拉取模型
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

**关键参数：**
- VLM: `qwen2.5:14b` (可改为其他模型)
- Embedding: `nomic-embed-text` (dimensions=768)

---

### 2. **openai.yaml** - OpenAI（推荐用于生产）
**最适合：** 生产环境、最佳质量、无需本地资源

```bash
cp config/templates/openai.yaml config/user/config.yaml
echo "LLM_API_KEY=sk-your-api-key" > .env
```

**特点：**
- ✅ 最高质量的模型
- ✅ 完全托管，无需本地资源
- ✅ 快速、可靠、持续更新
- ⚠️ 需要付费API
- ⚠️ 数据发送到云端

**前置条件：**
- OpenAI API Key（从 https://platform.openai.com/api-keys 获取）

**关键参数：**
- VLM: `gpt-4o` (可选: gpt-4-turbo, gpt-3.5-turbo)
- Embedding: `text-embedding-3-large` (dimensions=3072)

**成本参考：** 
- gpt-4o: ~$0.015 per 1K input tokens
- text-embedding-3-large: ~$0.13 per 1M tokens

---

### 3. **doubao.yaml** - Doubao / 火山引擎
**最适合：** 中国用户、本地化服务、性价比

```bash
cp config/templates/doubao.yaml config/user/config.yaml
echo "LLM_API_KEY=your-doubao-api-key" > .env
```

**特点：**
- ✅ 本地化支持，适合中文
- ✅ 相对低成本
- ✅ 数据合规性
- ⚠️ 需要付费API

**前置条件：**
- Doubao API Key（从 https://console.volcengine.com 获取）

**关键参数：**
- VLM: `doubao-seed-1-6-flash-250828`
- Embedding: `doubao-embedding` (dimensions=1024)

---

### 4. **hybrid.yaml** - 混合模式（推荐！）⭐
**最适合：** 生产环境、最佳性价比、隐私 + 质量平衡

```bash
cp config/templates/hybrid.yaml config/user/config.yaml
echo "LLM_API_KEY=sk-your-openai-api-key" > .env
ollama serve (in one terminal)
ollama pull nomic-embed-text (in another terminal)
```

**特点：**
- ✅ 最佳成本-质量-隐私平衡
- ✅ OpenAI GPT-4 的高质量理解
- ✅ Ollama 本地免费嵌入
- ✅ 嵌入数据本地保存，隐私更好
- ✅ 成本比全云更低

**前置条件：**
- OpenAI API Key (仅用于VLM)
- Ollama 本地运行 (仅用于嵌入)

**关键参数：**
- VLM: `gpt-4o` (来自 OpenAI)
- Embedding: `nomic-embed-text` (来自 Ollama, dimensions=768)

**成本对比：**
```
纯本地 (Ollama)        | 完全免费  | ✅ 低质量，但足够用
纯云端 (OpenAI)        | 较高      | ✅ 最高质量
混合 (本模板) ⭐        | 较低      | ✅ 优秀质量 + 隐私
```

---

### 5. **production.yaml** - 生产部署
**最适合：** 企业级部署、高可用、完整监控

```bash
cp config/templates/production.yaml config/user/config.yaml
# 配置所有环境变量和安全参数
```

**特点：**
- ✅ 生产级配置
- ✅ 完整监控和日志
- ✅ 安全加固
- ✅ 性能优化
- ✅ 生产部署检查清单

**关键特性：**
- 增强的日志和监控
- 安全验证和API密钥
- 性能调优（多工作进程）
- 健康检查和指标
- 备份和故障恢复

---

## 🚀 快速启动指南

### 场景1：我想快速试用（本地）
```bash
# 1. 选择 Ollama 模板
cp config/templates/ollama.yaml config/user/config.yaml

# 2. 启动 Ollama
ollama serve

# 3. 在另一个终端启动应用
python -m opencontext
```

### 场景2：我想用生产级质量（付费）
```bash
# 1. 选择 OpenAI 或混合模板
cp config/templates/hybrid.yaml config/user/config.yaml  # 推荐
# 或
cp config/templates/openai.yaml config/user/config.yaml

# 2. 配置 API Key
echo "LLM_API_KEY=sk-your-api-key" > .env

# 3. 如果用混合模式，启动 Ollama
ollama serve

# 4. 启动应用
python -m opencontext
```

### 场景3：我在中国，用 Doubao
```bash
# 1. 选择 Doubao 模板
cp config/templates/doubao.yaml config/user/config.yaml

# 2. 配置 API Key
echo "LLM_API_KEY=your-doubao-api-key" > .env

# 3. 启动应用
python -m opencontext
```

### 场景4：我要部署到生产环境
```bash
# 1. 选择生产模板
cp config/templates/production.yaml config/user/config.yaml

# 2. 修改所有配置参数（域名、路径、安全等）
vim config/user/config.yaml

# 3. 设置所有环境变量
# 编辑 .env 文件
vim .env

# 4. 检查部署清单（见 production.yaml 最后）

# 5. 启动应用
python -m opencontext
```

---

## ⚠️ 重要提示

### Embedding Dimensions（关键参数！）
每个嵌入模型都有特定的维度，**必须正确设置**，否则系统会崩溃！

常见维度值：
```yaml
# Ollama 模型
nomic-embed-text: 768
mxbai-embed-large: 1024
bge-m3: 1024
all-minilm: 384

# OpenAI 模型
text-embedding-3-small: 1536
text-embedding-3-large: 3072

# Doubao
doubao-embedding: 1024
```

### API Key 安全
- ✅ **永远不要**在代码中提交 API Key
- ✅ **永远不要**在 Git 中提交 `.env` 文件
- ✅ 使用环境变量存储敏感信息
- ✅ 使用 `.env` 文件本地管理（git忽略）

---

## 📖 配置修改指南

选择模板后，您可能需要修改以下参数：

### VLM 配置
```yaml
vlm_model:
  provider: "ollama"          # 或 openai, doubao
  model: "qwen2.5:14b"        # 改为您的模型
  base_url: "http://..."      # API 地址
  api_key: "${LLM_API_KEY}"   # 或留空
```

### Embedding 配置
```yaml
embedding_model:
  provider: "ollama"          # 或 openai, doubao
  model: "nomic-embed-text"   # 改为您的模型
  dimensions: 768             # ⚠️ 必须正确！
  base_url: "http://..."      # API 地址
  api_key: "${LLM_API_KEY}"   # 或留空
```

### 语言和首选项
```yaml
preferences:
  language: "zh"              # 或 "en"
  theme: "light"              # 或 "dark"
```

---

## 🆘 故障排除

### 问题：找不到配置文件
```
解决: 确保你已经将模板复制到 config/user/config.yaml
$ cp config/templates/[template].yaml config/user/config.yaml
```

### 问题：API Key 错误
```
解决: 检查 .env 文件中的 LLM_API_KEY
$ cat .env
$ echo "LLM_API_KEY=sk-your-correct-key" > .env
```

### 问题：嵌入维度不匹配
```
解决: 检查 embedding_model.dimensions 是否与您使用的模型匹配
# 查看配置
$ grep dimensions config/user/config.yaml
```

### 问题：连接到 Ollama 失败
```
解决: 确保 Ollama 在运行
$ ollama serve (in one terminal)

# 或检查地址是否正确
$ curl http://localhost:11434/api/tags
```

---

## 📞 更多帮助

- 详细配置指南：见 `docs/LLM_CONFIGURATION_GUIDE.md`
- 环境变量配置：见 `docs/ENV_CONFIGURATION.md`
- 完整配置分析：见 `CONFIG_MANAGEMENT_ANALYSIS.md`

---

**选择适合你的模板，立即开始！** 🚀
