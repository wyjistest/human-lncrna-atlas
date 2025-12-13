## 测试执行记录（2025-12-02）

- 未执行自动化测试：本次为静态代码审查，未启动后端/前端服务和数据库，未运行 pytest / vitest / e2e。
- 风险：潜在行为回归或集成问题未通过实测验证。

## 测试执行记录（2025-12-13，第1轮）

### Frontend（React/TS）

- `cd frontend/web && npm run lint`：通过（仅告警，主要为 `no-explicit-any` 与 `react-hooks/exhaustive-deps`）。
- `cd frontend/web && npm run build`：通过（`tsc -b` + `vite build`）。
- `cd frontend/web && npm run test:run`：通过（11 个文件，171 条测试；存在 antd 组件弃用告警与 jsdom CSS 解析告警）。

### Backend / Scripts（Python）

- `ruff check`（针对本轮修改文件）：通过。
- `python3 -m compileall -q frontend/backend/app frontend/backend/scripts scripts etl`：通过。
- `pytest -q frontend/backend/tests/test_conservation_regulations_items.py`：通过（2 条单元测试）。

### 未执行项与原因

- 后端现有 `frontend/backend/tests/*` 多数为合同/冒烟/性能测试，默认依赖已运行的 API（`TEST_API_URL`，默认 `http://localhost:8000`）与真实/近似数据库数据；本轮未在容器内启动数据库与服务，因此未执行整套后端集成测试。

## 测试执行记录（2025-12-13，第2轮）

### Frontend（React/TS）

- `cd frontend/web && npm run lint`：通过（131 warnings；主要为 `no-explicit-any` 与少量 `react-hooks/exhaustive-deps` 告警）。
- `cd frontend/web && npm run build`：通过（`tsc -b` + `vite build`）。
- `cd frontend/web && npm run test:run`：通过（11 个文件，171 条测试）。

### Backend / Scripts（Python）

- `ruff check`（仅针对本轮修改文件）：通过。
- `python3 -m compileall -q frontend/backend/app frontend/backend/scripts scripts etl`：通过。
- `pytest -q frontend/backend/tests/test_conservation_regulations_items.py frontend/backend/tests/test_chipseq_export_overlap_pairs.py frontend/backend/tests/test_settings_env_aliases.py`：通过（5 条单元测试）。

### 额外观察

- 第1轮中出现的 Pydantic/FastAPI 弃用告警（`Field(env=...)`、`Query(regex=...)`）在第2轮已消除。

## 测试执行记录（2025-12-13，第3轮）

### Frontend（React/TS）

- `cd frontend/web && npm run lint`：通过（130 warnings；主要为 `no-explicit-any` 与少量 `react-hooks/exhaustive-deps` 告警）。
- `cd frontend/web && npm run build`：通过（`tsc -b` + `vite build`；仍有 chunk size 提示告警）。
- `cd frontend/web && npm run test:run`：通过（11 个文件，171 条测试；存在 antd 组件弃用告警与 jsdom CSS 解析告警）。

### Backend / Scripts（Python）

- `python3 -m compileall -q frontend/backend/app etl/templates`：通过。
- `ruff check frontend/backend/app/routers/chipseq_genes.py frontend/backend/app/core/cache.py etl/templates/batch_manager.py`：通过。
- `ruff check --select S etl/templates/batch_manager.py frontend/backend/app/core/cache.py frontend/backend/app/routers/chipseq_genes.py`：通过。
- `pytest -q frontend/backend/tests/test_batch_heatmap_matrix_builder.py frontend/backend/tests/test_conservation_regulations_items.py frontend/backend/tests/test_chipseq_export_overlap_pairs.py frontend/backend/tests/test_settings_env_aliases.py`：通过（7 条单元测试；有 2 条 FastAPI `Query(example=...)` 弃用告警）。

### 未执行项与原因

- 后端现有 `frontend/backend/tests/*` 多数为合同/冒烟/性能测试，默认依赖已运行的 API（`TEST_API_URL`）与数据库；本轮未在容器内启动服务与数据库，因此未执行整套后端集成测试。

## 测试执行记录（2025-12-13，第4轮）

### Backend / App（Python）

- `python3 -m compileall -q frontend/backend/app frontend/backend/scripts scripts etl`：通过
- `ruff check frontend/backend/app ...`（仅本轮修改文件）：通过
- `ruff check --select S frontend/backend/app`：通过
- 离线 pytest 单元测试：通过
  - `pytest -q frontend/backend/tests/test_conservation_regulations_items.py`
  - `pytest -q frontend/backend/tests/test_chipseq_export_overlap_pairs.py`
  - `pytest -q frontend/backend/tests/test_settings_env_aliases.py`
  - `pytest -q frontend/backend/tests/test_batch_heatmap_matrix_builder.py`
  - `pytest -q frontend/backend/tests/test_igv_overlap_track_unit.py`
  - `pytest -q frontend/backend/tests/test_overlap_sort_enums.py`

### Backend / 集成验证（启动本地服务）

- 启动：`cd frontend/backend && python3 -m uvicorn main:app --host 127.0.0.1 --port 8001`
- `TEST_API_URL=http://127.0.0.1:8001 pytest -q frontend/backend/tests/test_igv_overlap_track.py`：通过（11 passed）
- 结束后已停止 uvicorn 进程。

### Frontend（React/TS）

- `cd frontend/web && npm run lint`：通过（129 warnings；主要为 `no-explicit-any` 与少量 `react-hooks/exhaustive-deps`）
- `cd frontend/web && npm run build`：通过（`tsc -b` + `vite build`；仍有 chunk size 提示告警）
- `cd frontend/web && npm run test:run`：通过（11 个文件，171 条测试；存在 antd 组件弃用告警与 jsdom CSS 解析告警）

## 测试执行记录（2025-12-13，第5轮）

### Backend / App（Python）

- `python3 -m compileall -q frontend/backend/app frontend/backend/scripts scripts etl`：通过
- `ruff check frontend/backend/app/schemas/lncrna_chipseq_overlap.py frontend/backend/app/routers/chipseq.py etl/templates/import_base.py`：通过
- 离线 pytest 单元测试：通过（15 passed）
  - `pytest -q frontend/backend/tests/test_conservation_regulations_items.py frontend/backend/tests/test_chipseq_export_overlap_pairs.py frontend/backend/tests/test_settings_env_aliases.py frontend/backend/tests/test_batch_heatmap_matrix_builder.py frontend/backend/tests/test_igv_overlap_track_unit.py frontend/backend/tests/test_overlap_sort_enums.py`

### Backend / 集成验证（启动本地服务）

- 启动：`cd frontend/backend && python3 -m uvicorn main:app --host 127.0.0.1 --port 8001`
- `TEST_API_URL=http://127.0.0.1:8001 pytest -q frontend/backend/tests/test_igv_overlap_track.py`：通过（11 passed）
- 结束后已停止 uvicorn 进程。

### Frontend（React/TS）

- `cd frontend/web && npm run lint`：通过（126 warnings；消除 3 处 hooks missing deps）
- `cd frontend/web && npm run build`：通过（`tsc -b` + `vite build`；仍有 chunk size 提示告警）
- `cd frontend/web && npm run test:run`：通过（11 个文件，171 条测试；存在 antd 组件弃用告警与 jsdom CSS 解析告警）
