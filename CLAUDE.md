# RuriRipperImporter — 项目特化铁律

> 通用工程铁律继承 skill `ruri-engineering-discipline`,本文只放本仓特化。
> 条款与用户指令冲突或条款本身错 → 先改本文,再写代码。

## 🔴 0. 只有一条数据流

```
行的 payload(种子)
  └─► C#:StatementSources —— 每个游戏一个回调,认领自己的种子
        └─► core.statement.*(节点 / 网格 / 骨架 / 材质 / 贴图 / 形态键 / 动画)
              └─► Kernel/app/loading.py:load(放置) / perform(动画)
                    └─► Host.materialise / Timeline.play
```

- **输入只有种子。** 一行能被导入,是因为它 `ColumnRole.Payload` 列的值**就是**种子。
  面板里组合出来的选择(卡片 × 套装 × 槽位、地图 × 矩形 × 场景状态)也由 hook 拼出种子
  (发一张答案型数据集:`<前缀>.chara.seed`、`endfield.scene.placement_counts` 的 `seed` 列),
  py 侧**一个前缀都不拼**。
- **每个游戏的差异只在一处**:C# `StatementSources.Register(Source)` 的那一个回调,
  `StatementPlan? Source(string seed, CabTable map, StatementOptions options)`。
  认领不了的种子由内核默认解析(CAB 名 / 容器路径 / 容器文件夹)。
  py 侧**没有**任何「这个游戏怎么加载」的代码。
- **输出只有一个入口**:`loading.load(context, seeds, options)` 与
  `loading.perform(context, seeds, rig, options)`。浏览器的导入、名册的 Load、场景窗口、剧情舞台、
  UI 舞台的美术、动画浏览——全部是它俩;面板上的按钮是内核命令 `ruri.load` / `ruri.reveal`
  (`Kernel/app/browser.py`),不是各游戏自己的。
- **判据**:`grep -rn "materialise(\|\.play(" Kernel Game` 只命中 `Kernel/app/loading.py`。
  出现第二个加载函数、第二种「包 / 数据库」对象、或宿主里自己解析种子,即违规。
- 🛑 **片段不许单独读:先读角色骨骼,再读动画。** 片段的绑定只存骨骼路径的 CRC32,只有对着骨架
  才叫得出骨骼名;不给目标骨架,读出来的骨骼曲线全是 `path_0x<crc>_` 占位符——对不上任何骨骼,
  看起来就像「这个片段什么都没动」(判成没脸、动画不动、曲线全丢,先查这个)。所以
  `Statement.clips(paths=..., avatar=...)` 两个都是必填,读取器也拒收不带骨架的请求。
  Unity 里**不存在没有 avatar 的动画目标**:运行时就是把目标对象层级的可逆路径字符串算一次
  哈希来绑定片段的,`paths` 就是这份层级。(剧情舞台的替身 / 镜头还没接到场景集里被绑定的
  真实对象上,是已知待修。)

**加一个游戏 = 两件事,都不碰内核:**
1. hook 侧:发列表数据集(Payload 列 = 种子);种子不是 CAB/容器路径时,注册一个 StatementSource。
2. `Game/<产品名>/`:`GAME_MODULE` 声明页签 + 面板模块(`cast_panel.Panel` / 视图绑定到数据集)。
   面板只声明「列哪张表、按钮叫哪个命令」,没有加载代码。

## 🔴 1. 游戏逻辑一律不许写在 py 里

凡是「解析某游戏的表/名字/槽位/材质码/LOD 规则/闭包/资产发现/种子拼法」,一律实现在 hook:

```
D:\Ruri\Git\FractalTools\Ruri-RipperHook\Source\Ruri.GameHook   (每游戏的黑盒)
D:\Ruri\Git\FractalTools\Ruri-RipperHook\Source\Ruri.RipperHook (内核:statement、cabmap、数据集)
```

`Game/<游戏>/` 只放:**面板**(调用内核命令、绑数据集)+ **生成的着色栈**
+ 必要时 `Game/<游戏>/<宿主名>/` 的宿主投影(例如剧情导演只在有时间轴的宿主里存在)。
py 侧只经 `Kernel.bridge.session` 的四个动词拿**已经算好的结果**。

**为什么**:python 逐资产解析是分钟级、单线程、还要跨 CLR 边界来回搬数据;同一套逻辑在
C# 侧是秒级且能并行。**顶级性能是硬要求,不是偏好。**

读 Unity 文本资产的 py 层(`unity_yaml` / `class_registry` / `ui_scene_state`)已删:UI 舞台的发现与
解析全在 hook 的 `endfield.ui.stages` / `endfield.ui.stage`。py 侧不许再出现任何资产文本解析。

