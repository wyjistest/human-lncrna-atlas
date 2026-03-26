# 前端首屏 Bundle / Modulepreload 回归锚点

目标：把“首屏资源体积”和“modulepreload 列表”变成**可审计、可回滚**的回归锚点，避免：

- 重依赖（如 `pdf-vendor` / `igv-vendor` 等）被首屏提前拉起
- entry chunk 体积悄悄变大导致首屏变慢
- modulepreload 总量/单个 vendor 出现明显回归但难以定位

相关脚本：

- 首屏 modulepreload + 体积预算门禁：`frontend/web/scripts/check-entry-preloads.mjs`
- bundle size 快照（含 entry/modulepreload/assets）：`frontend/web/scripts/report-bundle-sizes.mjs`
- 两份快照对比 + 回归门禁：`frontend/web/scripts/compare-bundle-sizes.mjs`

## 当前首屏 i18n 策略

为了避免入口 chunk 因翻译资源持续膨胀，前端当前采用“基础 namespace 首屏 eager，其它页面 namespace 路由级 lazy”的策略：

- 首屏只在 `frontend/web/src/i18n/index.ts` 中静态注册 `common` / `nav` / `home`
- 其它页面命名空间通过 `ensureNamespaces()` 显式动态导入后，再渲染对应路由
- 路由级包装统一走 `frontend/web/src/i18n/lazyWithNamespaces.ts`

如果后续出现 entry chunk 或 `i18n-vendor` 明显回归，优先检查：

- 是否把页面 namespace 重新改回了入口静态 import
- 是否新增页面绕过了 `lazyWithNamespaces()`，导致页面在 namespace 注册前先渲染
- 是否把不该首屏出现的翻译资源重新放回 `EAGER_NAMESPACES`

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
