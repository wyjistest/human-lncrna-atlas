# Frontend Baselines（可选）

本目录用于存放 **前端构建产物的可提交基线**（JSON 快照），用于在优化/重构时快速定位 bundle 体积与首屏预加载的回归。

相关脚本：

- 生成快照：`frontend/web/scripts/report-bundle-sizes.mjs`
- 对比快照 + 回归门禁：`frontend/web/scripts/compare-bundle-sizes.mjs`
- 首屏 modulepreload + 体积预算门禁：`frontend/web/scripts/check-entry-preloads.mjs`

推荐约定（可按需调整）：

- baseline 文件：`docs/baselines/frontend/bundle-sizes.baseline.json`
- 默认门禁阈值（可通过参数覆盖）：entry/modulepreload 回归 >2% 失败（见 `frontend/web/scripts/compare-bundle-sizes.mjs`）。

生成示例：

```bash
cd frontend/web
npm run build
node scripts/report-bundle-sizes.mjs --json "../../docs/baselines/frontend/bundle-sizes.baseline.json"
```

校验（本地可选，不进入默认 CI 门禁）：

```bash
bash scripts/run-tests.sh frontend-baselines
```
