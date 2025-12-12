# Human LncRNA Atlas - API使用指南

**版本**: v0.1.0
**基础URL**: `http://localhost:8000`
**文档**: http://localhost:8000/docs

---

## 📋 目录

- [快速开始](#快速开始)
- [认证](#认证)
- [核心端点](#核心端点)
- [数据模型](#数据模型)
- [错误处理](#错误处理)
- [性能指标](#性能指标)

---

## 🚀 快速开始

### 健康检查

```bash
curl http://localhost:8000/health
```

**响应**:
```json
{
  "status": "healthy",
  "database": "healthy",
  "version": "0.1.0"
}
```

### 基础查询示例

```javascript
// 获取基因列表
fetch('http://localhost:8000/api/v1/genes?page=1&page_size=10')
  .then(res => res.json())
  .then(data => console.log(data));
```

---

## 🔐 认证

**当前版本**: 无需认证（开发环境）
**生产环境**: 将使用JWT Token认证

---

## 📡 核心端点

### 1. 基因 (Genes)

#### 获取基因列表

```http
GET /api/v1/genes
```

**查询参数**:
| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `page` | int | 否 | 页码（默认1） | `1` |
| `page_size` | int | 否 | 每页数量（默认100，最大1000） | `10` |
| `gene_type` | string | 否 | 基因类型 | `lncRNA` 或 `protein_coding` |
| `species_id` | int | 否 | 物种ID | `1` (人类) |
| `chromosome` | string | 否 | 染色体 | `chr1` |
| `search` | string | 否 | 搜索关键词 | `CATG00000000011` |

**响应示例**:
```json
{
  "items": [
    {
      "gene_id": 17276,
      "core_id": 11,
      "gene_name": "CATG00000000011.1",
      "gene_type": "lncRNA",
      "species_name": "人类",
      "regulation_count": 46
    }
  ],
  "total": 17248,
  "page": 1,
  "page_size": 10,
  "total_pages": 1725
}
```

#### 获取基因详情

```http
GET /api/v1/genes/{gene_id}
```

**响应示例**:
```json
{
  "gene_id": 17276,
  "gene_name": "CATG00000000011.1",
  "species_name": "人类",
  "regulation_count": 46,
  "target_count": 35,
  "disease_count": 1,
  "orthologs": [
    {
      "species_name": "黑猩猩",
      "gene_name": "CATG00000000011.1_chimp"
    }
  ]
}
```

---

### 2. 调控关系 (Regulations)

#### 获取调控关系列表

```http
GET /api/v1/regulations
```

**查询参数**:
| 参数 | 类型 | 必填 | 说明 | 范围 |
|------|------|------|------|------|
| `page` | int | 否 | 页码 | ≥1 |
| `page_size` | int | 否 | 每页数量 | 1-1000 |
| `species_id` | int | 否 | 物种ID | - |
| `lncrna_gene_id` | int | 否 | lncRNA基因ID | - |
| `target_gene_id` | int | 否 | 靶基因ID | - |
| `min_ba` | float | 否 | 最小结合亲和力 | ≥0 (无上限) |
| `chromosome` | string | 否 | 染色体 | - |

**重要**: `min_ba` 参数**无上限**，可以使用任意高值（如700+）进行过滤。

**响应示例**:
```json
{
  "items": [
    {
      "regulation_id": 804941,
      "species_id": 1,
      "species_name": "人类",
      "lncrna_gene_name": "CATG00000042135.1",
      "target_gene_name": "ENSG00000268518.1",
      "binding_affinity": "755.9900",
      "num_peaks": 2
    }
  ],
  "total": 804630
}
```

#### 高亲和力过滤示例

```bash
# 获取BA>700的调控关系
curl "http://localhost:8000/api/v1/regulations?min_ba=700&page_size=10"
```

---

### 3. 疾病关联 (Diseases)

#### 获取疾病列表

```http
GET /api/v1/diseases
```

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `page` | int | 页码 |
| `page_size` | int | 每页数量 |
| `trait_category` | string | 疾病分类 |
| `search` | string | 搜索关键词 |

**响应示例**:
```json
{
  "items": [
    {
      "trait_id": 1,
      "trait_name": "mineral metabolism disease",
      "description": null,
      "trait_doid": "DOID:0050032",
      "gene_count": 28,
      "lncrna_count": 6
    }
  ],
  "total": 273
}
```

---

### 4. 统计分析 (Stats)

#### 获取统计概览

```http
GET /api/v1/stats/overview
```

**响应示例**:
```json
{
  "total_genes": 17248,
  "total_lncrna": 1969,
  "total_protein_coding": 3515,
  "total_regulations": 804630,
  "total_traits": 273,
  "species_stats": [
    {
      "species_id": 1,
      "species_name": "人类",
      "gene_count": 5484,
      "regulation_count": 496064
    }
  ]
}
```

#### 获取Top基因

```http
GET /api/v1/stats/top-genes?limit=10
```

**查询参数**:
| 参数 | 类型 | 说明 | 范围 |
|------|------|------|------|
| `limit` | int | 返回数量 | 1-100 |
| `gene_type` | string | 基因类型过滤 | `lncRNA` / `protein_coding` |

---

## 📦 数据模型

### 物种 (Species)

| ID | 名称 | 英文名 | 基因数 | 调控关系 |
|----|------|--------|--------|---------|
| 1 | 人类 | Human | 5,484 | 496,064 |
| 2 | 黑猩猩 | Chimpanzee | 4,341 | 156,136 |
| 3 | 猕猴 | Macaque | 3,917 | 102,430 |
| 4 | 狨猴 | Marmoset | 3,506 | 50,000 |

### 基因类型

- `lncRNA`: 长非编码RNA
- `protein_coding`: 蛋白编码基因

### 结合亲和力 (Binding Affinity)

- **范围**: 0 - 800+
- **单位**: 无量纲评分
- **解释**: 值越高，结合亲和力越强
- **典型高值**: 700-800

---

## ⚠️ 错误处理

### 标准错误响应

```json
{
  "message": "Error message",
  "detail": "Detailed error information"
}
```

### 常见错误码

| 状态码 | 说明 | 示例 |
|--------|------|------|
| 200 | 成功 | - |
| 404 | 资源不存在 | 基因ID不存在 |
| 422 | 参数验证失败 | `page_size` 超过1000 |
| 500 | 服务器错误 | 数据库连接失败 |

### 参数验证规则

```javascript
// 分页参数
page >= 1
page_size: 1 <= x <= 1000

// BA过滤
min_ba >= 0  // 无上限
max_ba >= 0  // 无上限

// 基因类型
gene_type in ['lncRNA', 'protein_coding']
```

---

## ⚡ 性能指标

### 响应时间（实测）

| 端点 | 数据量 | 响应时间 | 评级 |
|------|--------|---------|------|
| 基因列表 | 1000条 | 0.69秒 | ⭐⭐⭐⭐ |
| 调控关系 | 1000条 | 0.17秒 | ⭐⭐⭐⭐⭐ |
| 基因详情 | 1条 | 0.03秒 | ⭐⭐⭐⭐⭐ |
| 统计概览 | - | 0.24秒 | ⭐⭐⭐⭐⭐ |

### 并发能力

- **测试**: 50并发请求
- **总时间**: 2.01秒
- **平均**: 40ms/请求
- **评级**: ⭐⭐⭐⭐⭐

### 优化建议

**当前性能已足够生产使用。**

如果未来需要优化：
1. 使用 `page_size` 控制返回数量
2. 添加具体过滤条件减少结果集
3. 使用缓存（统计数据）

---

## 🔧 前端集成示例

### React + Axios

```javascript
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api/v1';

// 获取基因列表
export const getGenes = async (params) => {
  const response = await axios.get(`${API_BASE}/genes`, { params });
  return response.data;
};

// 获取调控关系（高亲和力）
export const getHighAffinityRegulations = async (minBA = 700) => {
  const response = await axios.get(`${API_BASE}/regulations`, {
    params: { min_ba: minBA, page_size: 100 }
  });
  return response.data;
};

// 使用示例
const data = await getGenes({
  page: 1,
  page_size: 10,
  gene_type: 'lncRNA'
});
```

### Vue 3 + Fetch

```javascript
// composables/useAPI.js
export const useGenes = () => {
  const fetchGenes = async (params) => {
    const query = new URLSearchParams(params);
    const response = await fetch(`/api/v1/genes?${query}`);
    return response.json();
  };

  return { fetchGenes };
};
```

### TypeScript 类型定义

```typescript
interface Gene {
  gene_id: number;
  gene_name: string;
  gene_type: 'lncRNA' | 'protein_coding';
  species_name: string;
  regulation_count: number;
}

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface Regulation {
  regulation_id: number;
  species_id: number;
  species_name: string;
  lncrna_gene_name: string;
  target_gene_name: string;
  binding_affinity: string;
  num_peaks: number;
}
```

---

## 📝 更新日志

### v0.1.0 (2025-11-25)

**新增**:
- ✅ 所有核心API端点
- ✅ 完整的分页支持
- ✅ 多维度过滤功能
- ✅ 统计分析接口

**修复**:
- ✅ 分页计数bug（GROUP BY场景）
- ✅ 子查询标准化（SQLAlchemy 2.0）
- ✅ BA阈值上限移除（支持高值过滤）
- ✅ 字段别名统一（species_name等）

**性能**:
- ✅ 1000条数据<1秒
- ✅ 并发50请求<3秒
- ✅ 所有过滤查询<200ms

---

## 🆘 支持

### 问题反馈

- **API文档**: http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/health

### 常见问题

**Q: 为什么 `min_ba=150` 返回422错误？**
A: 旧版本有 `le=100` 限制，已在v0.1.0移除。请更新到最新版本。

**Q: 如何获取所有物种的数据？**
A: 不传 `species_id` 参数即可获取所有物种数据。

**Q: 分页最大支持多少条？**
A: `page_size` 最大1000条。建议使用100-500以获得最佳性能。

---

**最后更新**: 2025-11-25
**维护者**: Human LncRNA Atlas Team
