# 陆家嘴建筑数据与许可

本目录为上海陆家嘴小范围 OpenStreetMap 开放数据的本地演示副本。

- 来源：© OpenStreetMap contributors，https://www.openstreetmap.org/copyright
- 数据许可：Open Database License 1.0（ODbL），https://opendatacommons.org/licenses/odbl/1-0/
- 查询时间：见 manifest.json 的 extractedAt；这不是实时城市数据。
- 建筑范围：121.488–121.515°E，31.225–31.247°N。
- source.osm.json：Overpass 返回的原始建筑/部件；context.osm.json：原始道路、水域。
- buildings.geojson：经筛选、去除含详细部件的重叠外轮廓后的派生建筑数据，可用于复现。
- tileset.json、tiles/*.glb：上述数据生成的简化建筑 3D Tiles；context.png 为道路水域制图。
- 以上数据库及派生数据库按 ODbL 提供；应与模型一起保留原始数据和本说明，履行署名与同许可要求。
- facade.png 是本项目程序绘制的示意窗格，不是摄影纹理；程序绘制素材按 MIT 提供。

高度口径：119 条记录使用 OSM height；138 条按 building:levels × 3.2m 换算；874 条缺少高度和层数，采用12m示意高度。共1,131个建筑/部件，不能当作1,131栋独立楼宇。OSM 标注高度也未逐栋实测核验。模型最高632m。

几何范围内的闭合 way 可用；未恢复 relation 多边形内洞；未建精细幕墙、真实窗户、室内或真实屋顶结构。统一地面椭球高5m，可能与在线地形存在少量高程差，图层页可调整模型整体偏移。离线模式使用椭球面。

复现（从项目根目录）：
1. python tools/prepare_city.py
2. python tools/render_city_context.py（需要 Pillow）
3. node frontend/tools-build-city.mjs（需要现有 frontend/node_modules）

原始数据已保存。不要为每次启动调用 Overpass；下载脚本仅用于人工更新有限范围的快照。
