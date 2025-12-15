# Human LncRNA Atlas 踩坑记录

> 开发过程中遇到的问题和解决方案汇总

## 前后端 API 契约

### 问题：表格列显示空白

**现象**: Ant Design Table 列显示 `-` 或空白

**原因**: 前端 TypeScript interface 字段名与后端实际返回不一致

| 前端期望 | 后端实际 |
|---------|---------|
| `lncrna_symbol` | `lncrna_name` |
| `chromosome` | `chr` |
| `species_count` | `conservation_count` |

**解决**:
```bash
# 检查实际 API 返回字段名
curl -s "http://localhost:8000/api/v1/xxx?limit=1" | python3 -m json.tool | head -30
```

**预防**: 开发前先用 curl 或 Postman 确认 API 返回结构

---

### 问题：rowKey 重复警告

**现象**: React 控制台报 "duplicate key" 警告

**原因**: 数据无唯一主键或主键重复

**解决**: 使用组合键
```typescript
rowKey={(record, index) => `${record.lncrna_gene_id}-${record.target_gene_id}-${index}`}
```

---

### 问题：图数据结构不匹配

**现象**: 疾病网络 Tab 显示 "No Data"

**原因**: 前端期望扁平表格结构，后端返回图数据 `{nodes, edges}`

**解决**: 检查 API 返回结构类型，重写组件适配图数据格式

---

## React 19 Hooks 规则

### 问题：Hooks 顺序违规

**现象**: `React has detected a change in the order of Hooks`

**原因**: 条件语句中调用了 Hooks

**修复**:
```typescript
// ❌ 错误
if (loading) return <Loading />
const [data] = useQuery()  // Hooks 在 return 后

// ✅ 正确
const [data] = useQuery()  // 所有 Hooks 在条件 return 前
if (loading) return <Loading />
```

---

### 问题：render 阶段访问 ref

**现象**: `Cannot read ref.current during render`

**原因**: 在 render 阶段读取或更新 `ref.current`

**修复**: 改用 `useMemo` + 直接依赖

---

### 问题：静态组件定义

**现象**: 组件每次 render 都重新创建

**原因**: 在 render 函数内定义组件

**修复**: 改用 JSX 表达式或提取到外部

---

## 常见编译错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `Property 'xxx' is missing` | 配置文件未同步 | 同步 `src/config/` 和 `src/i18n/config/` |
| `Cannot find module 'igv'` | 依赖未安装 | `npm install` |
| `TS2741: Property missing` | 类型不完整 | 检查 `types/` 目录 |
| `ModuleNotFoundError: app.routers.xxx` | router 不存在 | 检查 `main.py` 导入 |

---

## SQLAlchemy 注意点

### 问题：布尔比较

```python
# ❌ 错误 - E712 linting error
query.filter(Model.active == True)

# ✅ 正确
query.filter(Model.active.is_(True))
```

---

### 问题：空值检查

```python
# ❌ 错误 - Python 语法在 SQLAlchemy 中无效
query.filter(Model.field is not None)

# ✅ 正确
query.filter(Model.field.isnot(None))
```

---

### 问题：可空外键 JOIN

```python
# ❌ 错误 - 可空外键用 join 会丢失数据
query.join(Gene, Gene.core_id == Regulation.core_id)

# ✅ 正确 - 使用 outerjoin
query.outerjoin(Gene, Gene.core_id == Regulation.core_id)
```

---

## ETL 数据一致性

### 问题：ON CONFLICT 序列映射错误

**现象**: sequences 表与 regulations 表数据不对应

**原因**: `ON CONFLICT DO NOTHING` + `RETURNING` 只返回插入的行，跳过的行无法获取 ID

**修复**: 使用临时表 + `row_idx` 追踪原始行索引

```sql
CREATE TEMP TABLE temp_regulations_batch (
    row_idx INTEGER,
    batch_id INTEGER,
    ...
) ON COMMIT DELETE ROWS
```

---

### 问题：批次内重复数据

**现象**: 同一批次内有重复记录

**修复**: 使用 `DISTINCT ON` CTE 去重

```sql
WITH deduped AS (
    SELECT DISTINCT ON (species_id, lncrna_gene_id, target_gene_id, ...)
    * FROM temp_table
    ORDER BY species_id, lncrna_gene_id, ...
)
INSERT INTO regulations SELECT * FROM deduped
```

---

## ECharts 图表

### 问题：节点重复

**现象**: Sankey 图显示重复节点

**原因**: 使用 `name` 作为节点标识，但 `links` 使用 `id`

**修复**: 使用 `id` 作为 ECharts 节点 name，添加 `label.formatter` 显示真实名称

---

### 问题：Canvas 测试报错

**现象**: JSDOM 环境 ECharts 报 canvas 错误

**修复**: 全局 mock canvas context

```typescript
// test/setup.ts
HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
  fillRect: vi.fn(),
  // ...
})
```

---

## 安全相关

### 问题：X-Forwarded-For 伪造

**现象**: 攻击者可伪造 IP 绕过白名单

**修复**: 仅从可信代理接受转发头

```python
TRUSTED_PROXIES = ["127.0.0.1", "::1"]

def _get_client_ip(request):
    if _is_trusted_proxy(request.client.host):
        return request.headers.get("X-Forwarded-For", "").split(",")[0]
    return request.client.host
```

---

### 问题：数据库异常暴露

**现象**: PostgreSQL 错误直接返回客户端

**修复**: 创建 `sanitize_db_error()` 返回通用消息 + 错误 ID

---

## .gitignore 踩坑

### 问题：requirements.txt 被忽略

**原因**: `.gitignore` 中 `*.txt` 规则过于宽泛

**修复**: 添加例外
```
*.txt
!requirements.txt
```

---

*文档更新: 2025-12-15*
