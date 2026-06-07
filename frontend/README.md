# TrailForge 前端 —— 探索辅助交互 demo（T1.6）

把已交付的后端 `/route` 探索辅助服务（[T1.1](../reports/T1.1_backend_recommender.md)）接成可演示的端到端 demo。
设计文档：[docs/plans/2026-06-07-frontend-demo-design.md](../docs/plans/2026-06-07-frontend-demo-design.md)。

单屏直玩：左栏 persona 预设 + 5 偏好滑块 + 目标里程，右侧大地图。点起点 → 即时出多条不同风格候选 → 拖滑块实时重算 → 卡片↔地图双向高亮 → 「选这条」+ 星级反馈。

## 技术栈

Vite 8 + React 19 + TypeScript 6；地图 `deck.gl 9 + maplibre-gl 5 + react-map-gl 8`（底图 carto positron 矢量瓦片）；状态用 React 自带 hook（`useRoute` 防抖 + 竞态），请求用原生 `fetch` 薄封装。无重组件库 / 无 redux。

> react-map-gl v8 按底图分包导入：本项目用 `import { Map } from "react-map-gl/maplibre"`。

## 运行

前端纯消费后端 5 接口，**先起后端再起前端**。

```bash
# 1) 后端（仓库根目录，trailforge conda env）
conda activate trailforge
MKL_THREADING_LAYER=SEQUENTIAL PYTHONUTF8=1 python -m uvicorn backend.app:app --port 8000

# 2) 前端（本目录）
npm install
npm run dev          # http://localhost:5173
```

Vite dev proxy 把 `/api/*` 转发到 `127.0.0.1:8000`（见 [vite.config.ts](vite.config.ts)）。改后端地址：设 `VITE_API_TARGET`（见 [.env](.env)）。

## 脚本

| 命令 | 作用 |
|---|---|
| `npm run dev` | 开发服务器（HMR） |
| `npm run build` | `tsc -b` 类型检查 + 生产构建到 `dist/` |
| `npm run preview` | 本地预览生产构建 |
| `npm test` | Vitest 单测（`api` URL/payload、`useRoute` 防抖、配色稳定） |

## 结构

```
src/
├── main.tsx / App.tsx        # 入口；App 持有共享状态、装配各组件
├── api.ts                    # 5 接口封装（GET /health /personas /trails, POST /route /feedback）
├── types.ts                  # 对齐 backend/schemas.py 的 TS 契约（编译期护栏）
├── palette.ts                # 候选配色（按返回顺序固定分配，色盲友好）
├── hooks/useRoute.ts         # 防抖触发 /route + AbortController 竞态（只采纳末次）
├── components/
│   ├── MapView.tsx           # deck.gl 图层（trails 底层 / 每候选一层 / 起点）+ 点选取坐标 + fitBounds
│   ├── ControlPanel.tsx      # 品牌头 + health + persona + 5 滑块 + 距离 + 状态
│   ├── PersonaPicker.tsx     # 5 张 persona 预设卡（点选填充滑块）
│   ├── CandidateList.tsx     # 候选卡列表（active=hovered??selected，其余淡化）
│   ├── CandidateCard.tsx     # 单卡：色点/里程/标签 chip/反馈星级
│   └── Banner.tsx            # 地图顶部 warn（不可达 note）/ error 浮条
└── styles/app.css            # "地形图田野手册"主题（栅格布局 + 响应式）
```

## 已知边界（与设计文档 §6 一致）

- 不做环线闭合 / 局部搜索（后端 T2.6 未做，前端不涉及）。
- 起点偏移虚线、窄屏抽屉的极致打磨从简（响应式可用即可）。
- `npm run build` 仅一条 chunk-size 警告（deck.gl + maplibre 体积固有），不影响运行。
