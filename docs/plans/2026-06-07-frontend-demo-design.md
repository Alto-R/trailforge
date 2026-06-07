# 前端 demo 设计 —— T1.6 探索辅助交互界面

**日期**：2026-06-07　**状态**：设计已确认（brainstorming 产出），待实现
**范围**：把已交付的后端 `/route` 探索辅助服务（[T1.1](../../reports/T1.1_backend_recommender.md)）接成可演示的端到端 demo（Phase 1 工程线 / PROGRESS §7 最高优）
**前置**：后端 5 接口契约已稳定（`/health` `/personas` `/route` `/trails` `/feedback`），本前端纯消费、**不改后端契约**。

---

## 0. 决策摘要（brainstorming 锁定项）

| # | 决策点 | 选定 | 理由 |
|---|---|---|---|
| 1 | demo 定位 | **本地 demo，但从一开始做响应式** | 核心价值是演示 + 截图进论文/报告；响应式留出日后当网页的余地 |
| 2 | 技术栈 | **Vite + React 19 + TypeScript** | 组件化对上候选列表/滑块/persona 这类有状态 UI；响应式成熟；可扩展 |
| 3 | 地图层 | **deck.gl + maplibre-gl + react-map-gl**，底图 carto 浅色矢量(positron) | 3 万段步道用 WebGL 才顺；候选高亮数据驱动着色优雅 |
| 4 | 布局/流程 | **单屏直玩**：左栏控件 + 右侧大地图 | 探索辅助核心是"随便拨偏好看路线怎么变"，单屏即时对比；persona 降级为可选预设 |
| 5 | 触发时机 | **全自动实时**（防抖 ~300ms，未选起点不发） | 演示"拨 challenge → 路线当场变"，最契合"显式偏好驱动可见个性化" |
| 6 | 候选展示 | **多候选同屏 + 不同色 + 卡片悬停高亮其余淡化** | MMR 多样性"一眼看到几条不同风格"正是研究叙事 |
| 7 | 反馈(Module E) | **轻量内联**：卡片"选这条" + 1–5 星 → `POST /feedback` | 演示闭环有反馈通道，不喧宾夺主 |

---

## 1. 技术栈与仓库落点

**栈**：Vite + React 19 + TypeScript；地图 `deck.gl + maplibre-gl + react-map-gl`，底图 carto 免费矢量瓦片(positron)；样式用轻量 CSS（CSS Modules 或少量 Tailwind），不引重组件库；请求用原生 `fetch` + 薄封装；状态用 React 自带 `useState/useReducer` + `useRoute` hook（不引 redux）。

> **[已安装版本]** 依赖全部由 `npm install`（最新版）落定、写入 `package-lock.json`，非手填。实测 `npm run dev` / 直接编译均通过，无 peer 冲突：
>
> - 运行时：`react`/`react-dom` 19.2、`@deck.gl/*` 9.3、`maplibre-gl` 5.24、`react-map-gl` 8.1。
> - 工具链：`vite` 8.0、`vitest` 4.1、`typescript` 6.0、`@vitejs/plugin-react` 6.0、`@testing-library/react` 16.3、`jsdom` 29、`@types/geojson` 7946。
> - **react-map-gl v8 改了入口**：从 `react-map-gl` 改为按底图分包导入（用 maplibre 时 `import {Map} from 'react-map-gl/maplibre'`）。下文 §3 的 `<Map>` 与 `MapView.tsx` 实现按此路径写。

**目录**（新增顶层 `frontend/`，与 `backend/` 平级，不污染 Python）：

```
frontend/
├── index.html
├── package.json / vite.config.ts / tsconfig.json
├── .env                 # VITE_API_BASE=http://127.0.0.1:8000
└── src/
    ├── main.tsx / App.tsx
    ├── api.ts           # 5 接口封装 + 类型(对齐 schemas.py)
    ├── types.ts         # Persona/RouteResponse/Candidate... TS 类型
    ├── hooks/
    │   └── useRoute.ts  # 防抖触发 /route、管 loading/error/candidates
    ├── components/
    │   ├── MapView.tsx      # deck.gl + maplibre；trails 底层 + 候选层 + 起点 marker
    │   ├── ControlPanel.tsx # persona 预设 + 5 偏好滑块 + 距离滑块
    │   ├── PersonaPicker.tsx
    │   ├── CandidateList.tsx / CandidateCard.tsx
    │   └── Banner.tsx       # 不可达 note / 提示
    └── styles/
```

