# 前端首屏 Bundle / Modulepreload 回归锚点

目标：把“首屏资源体积”和“modulepreload 列表”变成**可审计、可回滚**的回归锚点，避免：

- 重依赖（如 `pdf-vendor` / `igv-vendor` 等）被首屏提前拉起
- entry chunk 体积悄悄变大导致首屏变慢
- modulepreload 总量/单个 vendor 出现明显回归但难以定位

相关脚本：

- 首屏 modulepreload + 体积预算门禁：`frontend/web/scripts/check-entry-preloads.mjs`
- bundle size 快照（含 entry/modulepreload/assets）：`frontend/web/scripts/report-bundle-sizes.mjs`
- 两份快照对比 + 回归门禁：`frontend/web/scripts/compare-bundle-sizes.mjs`

## 最短路径（本地）

在前端目录执行：

```bash
cd frontend/web
npm run build
node scripts/check-entry-preloads.mjs
```

如 `check-entry-preloads.mjs` 失败，说明 `dist/index.html` 出现了不允许的首屏 modulepreload（或 entry/预加载体积超预算），需要检查最近的依赖/路由拆分/预加载策略变更。

## 记录快照（建议）

生成一份“可机器读取”的 JSON 快照：

```bash
cd frontend/web
node scripts/report-bundle-sizes.mjs --json "../../docs/baselines/frontend/bundle-sizes.baseline.json"
```

建议把 baseline 快照提交到仓库（小文件，可 `git revert` 回滚），用于后续 diff 定位与门禁。

## 对比快照（定位/门禁）

示例：把当前 build 快照写到临时文件，然后与 baseline 对比：

```bash
cd frontend/web
node scripts/report-bundle-sizes.mjs --json "/tmp/bundle-sizes.current.json"
node scripts/compare-bundle-sizes.mjs \
  "../../docs/baselines/frontend/bundle-sizes.baseline.json" \
  "/tmp/bundle-sizes.current.json"
```

`compare-bundle-sizes.mjs` 会输出：

- entry / modulepreload 总量的 gzip 体积变化
- 关键 vendor family（如 `antd-vendor`、`igv-vendor`、`pdf-vendor`）的稳定对比视图

并在超过阈值时返回非 0 退出码（可用于 CI 或本地门禁止损）。

