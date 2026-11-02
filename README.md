# 农作物病虫害叶片识别系统

基于 **YOLO26 + FastAPI + Vue3** 的农作物病虫害识别与知识问答系统。上传一张叶片照片或一段视频，系统自动框出病虫害、给出危害等级与防治建议，并支持 AI 问答、知识图谱、药剂查询、模型热切换与在线训练。

> 课程设计项目 · 单机部署 · 无需云服务（除大模型 API 外）

---

## 功能一览

| 模块 | 说明 |
|---|---|
| **智能识别** | 图片 / 视频 / 摄像头实时检测，输出类别、置信度、危害等级、风险等级 |
| **AI 问答** | 基于知识库的 RAG 问答，检索不到时自动联网搜索；支持语音提问 |
| **病虫害图鉴** | 800+ 条病虫害资料，按作物分类、分页浏览、关键词检索 |
| **药剂资料** | 86 种药剂，含剂型、用法用量、适用病害 |
| **知识图谱** | 作物 / 病害 / 虫害 / 症状 / 药剂 / 病原 / 措施 六类实体，500 节点可视化 |
| **数据洞察** | 识别趋势、病害 TOP10、作物覆盖、字段完整度 |
| **知识库** | 上传文档 → 切块 → 向量化 → 检索，支持内置资料 |
| **模型管理** | 上传 `.pt` 权重、热切换、自动读取类别并翻译 |
| **模型训练** | 页面上发起训练任务，查看曲线与指标 |

---

## 技术栈

| 层 | 技术 |
|---|---|
| 目标检测 | Ultralytics YOLO26（n / s） |
| 后端 | Python 3.11 · FastAPI · SQLAlchemy · PyMySQL |
| 数据库 | MySQL 8.0（`utf8mb4`） |
| 大模型 | 通义千问（DashScope）：问答、翻译、知识抽取 |
| 向量检索 | NumPy 全量余弦相似度 + 本地向量库 |
| 前端 | Vue 3 · Vite · ECharts · 自研「禾鉴」档案册风格 |
| 训练 | Ultralytics + PyTorch（CUDA 可选） |

---

## 目录结构

```
.
├── server/                 后端（FastAPI）
│   ├── app/
│   │   ├── api/            接口层（识别/问答/图鉴/药剂/图谱/模型/训练…）
│   │   ├── service/        业务层（匹配/检索/图谱/训练/ASR）
│   │   ├── models/         ORM 模型
│   │   ├── core/           配置
│   │   └── utils/          工具
│   ├── data/
│   │   ├── models/         权重与 models.json
│   │   └── vstore/         向量库（chunks + vectors）
│   ├── main.py             启动入口
│   └── requirements.txt
├── web-v4/                 主前端（Vue3 + Vite）
│   └── src/{views,components,api,composables}
├── client/                 备用前端（可忽略）
├── datasets/               训练数据集
│   ├── plantdiseases-30类/ 30 类作物病害（1863 训练 + 465 验证）
│   └── pest101-101类/      101 类农业害虫（15182 训练 + 1897 验证 + 1897 测试）
├── train_project/          训练脚本与历史权重
├── 示例视频/               演示用视频（由数据集图片合成）
├── docs/                   文档
├── 启动项目.bat            Windows 一键启动
└── 启动.sh                 macOS / Linux 一键启动
```

---

## 快速启动

### 0. 前置要求

| 软件 | 版本 | 说明 |
|---|---|---|
| Python | 3.10+ | 建议 3.11 |
| Node.js | 18+ | 用于前端 |
| MySQL | 8.0 | 需要能创建数据库 |
| （可选）NVIDIA 驱动 + CUDA | — | 有 GPU 时推理更快 |

### 1. 准备数据库

```bash
# 建库（名字固定为 db_plant_diseases）
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS db_plant_diseases DEFAULT CHARSET utf8mb4;"

# 导入表结构与数据
mysql -u root -p --default-character-set=utf8mb4 db_plant_diseases < 数据库脚本/db_plant_diseases.sql
```

### 2. 配置后端

```bash
cd server
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

打开 `.env`，按自己的环境改这几项：

```ini
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的数据库密码
DB_NAME=db_plant_diseases