## 🔴 2. 层界(判据可 grep)

| 目录 | 禁止出现 |
|---|---|
| `Kernel/` | `bpy` / `mathutils` / `substance_painter` / `PySide` / 任何一个游戏的名字 |
| `Host/<宿主>/` | 另一个宿主的 API;任何游戏的名字;关于数据 / 浏览 / 加载 / 揭示 / 筛选的命令与逻辑 |
| `Game/<游戏>/` | 解析 / 拼种子 / 加载 / 遍历闭包;宿主 API(`<宿主名>/` 投影子目录除外) |

宿主只做三件事:**把陈述落成本宿主的数据**(`materialise` / `play` / …),**把内核的描述画出来**
(`render.py`),以及**操作它自己的设置**(Blender 的后处理链与材质参数面板、Painter 的显示设置)。
关于数据的一个命令、一个菜单、一个弹出面板写在宿主里,另一个宿主就没有它——
这正是「定位到浏览器」曾经在 Painter 上直接抛异常的原因。

**宿主差异一律是协议**(`Kernel/host.py`):驱动继承 `Host` + 它答得出的那几个
(`SceneGraph` / `Compositor` / `Rig` / `Timeline` / `MorphTargets` / `NodeMaterials` /
`TextureCache` / `TextureSets` / `DisplaySettings`),`host.capabilities` 由 `isinstance` 读回。
命令、选项、页签、分段声明 `requires=host_port.Rig` 这类**协议类**。
**不许声明两遍,不许写抛异常的桩,禁止 `if host.name == ...`**;
「用户面前的骨架」一律问 `host_port.selected_rig(context)`(不是 Rig 的宿主答 None)。

`Kernel/bridge/` 是读取器的唯一入口,公开面只有四个动词(表 / 字节 / 视图 / 搜索)加会话控制;
`Kernel/statement.py` 是**唯一**把字节变成数组的地方(唯一的 `frombuffer`)。

**坐标约定一个数字都不许写在 py 里。** 基变换 `matrix`、顶层一次性转身 `root`、以及
**相机/灯自己朝哪个轴的那一下 `aim`**,全部从 `core.bases` 读(`Kernel/statement.py::basis`)。
`aim` 只落在相机/灯这一个变换上,它的**子物体要乘逆**才不会被带着转;宿主里出现
`Matrix.Rotation(pi/2, 4, "X")` 这种写法即违规 —— 那是内核的陈述,不是宿主的意见。

**骨架是谁,问骨架自己**:动画重定向用的是 `Rig.rig_paths`(骨骼的变换路径)与
`Rig.rig_avatar`(建骨时烙上的 avatar 陈述),都由读取器原样带回读取器。
别拿骨骼名单冒充路径,别从名字反推身份。

## 🔴 3. 一个包两个宿主,入口不许分叉

根 `__init__.py` 只做宿主检测 + 分派:Blender 走 `register/unregister`,
Painter 走 `start_plugin/close_plugin/reload_plugin`,两边都落到 `Host/<宿主>/`。

Painter 侧的插件目录是**指向本仓的目录联接**:

```
<Painter user resources>\python\plugins\RuriRipperImporter
  -> D:\Ruri\00.Model\Tools\BlenderProfile\RuriConfig\scripts\addons\RuriRipperImporter
```

看到两条路径指向看起来一样的东西,先假设是同一个目录(`Get-Item -Force | Select LinkType, Target`)。

## 🔴 3.5 一行的 Payload 必须**就是**种子

名册给角色 id、场景表给地图名、卡片表给文件路径,都是**把拼种子这件事推给了宿主**——
而宿主不知道这个游戏的前缀,于是按钮按下去只会得到「这个种子没人认领」。

**判据**:每个会被导入的数据集,payload 列的值拿去 `core.statement.nodes --data-arg seed=<它>`
要出行。种子的拼法写在**认领它的那个 StatementSource 旁边**(`XxxStatementSource.XxxSeed(...)`),
任何一张表都不许自己拼前缀——拼两处就是两份真源,漂移只会在按钮上现形。

**答案型数据集不许带能上页签的角色。** 一张表是「列表」还是「答案」看它的签名:参数全是
可选/可空列表 = 页签能直接打开它;有必填参数 = 它在答一个还没被挑中的东西。
**判据:页签清单里不许有点开就是 0 行的项。**

名册的 Face 分页问 `panel.face_dataset`,参数就是**被挑中那行的种子**;返回的行自己说明它是
哪一种脸:带 `mesh/index/weight` 就是形态键,带 `kind/ctrl/bone` + TRS 就是骨驱动,
页签按列分动词,**不看游戏名**。