**与后端关系**：纯消费现有 5 接口；本地开发用 Vite proxy 把 `/api/*` 转 `127.0.0.1:8000`（后端已开 CORS，proxy 更省心）。`GET /health` 作启动自检。

**响应式**：CSS Grid 主布局——桌面"左栏 360px + 右地图自适应"；窄屏(<768px)折成"上地图 + 下抽屉式控件/候选"。

---

## 2. 数据流与交互时序

**启动加载**（App mount）：
1. `GET /health` 自检（失败 → 全屏错误页"后端未启动，请先 `uvicorn backend.app:app`"）。
2. `GET /personas` → 渲染 5 张 persona 卡片（含 `default_prefs`）。
3. `GET /trails` → 全网 GeoJSON，deck.gl 底层淡色画出步道网，引导往有路处点。

**核心状态**（集中在 `useRoute`）：
```
start: [lng,lat] | null
persona: string | null
prefs: {challenge,nature,culture,popularity,scenic}   // 0–1
budgetKm: number                                      // 默认 4
candidates / startSnapped / reachable / note
loading / error
selectedIdx / hoveredIdx
```

**交互时序**：
- **点 persona 卡片** → 用 `default_prefs` 填充 5 滑块、记 `persona`。之后拖滑块脱离预设；请求时**传 `preferences` 不传 `persona`**（让显式偏好主导，符合后端 `resolve_prefs` 优先级）。
- **地图点选** → 设 `start`，立即触发首次 `/route`。
- **拖任意滑块/距离** → 防抖 ~300ms 后触发 `/route`（仅当 `start` 非空）。
- **请求** `POST /route {start, preferences:prefs, budget_km, n_routes:4}` → 更新 candidates，deck.gl 重画候选层。
- **悬停/点击候选卡** → 设 hovered/selected，地图对应路线加粗、其余淡化。
- **点"选这条"+星级** → `POST /feedback {chosen_index, rating, context:{start,prefs,budget}}`，卡片标记"已反馈"。

**竞态**：`/route` 用递增 `requestId` 或 `AbortController`，只采纳末次响应，防快速拖动旧响应覆盖新结果。

**错误/空态**：loading 显骨架；`reachable=false` 顶部黄条显 `note`；请求失败显可重试提示。

---

## 3. 地图渲染与配色

**deck.gl 图层**（自下而上）：
1. **底图** — react-map-gl `<Map>` 载 carto positron 样式（论文截图干净）。
2. **trails 层**（`GeoJsonLayer`，`/trails`）— 全网 29,941 段细灰线（`#c8ccd0`，1px），`pickable:true` 让点空白处也能取坐标。WebGL 一次性渲染，这是选 deck.gl 的主因。
3. **候选层**（`GeoJsonLayer`/`PathLayer`，每条候选一组）— 2–5 条用**色盲友好**定性色板（参考 ColorBrewer Set2 橙/蓝/绿/紫/棕，避开纯红绿对撞）；线宽 4px，选中/悬停那条加宽 6px + 不透明拉满，其余降到 0.35。
4. **起点层** — `start_snapped` 醒目 marker；若 snapped 与原始点选有偏移，画虚线连两点（诚实展示"吸附到最近步道"）。

**取坐标**：`onClick(info)` → `info.coordinate` = `[lng,lat]`(WGS84) 喂 `start`；点中候选线(`info.object`)→ 选中该候选（与卡片联动）。

**视图**：初始 `viewState` 用 trails bbox `fitBounds` 框住北京登山区；点候选/起点后不强行移镜头（避免演示画面乱跳），仅首次定位。

**联动**：`selectedIdx/hoveredIdx` 作候选层 `updateTriggers` 依赖；卡片 ↔ 地图双向高亮。

