# IGV Overlap Track API - 快速使用指南

## 📍 API 端点

```
GET /api/v1/igv/overlap-track
```

## 🎯 用途

为 IGV.js 基因组浏览器提供 lncRNA-ChIP-seq overlap 数据的 BED6 格式轨道,支持动态区域查询。

## 📝 参数

### 必需参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `chr` | string | 染色体（推荐） | "chr1" 或 "1" |
| `chromosome` | string | `chr` 的别名 | "chr22" 或 "22" |
| `start` | integer | 起始位置(0-based) | 1000000 |
| `end` | integer | 结束位置(0-based) | 2000000 |

### 可选筛选

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `mark_type` | string | 筛选特定 Mark 类型 | "H3K27me3" |
| `cell_line` | string | 筛选特定细胞系 | "K562" |
| `min_ba` | float | 最小结合亲和力阈值（>=0） | 80.0 |
| `min_binding_affinity` | float | `min_ba` 的兼容别名（>=0） | 80.0 |
| `limit` | integer | 最大返回条目数（防止一次拉取过多数据） | 50000 |

## 📦 响应格式

**Content-Type**: `text/plain`

**BED6 格式** (6列,tab分隔):

```
chr1    1000120 1001050 MALAT1->GENE1|H3K27me3|K562 850     .
chr1    1002300 1003100 NEAT1->GENE2|H3K4me3|GM12878 750     .
```

**列定义**:
1. 染色体
2. 起始位置
3. 结束位置
4. 名称（包含 lncRNA/target/mark/cell_line 信息；便于 IGV 展示与排障）
5. 分数 (BA * 10, 0-1000)
6. 链（当前为 '.'）

## 🚀 使用示例

### JavaScript (fetch)

```javascript
async function loadOverlapTrack(chr, start, end, filters = {}) {
  const params = new URLSearchParams({
    chr,
    start: start.toString(),
    end: end.toString(),
    ...filters
  });

  const response = await fetch(
    `/api/v1/igv/overlap-track?${params}`
  );

  const bedData = await response.text();
  return bedData;
}

// 基础查询
const data1 = await loadOverlapTrack('chr1', 1000000, 2000000);

// 带筛选
const data2 = await loadOverlapTrack('chr1', 1000000, 2000000, {
  mark_type: 'H3K27me3',
  cell_line: 'K562',
  min_ba: 80
});
```

### IGV.js 集成

```javascript
const igvConfig = {
  genome: 'hg19',
  locus: 'chr1:1,000,000-2,000,000',
  tracks: [
    // 其他轨道...

    // lncRNA-ChIP-seq Overlap 轨道
    {
      name: 'lncRNA-ChIP-seq Overlaps',
      type: 'annotation',
      format: 'bed',
      url: `/api/v1/igv/overlap-track?chr=$CHR&start=$START&end=$END`,
      indexURL: null,
      displayMode: 'EXPANDED',
      height: 100,
      color: '#9B59B6'
    }
  ]
};

const igvBrowser = await igv.createBrowser(divElement, igvConfig);
```

### IGV.js 动态筛选

```javascript
// 创建带筛选的 overlap 轨道
function createOverlapTrack(markType = null, cellLine = null, minBa = null) {
  const params = new URLSearchParams({
    chr: '$CHR',
    start: '$START',
    end: '$END'
  });

  if (markType) params.append('mark_type', markType);
  if (cellLine) params.append('cell_line', cellLine);
  if (minBa) params.append('min_ba', minBa.toString());

  return {
    name: `Overlaps (${markType || 'All'})`,
    type: 'annotation',
    format: 'bed',
    url: `/api/v1/igv/overlap-track?${params}`,
    displayMode: 'SQUISHED',
    height: 50
  };
}

// 添加多个轨道
const tracks = [
  createOverlapTrack('H3K27me3', 'K562'),
  createOverlapTrack('H3K4me3', 'GM12878'),
  createOverlapTrack(null, null, 80) // 所有 BA >= 80 的 overlap
];

tracks.forEach(track => igvBrowser.loadTrack(track));
```

## ⚡ 性能

- **响应时间**: < 100ms (典型 1-5Mb 区间)
- **最大记录数**: 默认 50,000 条/请求（可通过 `limit` 调整，最大 200,000）
- **最大区间**: 10Mb (防止超时)

## ⚠️ 限制

1. **区间大小**: 最大 10Mb (10,000,000 bp)
2. **记录数**: 最多返回 200,000 条（由 `limit` 控制）
3. **物种**: 目前仅支持 Human (species_id=1)

## 🔧 错误处理

```javascript
async function safeLoadOverlapTrack(chr, start, end) {
  try {
    const response = await fetch(
      `/api/v1/igv/overlap-track?chr=${chr}&start=${start}&end=${end}`
    );

    if (!response.ok) {
      const error = await response.json();
      console.error('API Error:', error.detail);
      return null;
    }

    return await response.text();
  } catch (error) {
    console.error('Network Error:', error);
    return null;
  }
}
```

## 📊 可用筛选值

### Mark 类型
- `H3K27me3` - Polycomb 抑制
- `H3K4me3` - 活性启动子
- `H3K4me1` - 增强子
- `H3K27ac` - 活性增强子
- `H3K36me3` - 转录延伸
- `H3K9me3` - 异染色质
- `H3K9ac` - 活性转录
- `H4K20me1` - 转录活性
- `DNase-HS` - 开放染色质
- ... 更多

### 细胞系
- `K562` - 白血病细胞
- `GM12878` - B淋巴细胞
- `H1-hESC` - 胚胎干细胞
- `HepG2` - 肝癌细胞
- `A549` - 肺腺癌
- `MCF-7` - 乳腺癌
- `HMEC` - 正常乳腺上皮

## 🔗 相关资源

- **API 文档**: http://localhost:8000/docs#/igv/get_overlap_track_api_v1_igv_overlap_track_get
- **测试脚本**: `/frontend/backend/test_overlap_track.sh`
- **实现报告**: `/docs/IGV_OVERLAP_TRACK_IMPLEMENTATION.md`

## 💡 最佳实践

1. **分页加载**: 对于大染色体,分段查询以保持响应速度
2. **筛选优先**: 使用 mark_type 和 cell_line 筛选减少数据量
3. **缓存结果**: 对于常见区间,前端可以缓存结果
4. **错误重试**: 实现自动重试机制处理网络波动

## 📞 技术支持

如有问题,请联系:
- 项目 GitHub: https://github.com/wyjistest/human-lncrna-atlas
- 开发者: wyjistest

---

**最后更新**: 2026-02-02