一个页签**有没有「导入」这个动作**是页签自己声明的:表情、动作、剧情单元都有自己的动词,
它们的行不是文档能装下的东西。**不存在一个按下去什么都不发生的按钮。**

## 🔴 4. 每样东西只有一个

| 语义 | 唯一真源 |
|---|---|
| 加载 | `Kernel/app/loading.py` 的 `load` / `perform` |
| 注册 | `Kernel/extensions.py` 的 `ExtensionPoint`:命令、筛选规格、名册面板、弹出面板与菜单、Look 分段、图提供者、顶点腿、兑现面、灯角色、后处理——**不许再开一张模块级字典当注册表** |
| 面板 | `Kernel/app/layout.py` 的描述词汇;弹出面板/菜单用 `declare_popover` / `declare_menu` 声明一次,两个宿主从 `SURFACES` 生成,**宿主里不写菜单体** |
| 宿主能力 | `Kernel/host.py` 的协议类 |
| 会话 | C# 的 `core.installs`;py 只存用户输入的那几行 |
| 导入选项 | `Kernel/options.py` 一张表;两个宿主的控件都从它生成,**禁止手写第二份** |
| reload | 根 `__init__.py` + 各驱动一份,靠模块自报 `HOLDS_PROCESS_STATE` |

跨模块调用的函数就是公开函数:**不许 `模块._私有名`**(生成产物清单里点名的宿主函数除外,
那些名字是配方的数据,改名要改配方重生成)。

## 🔴 5. 着色栈按宿主投影,路径不硬编码

生成物落在 `Game/<游戏>/shader/<宿主>/`,由生成器配方的 `destination` 决定。这个目录**整个归生成器**:
部署后它恰等于产物树(Blender 的运行时就是该包的 `__init__.py`),不是本次产物的文件一律删掉,
**里面不许放任何手写文件**。
消费方一律走 `Kernel/shaderstack.py` 解析,**按安装自己公布的产品名 / 引擎家族**找
`Game/<名字>/`——文件夹名就是 join,没有映射表,**代码里不许出现着色器名或游戏名**。
带 `register`/`unregister` 的投影由游戏注册表直接按 `Game/<游戏>/shader/<宿主名>` 导入并注册
(`Game._host_stack`),**不写 `shader/__init__.py` 门面**。

产物的清单里写着它绑定的宿主模块与函数名(`registry_module` / `register_fn` / …),
那是**产物对宿主的声明**:`Host/Blender/material_builder.py` 的那组函数名因此是数据,
改名要改配方重生成,不许单方面改宿主。改生成物里的宿主回调路径
(`RegistryModule` / `RigIdentityModule`)= **改配方再重生成**,不许手改产物。重生成+部署:

```bash
dotnet run --project Ruri.RenderPipelines/Ruri.Generator.Cli -c Release -- --deploy-shaders Assets/Recipes/Blender.json
```

## 6. 收工验证

**画得出来 ≠ 按得下去。** `draw()` 不抛异常只说明面板画得出,命令体自己调自己这种错要等到
**真按一次**才现形。所以收工的判据是:**把注册表里每一条命令,在每一个安装上,通过它真正的
算子按一次**,记下 `ok / 异常 / 跳过理由`。跳过只有两种合法理由:①这个宿主不是那条命令
`requires` 的协议 ②本机没有那个安装。

Blender(headless 按得下去,只是画不出来),用隔离的配置目录,免得读到别处存的 bin 路径:

```bash
BLENDER_USER_SCRIPTS=<工作树>/scripts BLENDER_USER_CONFIG=<空目录> RURI_RIPPERHOOK_BIN=<仓>/Source/0Bins/Release blender.exe --background --python <探针>
```

探针里 `addon_utils.enable("RuriRipperImporter", default_set=True, persistent=False)`,然后
`getattr(bpy.ops, ns).op("EXEC_DEFAULT", **arguments)` 逐条按。stepped 的命令在无窗口时
自己走 inline 驱动,和交互式走的是同一个生成器。面板描述用 `app_layout.describe(draw, context)`
逐页签跑一遍。

Painter(不能 headless):最接近的可跑检查是把 `substance_painter` / `PySide6` 打桩后
真 import 整棵驱动树并实例化驱动 —— 协议缺方法在这一步就是 `TypeError`。

静态尺(纯 AST,不 import,缺宿主 API 也能跑):未定义全局名、跨模块不存在的属性、
**指向已删模块的相对 import**、`模块._私有名`、顶层同名重定义、只写不读的局部变量、
从插件入口(宿主驱动 + 各游戏按名加载的页签/分段/投影)出发走不到的模块、没人引用的顶层定义。
