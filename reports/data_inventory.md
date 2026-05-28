# D0.1 数据清点与核验报告


## 1. 登山-春 50m 中心线（邓钰桥 demo）
- **path**: G:\游憩线路生成\2.相关代码及说明\线路推荐demo(邓钰桥)\data\clim_春_centerline_50m_line_fix_AllMessage.shp
- **exists**: True
- **crs**: PROJCS["Krasovsky_1940_Albers",GEOGCS["Unknown datum based upon the Krassowsky 1940 ellipsoid",DATUM["Not_specified_based_on_Krassowsky_1940_ellipsoid",SPHEROID["Krassowsky 1940",6378245,298.3,AUTHORITY["EPSG","7024"]],AUTHORITY["EPSG","6024"]],PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]],PROJECTION["Albers_Conic_Equal_Area"],PARAMETER["latitude_of_center",0],PARAMETER["longitude_of_center",105],PARAMETER["standard_parallel_1",25],PARAMETER["standard_parallel_2",47],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH]]
- **n_segments**: 29941
- **columns**: ['FID_clim_', 'Id', 'length', 'lypID', 'joincount', 'slope_mean', 'lypid_1', 'daily_life', 'man_made', 'natural', 'FID_1', 'FID_clim1', 'FID_clim_1', 'Id_1', 'length_1', 'lypID_12', 'BUFF_DIST', 'ORIG_FID', 'FID_BDpoi_', 'F1', 'index', 'cluster', '地名', 'xid', '景点名', '经度', '纬度', '评论数', '84经度', '84纬度', '实际评', '饮食购', '娱乐活', '住宿', '票', '交通', '环境', '气氛', '人', '价格', '体验', 'OBJECTID', 'xid_1', 'FREQUENCY', 'MEAN_score', 'MEAN_emo_L', 'BUFF_DIS_1', 'ORIG_FID_1', 'length_n', 'joinc_mean', 'ziran_mean', 'geometry']
- **geom_types**: {'LineString': 29941}

## 2. 交互链 lypid_userid_tripid.csv（截断核实）
- **path**: G:\游憩线路生成\2.相关代码及说明\线路推荐demo(邓钰桥)\data\lypid_userid_tripid.csv
- **n_rows**: 1,048,575
- **== 1,048,576 (Excel 上限)?**: False
- **columns**: ['lypID', 'ORIG_FID', 'tripid', 'userid']
- **n_unique_userid**: 2,832
- **n_unique_tripid**: 6,458
- **n_unique_lypID**: 26,933
- tail (看 tripid 是否在尾部突然中断):
```
         lypID  ORIG_FID   tripid  userid
1048567  27012     27012  1249900  134211
1048568  27012     27012  1290242  248438
1048569  27012     27012  1290243  248438
1048570  27012     27012  1301262  257163
1048571  27012     27012  1577269  144697
1048572  27012     27012  1603458  904834
1048573  27012     27012  1615741  638747
1048574  27012     27012  1617832  862712
```

## 3. 登山-春属性表 北京登山中心线_春.xls
- **path**: G:\游憩线路生成\2.相关代码及说明\线路推荐demo(邓钰桥)\data\北京登山中心线_春.xls
- **shape**: (29941, 9)
- **columns**: ['FID', 'length', 'lypID', 'joincount', 'slope_mean', 'MEAN_score', 'MEAN_emo_L', 'joinc_mean', 'ziran_mean']
```
                FID        length         lypID     joincount    slope_mean    MEAN_score    MEAN_emo_L    joinc_mean    ziran_mean
count  29941.000000  29941.000000  29941.000000  29941.000000  29941.000000  29941.000000  29941.000000  29941.000000  29941.000000
mean   14970.000000     52.301120  14970.000000     36.871815     24.395481      0.217884      0.260436      0.716722      0.066571
std     8643.366541      8.921976   8643.366541     55.332562     11.889512      0.920106      1.100902      1.158005      0.194284
min        0.000000     10.000000      0.000000      0.000000      0.000000      0.000000      0.000000      0.000000      0.000000
25%     7485.000000     50.000000   7485.000000     12.000000     17.183385      0.000000      0.000000      0.240000      0.000000
50%    14970.000000     50.000000  14970.000000     19.000000     25.424403      0.000000      0.000000      0.360000      0.020000
75%    22455.000000     50.000000  22455.000000     36.000000     32.781873      0.000000      0.000000      0.700000      0.060000
max    29940.000000     99.499622  29940.000000    606.000000     69.576865      4.833333      7.000000     37.300000      5.500000
```

## 4. 基础中心线（未切 50m）：登山 / 徒步
- **climbing exists**: True  (bj_clim_centerline.shp)
- **climbing crs / n / cols**: EPSG:4024 / 0 / ['Id', 'geometry']
- **hiking exists**: True  (bj_hiking_centerline.shp)
- **hiking crs / n / cols**: EPSG:4024 / 0 / ['Id', 'geometry']

