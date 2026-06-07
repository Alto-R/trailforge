# Vispath 2.0 / TrailForge —— 项目进度总报告

**日期**：2026-06-02　**仓库**：[Alto-R/trailforge](https://github.com/Alto-R/trailforge)　**范围**：北京登山（climbing）单活动
**配套**：《户外个性化游线推荐系统：研究与原型开发计划》主文档 + 执行手册

---

## 0. 一句话现状

**研究主线（混合 CF）已闭环并得到决定性验证；工程主线后端 `/route` 服务已交付（探索辅助形态，27 测试全绿），只差前端交互。**
数据资产、用户/片段表示、混合 CF 模型与完整对照实验（含冷启动）全部就位。后端把成果做成 FastAPI 服务（[T1.1](T1.1_backend_recommender.md)）。**过程中得到一个决定性工程发现：E4 内容塔不个性化（见 §2.4），据此按主计划 §4.5 转为探索辅助形态**——多候选 + 显式偏好排序 + MMR 多样性 + 可解释标签 + 反馈。**前端 demo（[T1.6](T1.6_frontend.md)）已交付并全栈实测跑通，工程线闭环、可演示。**

---

## 1. 相对计划的阶段进度

| 阶段 | 计划内容 | 进度 | 说明 |
|---|---|---|---|
| **Phase 0** 预探索 | T0.1–T0.5 + M1 | ✅ ~90% | 见 §3。CLIP 验证(T0.3)以"原图不可得→改用彭晓"结案；后端走读(T0.5)因改为全新自写而取消 |
| **Phase 1** 基础+数据 | 后端重构/数据资产/规则 demo | ✅ ~95% | 数据资产 + 路径生成器 ✅；**后端 `/route` 服务(T1.1) ✅（探索辅助，27 测试绿）**；**前端 demo(T1.6) ✅（Vite8+React19+deck.gl，全栈实测、9 测试+构建绿）** |
| **Phase 2** 算法核心 | 用户表示/CF/评估 | ✅ ~95% | 用户表示、片段表示、混合 CF、E0–E6 矩阵、冷启动、**5-seed 显著性+冷启动消融(T2.7)** 全部完成；路径生成器 CF 化+环线(T2.6)待做 |
| **Phase 3** 整合测试 | 集成/用户测试 | ⬜ 0% | 依赖工程主线 |

> **关键判断**：研究目标已接近达成（核心算法验证完毕、有可发表结论）；产品目标（demo）已可演示——后端 `/route` + 前端探索辅助界面全栈跑通。下一步转向 Phase 3 小规模用户测试与 T2.6 路径生成器 CF 化/环线。

---

## 2. 决定性研究结果（本项目的核心产出）

### 2.1 混合 CF 完整对照矩阵（活跃用户域）

603 个活跃用户、s=83 维、u=24 维、地理感知负采样、BPR、100 路排序、n_eval=101,870。

| 模型 | Recall@10 | NDCG@10 |
|---|---|---|
| E0 popularity（非个性化） | 0.478 | 0.374 |
| E2 纯内容 | 0.475 | 0.344 |
| E3 混合 α=0.7 | 0.496 | 0.369 |
| E6 混合无视觉 | 0.498 | 0.373 |
| **E4 混合自适应 α** | **0.508** | **0.389** |
| **E1 纯协同** | **0.516** | **0.392** |

### 2.2 冷启动专项评估（决定性反转）

20% 用户完全 hold-out，在其测试正样本（18,786 条）上评估：

| 模型 | 冷用户 R@10 | 活跃用户 R@10 |
|---|---|---|
| E1 纯协同 | **0.182**（≈随机） | 0.516（最佳） |
| E2 纯内容 | **0.457** | 0.475 |
| **E4 自适应混合** | **0.449** | **0.508** |

### 2.3 三条可发表的结论

1. **协同 vs 内容的强弱取决于人群密度**：活跃域协同主导（E1 最佳），冷启动域协同崩溃（0.182≈随机）、内容塔接管（0.457，2.5×）。
2. **自适应 α(u,s) 两域鲁棒**：E4 学到 w1<0（高活跃用户偏协同），活跃 0.508 / 冷启动 0.449，**唯一两域都强**→ 生产首选。
3. **内容侧组件 ROI≈0（两域均成立，T2.7 加强）**：LLM 画像(E3≈E5)、彭晓视觉(E6≈E3) 在活跃域边际增益≈0；**T2.7 多 seed 消融证明二者在冷启动域同样 ROI≈0**（去 u_LLM p=0.44、去视觉 p=0.10、两者都去 p=0.06，|Δ|≤0.004）。冷启动里真正有用的是内容塔的其余部分——**GMM 行为聚类 + geo/behavior**（u_cluster↔s_behavior 匹配）。即"内容塔整体对冷启动不可或缺，但其中昂贵的 LLM 提取与视觉层可去而近乎无损"。注：原"单看活跃域会误判砍内容、冷启动纠正之"仍成立——内容塔作为整体不可砍。

---

### 2.4 后端工程发现：内容塔不个性化（决定性，重述 2.3 之三）

把 E4 做成服务时诊断到：`g_u(任何用户) ≈ 同一常量向量`——5 个 persona 与**真实 603 用户**的 g_u 嵌入两两 cosine 均 ≈0.999，评分向量两两 Pearson=1.0，冷启动对所有用户给出**完全相同的段排序**（未学到 cluster↔beh_cluster 匹配）。

**含义**：E4 个性化全在**协同路径**；内容塔在冷启动只是"流行度/特征全局先验"。"冷启动内容 2.5× 协同"应重述为 **"流行度先验 > 随机未训练嵌入"，非个性化推荐**。据此后端按主计划 §4.5 转**探索辅助形态**：可见个性化由**显式偏好**驱动（验证 challenge vs scenic 19/20 起点出不同路线），CF 作先验，MMR 给多样性。详见 [T1.1](T1.1_backend_recommender.md)。

---

## 3. 各任务交付明细（D/T 对照）

| 交付 | 对应计划 | 产出 | 关键数字 |
|---|---|---|---|
| D0.1 数据清点 | T0.5 | [data_inventory.md](data_inventory.md) | 全部数据就位；CLIP 原图不可得 |
| D0.2 交互矩阵 | T1.2 | [interaction.py](../src/interaction.py) | 1.59M(user,seg,season)，3630 用户，recall 0.972 |
| D0.3 用户聚类 | T0.1/T2.1 | [user_features.py](../src/user_features.py) | 清洗后 603 用户，GMM **K=5** |
| D0.4 几何+图 | T1.0 | [trail_graph.py](../src/trail_graph.py) | 29,941 段，**610 连通分量**(最大 4478)，8/8 测试 |
| D0.5 视觉层 | T1.4' | [visual_features.py](../src/visual_features.py) | s_visual 54 维，**覆盖 30.7%** |
| T1.2 划分/清洗 | T1.2 | [split.py](../src/split.py) | 80/20 时间划分，剔除 572 损坏行程 |
| D0.6 片段表示 | T2.3 | [segment_repr.py](../src/segment_repr.py) | s=[geo19;vis53;beh11]=83 维 |
| T2.3 用户表示 | T2.3 | [user_repr.py](../src/user_repr.py) | u=[cluster5;LLM18;flag]=24 维 |
| T0.2 LLM 实测 | T0.2 | [T0.2_llm_profile_result.md](T0.2_llm_profile_result.md) | 一致性 **0.901 通过**（DeepSeek） |
| T2.2 批量 LLM | T2.2 | [llm_extract_all.py](../src/llm_extract_all.py) | 586 画像，0 失败；离线增益≈0 |
| T2.4 混合 CF | T2.4 | [cf_model.py](../src/cf_model.py)/[cf_train.py](../src/cf_train.py) | 双塔+协同+自适应α+BPR+地理负采样 |
| T2.5 评估 | T2.5 | [T2.5_cf_matrix.md](T2.5_cf_matrix.md)/[T2.5_coldstart.md](T2.5_coldstart.md) | E0–E6 + 冷启动 |
| T2.7 显著性+消融 | §7 高优 | [T2.7_significance_ablation.md](T2.7_significance_ablation.md) | 5-seed 误差棒/p 值；冷启动 u_LLM/视觉 ROI≈0 |
| T1.5 路径生成 | T1.5 | [route_generator.py](../src/route_generator.py) | best-first DFS，偏好可区分的 ~4km 路线 + GeoJSON |

---

## 4. 数据资产现状（`data_processed/`，从 G: 盘可重建）

- **交互**：`interactions_climbing/train/test.parquet`（80/20 时间划分）
- **片段**：`segment_features_climbing.parquet`(s 三层 83 维)、`segment_visual_climbing.parquet`、`adjacency_climbing.pkl`(TrailGraph)
- **用户**：`user_cluster_soft.parquet`(K=5)、`user_llm_profile.parquet`(18 维)、`user_features_repr.parquet`(u 24 维)、`user_text_climbing.parquet`
- **几何基准**：`clim_春..._AllMessage.shp`（29,941 段，Krasovsky Albers，52 字段）

---

## 5. 关键技术决策与踩坑记录

1. **CLIP 搁置 → 彭晓场景标签**：原图是 2019 爬虫的 foooooot.com URL，已不可得、未归档；彭晓成果只有标签无原图无 embedding。视觉层改用彭晓 538k 点的场景分类直方图（无需 GPU）。
2. **坐标系**：统一 Krasovsky Albers（弃 UTM 50N）。
3. **后端全新自写**：不参考 Vispath 1.0（弃旧单文件 Flask 包袱）。
4. **网络天然碎成 610 连通分量**（最大 4478 段/242km）——snap 0.5–10m 不变，是真实属性；路径生成被锁在单分量内（符合"一条路线一个山头"）。
5. **MKL native crash 修复**：`GaussianMixture`/`np.corrcoef` 的 BLAS 在本 conda env 崩（EXIT 127），已用 `MKL_THREADING_LAYER=SEQUENTIAL` 永久修掉。
6. **脏数据**：剔除 dist>50km/dur>24h 的 GPS 损坏行程（max 14,159km），修复 D0.3 cluster 6/7 离群。
7. **安全**：DeepSeek key 走 gitignored `.env`，仓库扫描确认未泄露。
8. **中文路径 + GDAL**：bash 启动 python 时文件系统编码非 UTF-8，GDAL 找不到 `G:\…\clim_春_…shp`（路径字节损坏）。修复：`PYTHONUTF8=1` 启动；并把片段质心缓存到 `data_processed/segment_centroids.parquet`，多 seed 运行不再读 shapefile。
9. **多 seed 提速**：向量化负采样里的 `np.isin` 每个 batch 重排 70 万正样本（1200+ 次/配置）→ 致命慢。改用 `searchsorted` 命中预排序正样本，**10×+ 提速**，5-seed×15-epoch 全量从不可行降到可后台跑完。

---

## 6. 已知局限

- **片段几何**：无 DEM → 无 ascent/descent/elevation；s_geo 地形项仅 length/slope_mean。
- **视觉覆盖**：仅 31% 片段有照片（has_visual 掩码兜底）。
- **评估**：~~单次运行~~ 已补 5-seed 显著性（[T2.7](T2.7_significance_ablation.md)：活跃域 std≈0.002、冷启动 std≈0.024，头部对比均有 p 值）；负样本为地理邻近（相对易）。
- **范围**：仅北京登山单活动单分量；徒步/骑行未展开。
- **路径生成**：规则版+无环线闭合；CF 化与局部搜索(T2.6)未做。

---

## 7. 下一步（按价值排序）

| 优先级 | 任务 | 价值 |
|---|---|---|
| ✅ 完成 | 多 seed(≥5) 显著性 + 冷启动域内部消融(去 u_LLM/视觉) → [T2.7](T2.7_significance_ablation.md) | 已补误差棒/p 值；**新发现：u_LLM/视觉在冷启动也 ROI≈0**，工作层是 GMM 聚类+geo/behavior |
| ✅ 完成 | **T1.1 后端 `/route` 服务**（探索辅助：显式偏好+CF先验+MMR+可解释+反馈，27 测试绿）→ [T1.1](T1.1_backend_recommender.md) | 研究成果已服务化；附决定性发现"内容塔不个性化"（§2.4） |
| 高 | **T1.6 前端**：地图起点点选 + 偏好滑块/persona + 候选列表面板 + 高亮 + 反馈 | 把后端服务变成可演示 demo |
| 中 | T2.6 路径生成 CF 化 + 环线 + 局部搜索 | 推荐路线接入个性化评分（注：CF 内容塔不个性化，意义需重估） |
| 中 | onboarding 冷启动映射（用 GMM 聚类做冷用户表示）+ 可解释标签 | 产品形态完整；u_LLM/视觉可作可选解释而非主信号 |

> 当前是一个**自然的阶段性收尾点**：研究核心已验证、可写 M3 review。建议下一步转向工程服务化，让 demo 跑起来。

---

## 附：提交历史（近 16 次）

```
67c6245 T2.5 cold-start: content tower validated (E2 0.457 vs collab 0.182)
7f14493 T2.5 matrix E0-E6: collab dominates active; adaptive-a best hybrid
22176c9 T1.5: rule-based route generator (best-first DFS)
a0c4dc1 T2.2 result: u_LLM ~0 offline gain (answers E5)
6e49457 T2.2: batch LLM extraction -> u_LLM
98a711f T2.5 + T0.2: CF baseline (E1/E2/E3) + LLM consistency pass
3e933f5 T2.4 + T0.2: hybrid CF + LLM profile harness
babb079 D0.6: assemble segment representation s=[geo;visual;behavior]
97bc870 T1.2/T2.1: trip cleaning + GMM re-cluster (K=8->K=5)
c9a1744 D0.5: 彭晓 visual layer + interaction split
b64027f D0.4: TrailGraph + adjacency (610 components finding)
6d450f8 D0.3 / 7183012 D0.2 / (D0.1 bootstrap)
```
