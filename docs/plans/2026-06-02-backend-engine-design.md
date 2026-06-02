# 工程线设计 —— 后端 CF 个性化路线服务（+ 前端 demo）

**日期**：2026-06-02　**状态**：已修订 —— 见末尾《修订 R1：转向探索辅助形态》。§1–7 是初版（单条 CF 个性化路线）的设计，**因下述关键发现已被 R1 取代产品形态**，保留作演进记录。
**范围**：北京登山单活动；把已闭环的研究成果做成可演示 demo（Phase 1 工程线 / PROGRESS §7 高优）

---

## 1. 一句话功能（通俗版）

**用户在地图上点一个起点、选一下自己是哪种登山者，系统就生成一条专属徒步路线。**

流程：前端开局问"你是哪种登山者？"（5 个 persona，源自 GMM K=5 真实人群聚类）→ 用户选一个 + 拖滑块定"想走多远" + 在地图点起点 → 后端给地图上每段步道打分（这类人有多对胃口）→ 从起点贪心长出一条到目标公里数的路线 → 地图画出来。

**为什么这么设计**：故意做"全新用户从零开始"这个最难场景，直接演示研究里最硬的结论——对无历史的冷启动用户，内容塔（猜他像哪类人）效果是随机协同的 **2.5×**（冷启动域 0.457 vs 0.182）。

---

## 2. 关键设计决策（brainstorming 结论）

| # | 决策点 | 选定方案 | 含义 |
|---|---|---|---|
| 1 | 推荐引擎 | **CF 个性化（T2.6）**，MVP 只做"CF 化"，环线闭合 + 局部搜索推迟 | 后端服务"CF 评分的路径生成器" |
| 2 | 用户模型 | **新用户 onboarding / 内容塔（冷启动域）** | 走内容塔通路，无 `u_id` 协同嵌入 |
| 3 | 冷启动映射 | **persona 选择（直接用 K=5 聚类）** | 选 persona → 构造 `u_feat` |
| 4 | 技术栈 | **FastAPI**（Pydantic 校验 + OpenAPI 文档 + 异步；全新自写，不碰 Vispath 1.0） | 启动时加载一次模型常驻 |

---

## 3. 数据源澄清 —— 步道网来自 GPS 轨迹，**不是**北京路网

> 2026-06-02 讨论中确认，记录备查。

**结论**：地图上的"北京步道网"用的是登山步道网（从六只脚 GPS 轨迹来的产物），**不是 OSM/高德那种市政路网**。

几何基准 = `clim_春..._AllMessage.shp`（29,941 段、52 字段，含 slope_mean / 场景标签 / cluster / POI），见 [reports/D0.4_geom_graph.md](../../reports/D0.4_geom_graph.md)。三条佐证：

1. **ID 与轨迹交互矩阵对齐**：段 ID `lypID` 与 D0.2（从 GPS 轨迹重建的"用户–步道片段交互"）几乎 1:1（29,934/29,941）。每段就是被人走过的那段步道。
2. **天然碎成 610 个互不相连片区**：对应西山/香山/八达岭等独立山块，snap 0.5→10m 不变（真实属性，非伪影）。市政路网会是一张大连通图，不会这样碎。
3. **"北京"命名的 `bj_clim_50m_line_fix3.shp` 反被弃用**（裸几何、无属性、ID 空间不一致），且同为 "clim" 登山专用、非通用路网。

**前提**：该 shapefile 是上游（彭晓/Vispath 旧）流水线**已预处理好的产物**，本仓库直接采用，未从裸轨迹重切。

**对 demo 的影响**：
- ✅ 每段都是真人实走的路 → 生成真实徒步路线，不会导到机动车道。
- ✅ "一条路线待在一个山头"是正确行为（受限于单连通分量），非 bug。
- ⚠️ 覆盖只在有 GPS 轨迹的地方；没轨迹的山没有路。
- ⚠️ 无 DEM → 段的高程/爬升缺失，坡度仅 `slope_mean`。

---

## 4. 架构与代码落点

```
src/
  cf_export.py        # 新：全量训练 E4 → 保存 e4.pt + e4_meta.json
  route_generator.py  # 改：_reward 支持注入 CF 内容塔打分（保留规则版兜底）
  persona.py          # 新：5 个 GMM 聚类 → 可解释 persona 标签 + u_feat 构造
backend/              # 新：FastAPI 应用（全新自写）
  app.py              # 入口 + 启动时加载模型/图/特征
  schemas.py          # Pydantic 请求/响应模型
  engine.py           # persona→u_feat→内容塔评分→route_generator 串联
  tests/              # 后端测试（先写，再写前端）
```

