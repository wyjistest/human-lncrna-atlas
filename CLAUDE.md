# Human LncRNA Atlas - Claude Code 配置

## 代码搜索规则

**必须优先使用 Augment MCP 搜索代码上下文**

当需要理解代码、查找实现、或搜索相关文件时：

```
使用工具: mcp__auggie-mcp-d3__codebase-retrieval
不要直接用: Grep/Read/Glob 进行碎片化搜索
```

### 使用场景

| 场景 | 用 Augment MCP |
|------|----------------|
| 理解某个功能的实现 | Yes |
| 查找相关代码文件 | Yes |
| 分析代码依赖关系 | Yes |
| 查找 bug 根因 | Yes |
| 精确查找已知文件路径 | No (用 Read) |
| 查找精确字符串匹配 | No (用 Grep) |

### 示例

```javascript
// 搜索 ChIP-seq 相关实现
mcp__auggie-mcp-d3__codebase-retrieval({
  information_request: "Find all code related to ChIP-seq track loading, including frontend components, backend API endpoints, and data flow"
})
```

## 项目结构

- `/data/wenyujianData/humanLncAtlas/` - 本地开发目录（含数据）
- `/data/wenyujianData/human-lncrna-atlas-github/` - GitHub 仓库（代码同步）

## 技术栈

- **后端**: FastAPI + PostgreSQL
- **前端**: React 18 + TypeScript + Vite + Ant Design 5
- **可视化**: IGV.js (基因组浏览器) + Cytoscape.js (网络图) + ECharts (图表)

## 开发工作流

1. 在 `/data/wenyujianData/humanLncAtlas/` 进行开发和测试
2. 修改完成后复制到 `/data/wenyujianData/human-lncrna-atlas-github/`
3. 提交并推送到 GitHub

## 推送前验证流程（必须执行）

**在推送到 GitHub 之前，必须在 GitHub 目录中验证编译：**

```bash
# 1. 切换到 GitHub 目录
cd /data/wenyujianData/human-lncrna-atlas-github/frontend/web

# 2. 安装依赖（如有更新）
npm install

# 3. 运行编译验证
npm run build

# 4. 确认编译成功后再推送
git add . && git commit -m "..." && git push
```

### 注意事项

1. **不要只在开发目录验证** - 两个目录的 node_modules 和文件可能不同
2. **检查重复文件** - 项目中存在代码冗余，修改配置时需同步多个位置：
   - `src/config/` 和 `src/i18n/config/`
   - `src/components/` 和 `src/i18n/components/`
3. **文件同步检查** - 使用以下命令检查是否有遗漏：
   ```bash
   # 查找同名文件
   find /data/wenyujianData/human-lncrna-atlas-github/frontend/web/src -name "markConfigs.ts"
   find /data/wenyujianData/human-lncrna-atlas-github/frontend/web/src -name "MarkSelector.tsx"
   ```

### 常见编译错误

| 错误类型 | 原因 | 解决方案 |
|---------|------|---------|
| `Property 'xxx' is missing` | 配置文件未同步 | 同步所有同名配置文件 |
| `Cannot find module 'igv'` | 依赖未安装 | 运行 `npm install` |
| `TS2741: Property missing` | 类型定义不完整 | 检查 types/ 目录文件 |
