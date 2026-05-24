# 不挂科神器 · 题库查答案

上传 **带红色正确答案标注的 PDF 题库**，在网页里粘贴题目，自动匹配原题并返回正确答案。

## 安装包（给最终用户）

1. 开发者在本机双击 **`build_installer.bat`**（需先 `install_deps.bat`；打包约 5–15 分钟，体积约 1–2GB）
2. **改版本号 / 图标**：编辑 `assets/build_meta.py`（版本）与 `scripts/make_icon.py`（图标样式），再重新打包
3. 将以下之一发给用户：
   - **`installer\Output\NoguakeSetup.exe`**（需本机安装 [Inno Setup 6](https://jrsoftware.org/isinfo.php) 才会生成）
   - 或 **`release\NoguakeSetup`** 文件夹（zip 后分发）：用户解压 → 运行 `install.ps1` → 桌面出现「不挂科神器」快捷方式
4. 用户双击桌面快捷方式即可使用（题库数据在 `%LOCALAPPDATA%\Noguake\libraries`）

## 桌面应用（开发/自用）

1. 双击 `安装依赖.bat`（只需一次）
2. 双击 **`启动桌面版.bat`** → 弹出独立窗口，无需开浏览器

## 浏览器版

1. 双击 `启动应用.bat`
2. 打开 **http://127.0.0.1:8765**

使用步骤：**新建题库** → 上传 PDF → **开始构建** → 「查答案」粘贴题目。

界面为浅色备考风格，数据保存在本机 `libraries/` 目录。

## 命令行（可选）

1. PDF 放进 `data/`，运行 `解析题库.bat`
2. 运行 `开始提问.bat` 在终端查答案

## 使用说明

- 题库 PDF 中 **红色文字 = 正确答案**（itexamanswers 等站点）
- 输入题干关键词或整段英文题目
- 显示题号、正确选项（绿色高亮）、是否来自 PDF 红色标注

## 技术架构

```
data/（原始资料）
    ↓ 解析 PDF/PPT/Word/TXT
分块 + 元数据（来源文件名）
    ↓ BAAI/bge-small-zh-v1.5 向量化
FAISS 索引（knowledge_base/）
    ↓ 题目向量检索匹配（<1 秒）
返回答案（无需联网）
```

| 环节 | 技术 | 说明 |
|------|------|------|
| 答案识别 | PyMuPDF 红色提取 | 全卷按 #FF0000 标注 |
| 向量库 | FAISS | 题目语义匹配 |
| 嵌入 | bge-small-zh-v1.5 | 中英文题干均可 |
| 前端 | FastAPI + 静态页 | 上传、构建、查答案 |

## 配置说明（config.yaml）

```yaml
course:
  university: "XX大学"
  major: "计算机科学与技术"
  course_name: "数字信号处理"
  professor: "张教授"

ollama:
  model: "qwen2.5:3b"   # 可换 qwen2.5:7b 等

embedding:
  device: "cpu"          # 有 NVIDIA 显卡可改为 cuda
```

## 命令行（可选）

```bash
# 激活虚拟环境后
python build_index.py    # 重建索引
python ask.py            # 交互问答
```

## 商业化提示

- 每门课/每个教授版本单独打包：`data/` + 已建好的 `knowledge_base/` + 改好的 `config.yaml`
- 资料需为**公开或已获授权**的学习材料，注意版权与学校规定
- 可搭配 U 盘或网盘售卖「离线包」，买家本机运行，无需 API 费用

## 常见问题

**Ollama 连不上**  
先运行 `ollama serve`，或确认 Ollama 托盘程序已启动。

**检索结果为空**  
调低 `config.yaml` 里 `retrieval.score_threshold`（如 0.25），或增加 `data/` 资料后重新构建。

**PPT 解析文字很少**  
扫描版 PPT 无法提取文字，需 OCR 或改用老师发的 PDF/Word 版。

## 目录结构

```
不挂科神器/
├── 启动桌面版.bat    ← 独立窗口（推荐）
├── 启动应用.bat      ← 浏览器打开
├── 安装依赖.bat
├── 解析题库.bat
├── 构建知识库.bat
├── 开始提问.bat
├── app/              ← 前端 + API
├── libraries/        ← 用户题库（自动创建）
├── config.yaml
├── requirements.txt
├── build_quiz.py
├── build_index.py
├── ask.py
├── data/              ← 放学习资料
├── knowledge_base/    ← 自动生成，勿删
└── src/
```

祝期末不挂科。