## 5. 登山 夏/秋/冬 的 50m 切片 + 属性是否存在
- **found seasonal/50m files**: 13
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_clim_50m_below49_points_2.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_clim_50m_buffer.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_clim_50m_buffer_joincount2.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_clim_50m_line.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_clim_50m_line_fix3.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_clim_50m_points.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_hiking_50m_below49_point.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_hiking_50m_buffer3.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_hiking_50m_buffer_joincount2.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_hiking_50m_line.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_hiking_50m_line_fix2.shp
  - G:\游憩线路生成\1.sixfoot全部相关数据\六只脚基本数据\处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）\线数据\北京地区的处理数据\轨迹中心线提取\bj_hiking_50m_points.shp
  - G:\游憩线路生成\2.相关代码及说明\线路推荐demo(邓钰桥)\data\clim_春_centerline_50m_line_fix_AllMessage.shp

## 6. 彭晓 图片深度学习成果 lzj_youxiao.shp
- **path**: G:\游憩线路生成\1.sixfoot全部相关数据\图片深度学习成果数据-京津冀（彭晓）\lzj_bj_youxiao\lzj_youxiao.shp
- **exists**: True
- **crs**: EPSG:4326
- **n_points**: 538848
- **columns**: ['pid', 'lng', 'lat', 'main_cla', 'med_cla', 'fine_cla', 'date', 'year', 'month', 'week', 'id_806677', 'geometry']
- head:
```
   pid         lng        lat         main_cla med_cla           fine_cla       date  year  month week  id_806677
0   81  115.761053  40.004303          manmade      HB  synagogue/outdoor 2018-03-18  2018      3   周日        NaN
1   82  115.764848  40.024404          natural      MT      mountain_path 2018-03-18  2018      3   周日        NaN
2   83  115.762959  40.024420          natural      MT  desert/vegetation 2018-03-18  2018      3   周日        NaN
3   89  115.755568  40.038083  natural&manmade      TP        desert_road 2018-03-18  2018      3   周日        NaN
4   90  115.755894  40.037876          natural      MT             canyon 2018-03-18  2018      3   周日        NaN
```

## 7. 高德 POI 地理数据库 (.gdb)
- **path**: G:\游憩线路生成\3.其他数据\高德POI-京津冀\京津冀merge_poi_分类型.gdb
- **exists**: True
- **n_layers**: 1
- **layers**: ['poi_class_merge']

## 8. 原始六只脚 track / footprints / basic 抽样
- **SIXFOOT_RAW exists**: True
- **#track shp (sample)**: 32 found
- **#footprints shp**: 32 found
- **#basic xlsx**: 64 found
- **track sample**: track120001_147850.shp
- **track crs / cols**: None / ['tripid', 'geometry']
- **footprints sample**: footprints120001_147850.shp
- **footprints cols**: ['pic', 'title', 'tripid', 'geometry']
- **basic sample**: basic120001_147850.xlsx
- **basic cols**: ['Unnamed: 0', 'description', 'location', 'title', 'tripid', 'triptime', 'triptype', 'userid', 'username']

## 9. 原始照片是否已下载到本地
- **photos found**: ❌ 未发现本地图片文件 → CLIP 路线需先用 crawler/download.py 下载，或改用彭晓成果

---

## 结论与对计划的影响（D0.1 决策）

**数据可用性：全部通过。** 原始轨迹、用户ID+文字、照片语义、POI 全部就位。

1. **交互链确认被截断** —— `lypid_userid_tripid.csv` 共 1,048,576 行（表头 + 1,048,575 数据）= Excel 行上限；尾部停在 `lypID=27012`，而片段实际到 `29940`，约 2900 段的交互缺失。→ **必须从原始轨迹重建（D0.2）**，旧 csv 仅作交叉校验。

2. **坐标系定板：Krasovsky_1940_Albers（G 盘现成）。** 50m 片段已是该 Albers（米制）；原始 track 为未投影 WGS84，彭晓照片为 EPSG:4326。→ 分析统一到 Albers；track/照片在做空间归属前 reproject 到 Albers。**放弃**计划里建议的 UTM 50N，避免重投影已处理好的片段。

3. **“登山全季节”无需重新切片几何。** 季节只影响**行为层**（流量/通过率）与天气，**不影响片段几何**。全登山 50m 网络已存在（`bj_clim_50m_line_fix3.shp` 等），春季 `..._AllMessage.shp`（29941 段，属性齐全）是春季预计算版。→ 用全登山 50m 网络作基础几何 + 按 `triptime` 分季节统计行为，即得全季节，无需重生成夏/秋/冬中心线。

4. **视觉层改用彭晓成果，近期不跑 CLIP。** 本地无原始图片（530k+ 需下载）；彭晓已产出 **538,848 个带 geotag 的照片点**，含场景分类 `main_cla/med_cla/fine_cla`（如 natural/MT/mountain_path、canyon）+ `date/year/month`。→ D0.5 先用彭晓分类作 `s_visual` 与情境信息；CLIP 仅在彭晓粒度不足时再考虑。

5. **片段属性已相当丰富。** demo 片段 shp 直接含 `slope_mean / joincount / joinc_mean / ziran_mean / MEAN_score(POI百度评分) / MEAN_emo_L(POI情绪) / natural/man_made/daily_life / cluster` 及大量 POI 维度字段 → `s_geo`+部分 `s_behavior` 可直接复用。

**待办微调**：`bj_clim_centerline.shp` / `bj_hiking_centerline.shp` 读出 0 要素（空/占位）；可用的全登山几何是 `bj_clim_50m_line_fix3.shp`（D0.2 开始前核验其要素数与字段）。