# 通义千问（问答/翻译/抽取都要用；不填则这些功能不可用，识别仍可用）
DASHSCOPE_API_KEY=sk-你的key
```

安装依赖：

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

启动后端：

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

看到 `Application startup complete` 即成功；接口文档：<http://127.0.0.1:8001/docs>

### 3. 启动前端

```bash
cd web-v4
npm install
npm run dev -- --port 5176
```

打开 <http://127.0.0.1:5176>

> 前端已在 `vite.config.js` 里把 `/api` 和 `/uploads` 代理到 `127.0.0.1:8001`，无需额外配置。

### 4. 一键启动（可选）

- **Windows**：双击根目录 `启动项目.bat`（会自动检查端口、开两个窗口、打开浏览器）
- **macOS / Linux**：`bash 启动.sh`

---

## 数据集

> 为了仓库轻量，数据集单独放在 **Releases** 页下载（解压到 `datasets/` 即可训练）。

| 数据集 | 类别 | 训练/验证/测试 | 大小 |
|---|---|---|---|
| `plantdiseases-30类.zip` | 30 类作物病害（含健康叶片） | 1863 / 465 / — | 69 MB |
| `pest101-101类.zip` | 101 类农业害虫 | 15182 / 1897 / 1897 | 775 MB |

**只是跑通系统不需要下载数据集** —— 仓库已带训练好的权重，直接启动即可；下载数据集是为了自己重训。

格式为 **YOLO 检测格式**：

```
datasets/plantdiseases-30类/
├── images/train/  images/val/
├── labels/train/  labels/val/
└── data.yaml          # 类别名与路径
```

训练：

```bash
cd train_project
python retrain.py --data ../datasets/plantdiseases-30类/data.yaml --epochs 120
```

> 数据集较大，如果只是跑通系统，**不需要下载数据集**：仓库里已带训练好的权重，直接启动即可。

---

## 模型

| 模型 | 类别数 | mAP50 | 说明 |
|---|---|---|---|
| `yolo26s_cos120`（默认） | 30 | 0.336 | 作物病害，整图判断准确率 54.6% |
| `mpest101` | 102 | 0.608 | 农业害虫，数据量 8 倍、质量更好 |

权重在 `server/data/models/`，注册信息在 `models.json`。

**换模型**：页面「模型」→ 上传 `.pt` → 切换启用。系统会：

1. 读取权重里的类别名
2. 英文类名自动用大模型翻译成中文
3. 写入 `t_model_class` 并尝试绑定已有知识

---

## 数据表（核心 4 张）

| 表 | 作用 | 行数 |
|---|---|---|
| `t_knowledge` | 知识条目（症状/防治/等级） | 809 |
| `t_model_class` | 模型类别 ↔ 知识 对照（编号 + 名字 + 知识 id） | 162 |
| `t_pesticide` | 药剂（剂型/用量/间隔期） | 86 |
| `t_pesticide_knowledge` | 药剂 ↔ 知识 关联 | 236 |

识别匹配顺序：

```
① (model_id, class_id) → knowledge_id → 知识    （按编号，最准）
② 没绑定 → 中文名精确匹配 → 归一化匹配
③ 都没有 → known=false，页面显示"数据库里没有"
```

---

## 常见问题

**Q：启动后页面空白 / 接口 500？**
看后端控制台。多数是 `.env` 里数据库密码没改，或数据库没导入。

**Q：识别报错 `Unexpected UTF-8 BOM`？**
`server/data/models/models.json` 被编辑器加了 BOM。用 VS Code 另存为「UTF-8 无 BOM」，或执行：
```bash
python -c "from pathlib import Path;p=Path('server/data/models/models.json');p.write_text(p.read_text(encoding='utf-8-sig'),encoding='utf-8')"
```

**Q：AI 问答没反应？**
`.env` 里 `DASHSCOPE_API_KEY` 没填或已失效。识别功能不依赖它。

**Q：没有 GPU 能跑吗？**
能。把 `server/app/core/config.py` 里的 `DEVICE` 改成 `cpu`。

**Q：端口被占用？**
后端默认 8001、前端 5176，改端口时记得同步 `web-v4/vite.config.js` 的代理地址。

---

## 许可与声明

- 代码：课程设计项目，可自由参考学习
- 数据集：`plantdiseases-30类` 来自 PlantVillage 公开数据；`pest101-101类` 来自 IP102 公开数据，**仅用于学习研究，不得商用**
- 示例视频：由上述数据集图片合成，无额外版权问题
- 药剂信息：由公开农业资料整理生成，**实际用药请以当地植保部门或农药标签为准**