**性能**：trails 层数据加载一次、`useMemo` 缓存，不随 prefs 重建；只有候选层随 `/route` 更新。

**配色稳定**：候选颜色按返回顺序（score 降序）固定分配，保证"第 1 条永远橙色"的稳定心智。

---

## 4. 控件面板 / 候选卡 / 反馈 UI

**ControlPanel（左栏，自上而下）**：
- **标题区** — "TrailForge · 北京登山路线探索" + `/health` 绿点状态。
- **PersonaPicker** — 5 张小卡（label + 一句 description + size）。选中高亮；点击即填充滑块。灰字提示"选一个登山者作起点偏好，也可直接拖下面滑块"。
- **5 偏好滑块** — challenge/nature/culture/popularity/scenic（挑战/自然/人文/热门/打卡），0–1 步长 0.05，带当前值。拖动即脱离 persona 选中态。
- **距离滑块** — budget_km 1–15，默认 4，显示"目标里程 X km"。
- **状态行** — 未点起点提示"在地图上点一个起点开始"；loading 显 spinner。

**CandidateList（控件下方）**：`score` 降序卡片。每张 **CandidateCard**：
- 顶部：颜色圆点（对应地图线色）+ "路线 N" + `length_km`。
- 标签行：`labels` 做成 chip（如"坡度突出/自然占比高"）。
- 次要：`n_segments`、score 小字。
- 底部反馈：**"选这条" + 1–5 星** → `POST /feedback`，成功后角标"✓ 已记录"。
- 整卡 hover → 地图高亮该路线；`reachable=false` 显灰边 + "未达目标里程"。

**Banner（地图顶部）**：`note` 非空显黄条（如"该片区最多约 2.3km"）；请求失败显红条 + 重试。

**响应式**：窄屏(<768px)左栏变底部抽屉，候选卡横向滚动，地图占上半屏。

**空/边界**：候选为空显"该起点附近无可行路线，换个点试试"。

---

## 5. 测试与交付

**测试策略**（前端轻量）：
- **类型对齐**：`types.ts` 手写对齐 `backend/schemas.py`，作编译期契约护栏。
- **单元测试**(Vitest)：`api.ts` URL/payload 构造、`useRoute` 防抖+竞态（`AbortController` 只采纳末次）、persona→滑块填充、候选色板分配稳定。用 MSW/`fetch` mock，不连真后端。
- **冒烟/E2E**(Playwright，可选)：点起点→出候选→拖 challenge→候选变→"选这条"→feedback。列为有时间再补，不阻塞 demo。
- **人工验收清单**：health 红/绿、persona 填充、滑块实时重算、多候选同屏异色、卡片↔地图高亮、不可达 banner、窄屏抽屉。

**交付与运行**：
- `frontend/README.md` 写 `npm i && npm run dev`；根 `README.md` §4 补"前端启动"（先起后端再起前端）。
- 不引 CI；`dist/` gitignore。
- 文档：完成后按维护约定补 `reports/T1.6_frontend.md`（截图 + 交互说明 + 待办），更新 README 里程碑表 + PROGRESS §1/§7。

**实现分块**（给 writing-plans 用）：
1. 脚手架（Vite+React+TS+deck.gl 依赖、proxy、health 自检页）
2. 地图（trails 层 + 点选取坐标 + fitBounds）
3. 控件（persona + 滑块 + 距离）+ `useRoute`（防抖/竞态）
4. 候选（列表卡 + 地图候选层 + 双向高亮 + 配色）
5. 反馈 + banner + 响应式收尾
6. 测试 + 文档

每块跑通即可见增量（板块 2 能点地图、3 能出候选）。

---

## 6. 范围外（YAGNI / 推迟）

- 强制 onboarding 弹窗、向导式分步（已选单屏直玩）。
- 重组件库 / redux / SSR。
- 部署到公网、手机原生体验打磨（本期只保证响应式可用）。
- 把 `W_pref/W_cf` 暴露成可调参（属后端待调整项，见 [T1.1](../../reports/T1.1_backend_recommender.md) §5）。
- 环线/局部搜索（T2.6）、persona 软混合——后端侧未做，前端不涉及。
