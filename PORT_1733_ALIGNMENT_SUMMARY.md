# Backend Port 1733 Alignment - Configuration Consistency Fix

## 问题背景 (Problem Background)

用户报告前后端通信存在问题：
- 后端默认应该运行在1733端口，但后来改成了8008端口
- 屏幕截图无法正常显示
- 无法正常生成总结
- 前端跳过了VLM + embedding模型配置验证
- 配置分散在多个文件中，存在不一致性

## 问题分析 (Root Cause Analysis)

### 端口配置不一致
通过代码审查发现多处端口配置不一致：
1. **前端 axiosConfig.ts**: 默认端口设置为 8008 ❌
2. **前端 electron.vite.config.ts**: 默认端口设置为 8000 ❌
3. **后端 backend.ts**: 启动端口为 1733 ✅
4. **后端 opencontext.py**: 默认端口为 1733 ✅
5. **配置文件 defaults.yaml**: 端口为 1733 ✅
6. **.env.example**: 默认端口设置为 8000 ❌

### 通信失败原因
- 前端默认连接到 8008 或 8000 端口
- 后端实际运行在 1733 端口
- 导致前端无法连接到后端，屏幕截图上传失败，无法获取生成的总结

## 修复方案 (Solution)

### 1. 统一端口配置为 1733
修改所有配置文件，确保默认端口一致：

#### 前端修改
- ✅ `frontend/src/renderer/src/services/axiosConfig.ts`: 8008 → 1733
- ✅ `frontend/electron.vite.config.ts`: 8000 → 1733

#### 后端修改
- ✅ `opencontext/cli.py`: 8000 → 1733

#### 配置文件修改
- ✅ `.env.example`: 8000 → 1733
- ✅ `config/config.ollama.example.yaml`: 8000 → 1733

#### 文档更新
- ✅ `docs/ENV_CONFIGURATION.md`: 8000 → 1733
- ✅ `docs/issues/2025-10-19-unified-env-web-config.md`: 8000 → 1733

### 2. 模型配置验证
经过代码审查，前端的模型配置验证逻辑是合理的：
- 检查 VLM 模型 ID 是否配置
- 检查 Embedding 模型 ID 是否配置
- 允许 API key 为空（支持 Ollama、LocalAI 等本地提供商）
- 不需要修改验证逻辑

### 3. 配置一致性保证
确保前后端配置来源统一：
- 环境变量 `.env` 文件优先级最高
- 通过 `WEB_HOST` 和 `WEB_PORT` 统一配置
- 前端通过 Vite 的 `VITE_WEB_HOST` 和 `VITE_WEB_PORT` 读取
- 后端通过 Python 的 `os.environ` 读取
- 所有配置文件默认值统一为 1733

## 修改的文件 (Modified Files)

### 核心配置文件
1. `.env.example` - 默认端口配置
2. `config/config.ollama.example.yaml` - Ollama 配置示例

### 前端代码
3. `frontend/src/renderer/src/services/axiosConfig.ts` - Axios 默认端口
4. `frontend/electron.vite.config.ts` - Vite 环境变量映射

### 后端代码
5. `opencontext/cli.py` - CLI 默认端口

### 文档
6. `docs/ENV_CONFIGURATION.md` - 环境变量配置文档
7. `docs/issues/2025-10-19-unified-env-web-config.md` - 配置统一说明

## 测试验证 (Testing)

### 1. 验证端口一致性
```bash
# 检查配置文件中的端口设置
grep -r "1733" --include="*.ts" --include="*.py" --include="*.yaml" . | grep -v ".git" | grep port
```

### 2. 启动测试
```bash
# 清理并重新构建
cd frontend && npm install && npm run build
cd .. && ./start-dev.sh
```

### 3. 功能验证
- ✅ 前端能够连接到后端 (端口 1733)
- ✅ 屏幕截图可以正常上传
- ✅ 可以正常获取和显示生成的总结
- ✅ 模型配置验证正常工作

## 配置优先级 (Configuration Priority)

系统按以下优先级读取端口配置：
```
1. 命令行参数 (--port)
   ↓
2. 环境变量 (.env 文件中的 WEB_PORT)
   ↓
3. config.yaml 中的配置
   ↓
4. 代码中的默认值 (1733)
```

## 最佳实践建议 (Best Practices)

1. **使用 .env 文件**: 复制 `.env.example` 到 `.env` 并根据需要修改
2. **保持配置一致**: 不要在多个地方重复配置同一个值
3. **遵循优先级**: 理解配置的加载顺序
4. **本地开发**: 使用默认的 1733 端口
5. **生产部署**: 通过环境变量或命令行参数指定端口

## 相关链接 (Related Links)

- [环境变量配置指南](docs/ENV_CONFIGURATION.md)
- [LLM 配置指南](docs/LLM_CONFIGURATION_GUIDE.md)
- [配置架构分析](CONFIG_ARCHITECTURE_ANALYSIS.md)

## 总结 (Summary)

此次修复确保了：
1. ✅ 所有配置文件中的默认端口统一为 1733
2. ✅ 前后端通信端口一致
3. ✅ 屏幕截图上传功能恢复
4. ✅ 总结生成和获取功能正常
5. ✅ 模型配置验证逻辑合理
6. ✅ 配置来源统一，避免重复和冲突

现在系统的端口配置是一致的、可预测的，并且遵循了 12-Factor App 的最佳实践。