模型产物 `e4.pt` / `e4_meta.json` 存 `data_processed/`（gitignored，可重建）。

---

## 5. CF 个性化引擎

`u_feat` 精确布局（24 维，顺序即列序，见 [src/user_repr.py](../../src/user_repr.py)）：
`u_cluster_0..4`（5，GMM 软分配）+ `llm_*`（18）+ `has_llm_profile`（1）。

- **① `cf_export.py`**：全量活跃用户训练 E4（content+collab+adaptive_alpha）→ 存 `e4.pt`（state_dict）+ `e4_meta.json`（`feat_cols` 顺序、`llm_*` 列均值、片段特征归一化参数）。
- **② `persona.py`**：从 5 个 GMM 质心在 14 维行为特征上的判别项自动生成 persona 标签草稿（人工润色）。选 persona k →
  `u_feat = [cluster one-hot k (5); llm 列均值 (18); has_llm=0]`
  —— **完全复用 user_repr.py 现有的冷用户编码**（列均值填充 + flag=0），保证 in-distribution。
- **③ 评分**：启动时对全部片段预计算 `g_s(s_feat)` → 矩阵 `S[n_segs, d]`。给定 persona：`g_u(u_feat)` → `[d]`，与 `S` 点积 → 每段得分 → 注入 `RouteGenerator._reward`，从起点按预算长出路线。
- **④ 忠实性**：这是 E4 的内容塔通路（新用户无 `u_id`），即冷启动域 0.457（协同 2.5×）的场景。

---

## 6. API 契约（MVP 4 个接口）

- **`GET /personas`** → 5 个 persona 的 `id/label/description/size`，前端渲染选项。
- **`POST /route`**（核心）
  - 请求：`{ start: [lng,lat], persona: "hardcore", budget_km: 5.0 }`
  - 响应：`{ length_km, n_segments, start_snapped:[lng,lat], geojson:{…}, summary:{…} }`
  - 边界：起点附近无路/落在小孤岛凑不满公里数 → **明确返回"本区最多 ~Xkm"**，不偷偷返回残缺路线。
- **`GET /trails`** → 步道网 GeoJSON（地图淡显，引导用户往有路处点；因 610 碎片，起点决定可达范围）。
- **`GET /health`** → 模型加载就绪状态。

---

## 7. 测试策略（全真数据 + 真模型，无桩）

约定：**整个后端实现完成且测试全绿后，再写前端**；写前端前用 skill 与用户讨论。**节奏：每板块先写实现、跑通，再补测试验收（非 TDD）。**

原则：测试读 `data_processed/` 里的**真产物**，不碰 G: 盘、不重训（训练只在板块 A 跑一次存盘，测试只 `load`）。桩测试能过、真流水线却挂的坑（特征列序 / 归一化 / NaN 段 / 610 连通分量）必须被真数据覆盖。

- **session 级 fixture**：模型 + parquet 等重物整轮只加载一次，所有用例共享（首次约几秒，之后秒级）。
- **真产物来源**：图 `adjacency_climbing.pkl`、特征 `segment_features_climbing.parquet`、几何 `segment_geom_climbing.parquet`（板块 A 新建）、用户表示 parquet、模型 `e4.pt` + `e4_meta.json`（板块 A 产出）。
- **纯逻辑单测**（`u_feat` 维度/列序）只需 `e4_meta.json`，瞬时，仍是真列均值。
- **边界用例在真图上测**：凑不满公里数 → 挑一个已知小孤岛连通分量起点；persona 可区分 → 两个对比强烈 persona + 一个真起点断言路线不同。
- **跑测**：`PYTHONNOUSERSITE=1 PYTHONUTF8=1 D:/Anaconda/envs/trailforge/python.exe -m pytest backend/tests -v`。

**顺序约束**：engine/API 测试依赖 `e4.pt` 与几何缓存 → **板块 A 必先跑**。每板块**先写实现、跑通，再补测试验收**（非 TDD）。例：板块 A 先实现 `cf_export` 跑出 `e4.pt`/`e4_meta.json` + 几何缓存，再补测试断言（产物存在、能 `load`、`g_s` 全片段输出有限、形状 `[n,d]`）。

---

## 8. 待办 / 推迟项

- T2.6 环线闭合 + 局部搜索（MVP 不做）。
- onboarding persona 软混合（MVP 先单选）。
- 现有用户/协同塔通路（本期不做，只做冷启动内容塔）。

---

## 9. 过程约定

- 每完成一个板块 → 更新 README 里程碑 + PROGRESS + 模块总结报告 → 推 GitHub（提交不署 Claude 为 co-author）。
- Python 统一用 D 盘 anaconda `trailforge` conda env。

