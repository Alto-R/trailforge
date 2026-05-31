# TrailForge（Vispath 2.0）— 户外个性化游线推荐系统

> **范围**：北京登山（climbing）单活动　**当前状态**：研究主线（混合 CF）已闭环并完成决定性验证；工程主线（后端 API / 前端 demo）尚未启动
> **仓库**：[Alto-R/trailforge](https://github.com/Alto-R/trailforge)　**配套文档**：《户外个性化游线推荐系统：研究与原型开发计划》主文档 + 执行手册（见上级目录）
> **快照日期**：2026-05-31（里程碑与状态请以 [reports/PROGRESS.md](reports/PROGRESS.md) 为准）

---

## 1. 这是什么

从六只脚户外社区的 GPS 轨迹与图文，重建用户–步道片段交互，构建用户表示（行为聚类 + LLM 文本画像）与片段表示（地理 / 视觉 / 行为三层），训练**双塔 + 显式协同因子 + 自适应融合系数的混合协同过滤模型**，并在其上做规则版路径生成。目标是把"研究结论"和"可演示 demo"两条线都跑通——当前研究线已闭环，工程线待启动。

**一句话研究结论**：协同与内容信号的强弱**取决于人群密度**——活跃用户域协同主导（内容≈流量基线）、冷启动域协同失效（内容塔决定性有用，2.5×），带自适应 α 的混合模型是唯一两域都稳健的方案。详见 [reports/进展汇报_2026-05.md](reports/进展汇报_2026-05.md)。

---

## 2. 主要进展里程碑

> 维护约定见 §7。每完成一个里程碑或每月，在本表追加一行；细节落到对应的 `reports/` 文档。

| 日期 | 里程碑 | 关键结果 | 文档 |
|---|---|---|---|
| 2026-05 | **D0.1 数据清点** | 数据可用性全通过；坐标系定 Krasovsky Albers；原图不可得 → 弃 CLIP 改用彭晓场景标签 | [data_inventory.md](reports/data_inventory.md) |
| 2026-05 | **D0.2 交互矩阵重建** | 1,594,250 条 (用户,片段,季节) 交互、3,630 用户；与旧截断 csv 交叉校验召回 0.972 | [D0.2_interaction_matrix.md](reports/D0.2_interaction_matrix.md) |
| 2026-05 | **D0.4 步道图 TrailGraph** | 平均度 2.14；**网络天然分裂为 610 个连通分量**（最大 4,478 段），snap 0.5–10m 不变；8/8 测试通过 | [D0.4_geom_graph.md](reports/D0.4_geom_graph.md) |
| 2026-05 | **D0.3 / T2.1 用户聚类** | 清洗 572 条损坏行程后 603 用户，GMM 按 BIC 选 **K=5**；修复了清洗前的两个伪聚类 | [D0.3_user_clustering.md](reports/D0.3_user_clustering.md) |
| 2026-05 | **D0.5 视觉层 + T1.2 划分** | 彭晓 538k 点 → 54 维 s_visual（覆盖 30.7%）；每用户时间维 80/20 划分 | [D0.5_visual_split_clean.md](reports/D0.5_visual_split_clean.md) |
| 2026-05 | **D0.6 / T2.3 特征表示组装** | 片段表示 s=83 维（geo19;vis53;beh11）、用户表示 u=24 维（cluster5;LLM18;flag1） | [D0.6_segment_repr.md](reports/D0.6_segment_repr.md) |
| 2026-05 | **T0.2 / T2.2 LLM 画像** | split-half 一致性中位 **0.901 通过**；586 画像 0 失败；活跃域离线增益≈0 | [T0.2_llm_profile_result.md](reports/T0.2_llm_profile_result.md) · [T2.2_ullm_gain.md](reports/T2.2_ullm_gain.md) |
| 2026-05 | **T2.4 / T2.5 混合 CF 对照矩阵** | E0–E6 完整对照：活跃域纯协同 E1 最佳 0.516、自适应 E4 0.508、内容≈流量基线 | [T2.5_cf_matrix.md](reports/T2.5_cf_matrix.md) |
| 2026-05 | **T2.5 冷启动专项（决定性结果）** | 活跃域结论反转：协同 0.182（≈随机）、内容 0.457（2.5×）、自适应 E4 0.449 两域都稳 | [T2.5_coldstart.md](reports/T2.5_coldstart.md) |
| 2026-05 | **T1.5 规则版路径生成器** | best-first DFS，不同偏好从同一起点生成可区分的 ~4km 路线 + WGS84 GeoJSON | [T1.5_route_generator.md](reports/T1.5_route_generator.md) |
| 2026-05 | **T2.7 多 seed 显著性 + 冷启动消融** | 活跃域误差棒(std≈0.002)、E1>E4 显著(p<1e-3)；冷启动反转高度显著(p=1.5e-5)；**消融定位：u_LLM/视觉在冷启动也 ROI≈0**，真正工作层是 GMM 聚类+geo/behavior | [T2.7_significance_ablation.md](reports/T2.7_significance_ablation.md) |

**阶段进度速览**（详见 [reports/PROGRESS.md](reports/PROGRESS.md) §1）：Phase 0 预探索 ✅~90% · Phase 1 数据/规则 🟡~55%（后端/前端未起）· Phase 2 算法核心 ✅~90% · Phase 3 整合测试 ⬜0%。

---

## 3. 仓库结构

```
trailforge/
├── config.py                # 全局路径与常量（G: 盘原始数据 → data_processed/），含 .env 加载
├── environment.yml          # conda 环境（python 3.11 + geopandas/sklearn/...）
├── src/                     # 数据处理与算法模块（每个文件头有 docstring + "Run:" 行）
│   ├── interaction.py       # D0.2 交互矩阵重建
│   ├── split.py             # T1.2 时间维 80/20 划分 + 脏行程清洗
│   ├── trail_graph.py       # D0.4 段级邻接表 + 连通分量 + 最短路/子图接口
│   ├── visual_features.py   # D0.5 彭晓场景标签 → s_visual（直方图归属）
│   ├── user_features.py     # D0.3/T2.1 14 维行为元特征 + GMM/BIC 聚类
│   ├── llm_profile.py       # LLM 画像 18 维 schema + DeepSeek 调用 + 缓存
│   ├── llm_run_t02.py       # T0.2 split-half 一致性测试
│   ├── llm_extract_all.py   # T2.2 批量画像提取 → u_LLM
│   ├── segment_repr.py      # D0.6 片段表示 s=[geo;visual;behavior]=83
│   ├── user_repr.py         # T2.3 用户表示 u=[cluster;LLM;flag]=24
│   ├── cf_model.py          # T2.4 双塔 + 协同 + 自适应α 模型定义
│   ├── cf_train.py          # T2.4/T2.5 训练 + E0–E6 评估（地理感知负采样、BPR）
│   ├── cf_coldstart.py      # T2.5 冷启动专项评估（20% 用户 hold-out）
│   └── route_generator.py   # T1.5 规则版路径生成器
├── notebooks/               # 审计与制图脚本（00 数据审计 / 01 交互摘要 / 02 几何视觉审计 / make_report_figures）
├── tests/                   # 单元测试（test_trail_graph.py，8 项）
├── figures/                 # 报告插图 fig1–3（.png/.pdf）
├── data_processed/          # 处理产物（gitignored，可从 G: 盘一键重建）
└── reports/                 # 进展文档与各任务总结报告 —— 见 §6 文档索引
```

---

## 4. 环境与复现

**环境**（conda）：

```bash
conda env create -f environment.yml      # 创建 trailforge 环境（python 3.11）
conda activate trailforge
# Phase 2 另需 pytorch（CF 模型），见 environment.yml 末尾注释
```

**前置**：原始数据为只读真值源，位于 `G:\游憩线路生成`（路径集中在 [config.py](config.py)）；DeepSeek API key 放入仓库根的 `.env`（`DEEPSEEK_API_KEY=...`，已 gitignored，切勿入库）。`data_processed/` 不入库，可由下列流水线从 G: 盘重建。

**复现流水线**（从仓库根运行；每个脚本文件头的 docstring 含确切 `Run:` 命令与参数，亦可 `--help`）：

```bash
python src/interaction.py            # D0.2 交互矩阵（--pilot 先做单文件逻辑自检）
python src/split.py                  # T1.2 清洗 + 80/20 时间划分
python src/trail_graph.py            # D0.4 TrailGraph + 邻接表
python src/visual_features.py        # D0.5 视觉层
python src/user_features.py          # D0.3 行为聚类（GMM/BIC）
python src/llm_run_t02.py            # T0.2 LLM 一致性测试（需 .env）
python src/llm_extract_all.py        # T2.2 批量 LLM 画像（需 .env，带缓存）
python src/segment_repr.py           # D0.6 片段表示 s=83
python src/user_repr.py              # T2.3 用户表示 u=24
python src/cf_train.py --configs E0,E1,E2,E3,E4,E6 --epochs 15   # T2.4/T2.5 矩阵
python src/cf_coldstart.py           # T2.5 冷启动评估
python src/route_generator.py        # T1.5 路径生成示例
python notebooks/make_report_figures.py   # 重生成报告插图
pytest tests/                        # 单元测试
```

> ⚠️ 若 `GaussianMixture` / `np.corrcoef` 在本机 conda 环境触发 MKL 原生崩溃（EXIT 127），设 `MKL_THREADING_LAYER=SEQUENTIAL`（已在相关脚本内固定，见 PROGRESS §5）。

---

## 5. 数据资产与核心结论（速览）

- **数据资产**（`data_processed/`，可重建）：交互 `interactions_climbing/train/test.parquet`、片段 `segment_features_climbing.parquet`(s=83) + `adjacency_climbing.pkl`、用户 `user_cluster_soft.parquet`(K=5) + `user_llm_profile.parquet`(18) + `user_features_repr.parquet`(u=24)。明细见 [reports/PROGRESS.md](reports/PROGRESS.md) §4。
- **混合 CF（活跃域，603 用户 / n_eval=101,870）**：E1 纯协同 R@10=0.516（最佳）、E4 自适应混合 0.508、E2 纯内容 0.475（≈流量基线 E0 0.478）。
- **冷启动域（20% hold-out，18,786 正样本）**：E1 协同暴跌至 0.182（≈随机）、E2 内容 0.457（2.5×）、E4 0.449（唯一两域都强）。
- 三条可发表结论与图表见 [reports/进展汇报_2026-05.md](reports/进展汇报_2026-05.md) 与 [figures/](figures/)。

---

## 6. 文档索引

| 类别 | 文档 | 用途 |
|---|---|---|
| **总进度（滚动）** | [reports/PROGRESS.md](reports/PROGRESS.md) | 唯一权威的实时进度总报告：阶段进度、决定性结果、决策与踩坑、下一步 |
| **阶段汇报（定期）** | [reports/进展汇报_2026-05.md](reports/进展汇报_2026-05.md) | 面向汇报的叙述性正式文档（按月/按阶段产出） |
| 数据清点 | [reports/data_inventory.md](reports/data_inventory.md) | D0.1 原始数据核验与决策 |
| 模块总结 | `reports/D0.2_*` `D0.3_*` `D0.4_*` `D0.5_*` `D0.6_*` | 各数据处理交付的总结说明 |
| 模块总结 | `reports/T0.2_*` `T2.2_*` `T2.5_*` | LLM 画像、增益、CF 矩阵、冷启动的总结说明（含 `.csv` 指标） |
| 模块总结 | [reports/T1.5_route_generator.md](reports/T1.5_route_generator.md) | 规则版路径生成器（算法 / 约束 / demo / 待办） |
| 模块总结 | [reports/T2.7_significance_ablation.md](reports/T2.7_significance_ablation.md) | 多 seed 显著性 + 冷启动域内部消融（均值±std / p 值 / 哪层内容有用） |
| 上级计划 | `../vispath2_project_plan.md` · `../vispath2_execution_handbook.md` | 研究与原型开发主文档 + 执行手册 |

---

## 7. 文档维护约定（过程管理）

为便于后续整理成果、撰写正式文档，本仓库遵循以下分工与节奏：

1. **README.md（本文件）= 入口 + 里程碑 + 索引。** 每完成一个里程碑、或每月，更新 §2 里程碑表与顶部状态行；只放结论与链接，不堆细节。
2. **`reports/PROGRESS.md` = 滚动总进度（唯一权威实时态）。** 每个交付（D/T 任务）完成后即更新其阶段进度表、结果、决策/踩坑、下一步。
3. **`reports/进展汇报_YYYY-MM.md` = 定期叙述性正式汇报。** 按月或按阶段产出，面向对外汇报，可直接复用为论文/报告素材。
4. **`reports/<交付ID>_<主题>.md` = 模块总结说明文档。** **每个数据处理或算法模块迭代告一段落、基本稳定后**，按既有范式（标题 → 链接到源码 → 关键数字表 → 结论 → 待办）补一篇；命名沿用计划中的交付编号（如 `D0.x_*` / `T2.x_*`）。指标数据另存同名 `.csv`。
5. **代码自带轻量文档。** 每个 `src/*.py` 文件头写明用途、输入输出与 `Run:` 命令，与上述报告互为索引。

> 原则：**写一次、就近放、可链接、勿重复**——细节归各任务报告，进度归 PROGRESS，里程碑与导航归 README。