---

# 修订 R1（2026-06-02）：转向探索辅助形态

## R1.1 触发：一个决定性的负面发现 —— E4 内容塔不个性化

初版打算"persona→内容塔评分→单条个性化路线"。实现并跑通后，诊断发现：

- **g_u 把所有用户映射成几乎同一个嵌入**：5 个 persona 的 one-hot 两两 cosine 0.999–1.0；**真实 603 用户**（真实软 cluster+llm）两两 cosine 均值 0.9995。
- **评分向量两两 Pearson = 1.0** → 冷启动对所有用户给出**完全相同的段排序** → 5 个 persona 得到**同一条路线**、同一目的地（12 起点 × 5 persona 全同）。
- 模型没学到"cluster k ↔ 段 beh_cluster_k"匹配（c0 甚至 -0.325）。

**解读**：E4 的个性化全在**协同路径**（user_id 嵌入）；内容塔在冷启动只是个"按段流行度/特征"的**全局先验**。研究里"冷启动内容 2.5× 协同（0.457 vs 0.182）"应重述为 **"流行度/特征先验 > 随机未训练嵌入"，而非个性化推荐**。代码与测试全对，是模型性质本身否决了"单条随 persona 变形"的前提。

## R1.2 决策：按主计划 §4.5 的探索辅助形态（用户确认）

主计划 §4.5 早已定产品为**探索辅助而非精准推荐**，理由白纸黑字：*"即使 CF 预测有偏差，用户看到 3–5 条不同风格的路线也能找到合适的那条"*。即**计划预设了 CF 可能不精准**，用"多候选+排序+可解释"容错。上述发现**印证而非推翻**该选择。

**个性化信号来源（用户确认）：显式偏好 + CF 先验 + MMR**：
- **显式偏好**主导可见个性化：persona→默认偏好权重（数据派生，弱差异，主要在 popularity）+ 滑块可调。已验证 **challenge vs scenic+nature 在 19/20 起点走出不同路线**（PREF_MAP：challenge→坡度、nature→自然、scenic→打卡…）。
- **CF 段分**作相关性/质量先验（跨用户恒定，但学习式融合 83 维，超出 5 个手挑属性）。
- **MMR** 给多样性（计划 §5.4.5：候选池 50–100、Jaccard 距离、β=0.7、输出 top 3–5）。

## R1.3 新架构与接口（取代 §4–6 的单路线设计）

```
src/
  route_generator.py  generate_pool(start,budget,seg_scores,pool_size) 候选池
  diversifier.py      MMR（Jaccard，β=0.7）→ top n_routes
  explainer.py        每条候选 → 可解释标签（属性相对均值的突出项）
backend/
  engine.py           偏好(persona默认+滑块)·属性 + CF先验 → seg_scores
                      → 候选池 → MMR → 解释 → 候选列表
  schemas.py          RouteRequest{start,persona?,preferences?,budget_km,n_routes}
                      RouteResponse{candidates:[{length_km,segments,geojson,
                        attributes,labels,score,reachable}], start_snapped, note}
  feedback.py + /feedback   记录选了哪条 + 评分（jsonl，最小实现）
```

**`/route`（POST）** 入：起点[lng,lat]、persona（可选，给默认偏好）、preferences（可选，覆盖默认）、budget_km、n_routes(默认4)。出：3–5 条候选（每条含 GeoJSON/属性/可解释标签/分数），按相关度排序、MMR 去同质。
**`/personas`**：附 default_prefs。**`/trails`**、**`/health`** 不变。**`/feedback`（POST）**：{chosen_index, rating, comment?} → jsonl。

## R1.4 §5.1.1 特征族偏离（如实记录）

主计划 §5.1.1 列的 `ascent_mean`/`exploration_ratio`/`type_entropy`/`intensity_cv` **未按原样实现**：无 DEM→无爬升项；单活动→无类型熵；改用 `dist_cv`/`start_compactness`/`coverage_breadth`/`daypart_entropy` 等近义替代。原因见 [src/user_features.py](../../src/user_features.py) 文件头与 D0.3。属**有据偏离**，非疏漏。

## R1.5 测试策略（沿用 §7 全真，调整断言）

仍全真数据+真模型、session fixture。断言改为：`/route` 返回 2–5 条候选；候选间 Jaccard 有差异（MMR 生效）；**不同 preferences → 候选集不同**（个性化可见，替代原"不同 persona 不同路线"——后者已知对 CF 无效）；每条含 labels 非空；不可达起点 reachable=False。persona/几何/连通性等不变。
