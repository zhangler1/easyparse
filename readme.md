# Easyparse 接口说明文档

## 概述

Easyparse 是一个文件解析与转换服务，基于 FastAPI 构建，提供以下三类核心能力：

| 接口 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `POST /convert` | 文件解析为文本 | OFD / PDF / Office 等文件 | 纯文本 `.txt` |
| `POST /ofd_to_pdf` | OFD 转 PDF | OFD 文件 | PDF 文件 |
| `POST /markdown_to_word` | Markdown 转 Word | Markdown 文件 | Word `.docx` 文件 |

---

## 环境准备（重要）

本项目依赖两个**本地源码形式**的子项目，必须手动拉取到 `easyparse/` 目录下后才能正常运行：

| 子项目 | 目录 | 用途 |
|--------|------|------|
| [`easyofd`](https://github.com/renoyuan/easyofd) | `easyparse/easyofd/` | 解析 OFD 并渲染为 PDF，`/convert` 和 `/ofd_to_pdf` 接口依赖 |
| [`markitdown`](https://github.com/microsoft/markitdown) | `easyparse/markitdown/` | 解析 PDF/Office 等文档为文本，`/convert` 接口依赖 |

### 拉取方式

```bash
cd easyparse

# 拉取 easyofd（OFD 解析渲染库）
git clone https://github.com/renoyuan/easyofd.git

# 拉取 markitdown（微软开源文档解析库）
git clone https://github.com/microsoft/markitdown.git
```

### 说明

- `pyproject.toml` 中的 `easyofd` / `markitdown[all]` 声明只是占位，实际运行时优先使用项目本地的源码。
- Docker 构建时（`dockerfile.uv`）会通过 `uv pip install -e /app/markitdown/packages/markitdown[all]` 将本地 `markitdown` 以可编辑模式安装进虚拟环境；若不提前拉取，镜像构建会失败。
- 如需本地运行（非 Docker），拉取后执行：
  ```bash
  uv venv .venv
  uv sync
  uv pip install -e markitdown/packages/markitdown[all]
  uv pip install -e markitdown/packages/markitdown-sample-plugin
  ```

---

## 1. POST `/convert` — 文件解析为文本

### 功能说明

将上传的文件解析提取为纯文本内容。支持多种文件格式的自动识别与转换：

- **OFD 文件**：先通过 `easyofd` 将 OFD 转为 PDF，再通过 `markitdown` 将 PDF 转为文本
- **其他文件**（PDF、Office、图片等）：直接通过 `markitdown` 解析为文本

### 原理

```
OFD 文件:  上传 → base64编码 → easyofd解析OFD结构 → 渲染为PDF字节流 → markitdown提取文本 → 返回.txt
其他文件:  上传 → markitdown解析(支持PDF/Office/HTML等) → 返回.txt
```

**核心依赖**：
- `easyofd`：解析 OFD（开放版式文档）格式，OFD 是中国版式文档国家标准（GB/T 33190-2016），其内部为 XML+资源文件的 ZIP 包。`easyofd` 解析 XML 结构并渲染为 PDF。
- `markitdown`：微软开源的文档转换库，底层针对不同格式使用不同解析器（PDF 用 `pdfminer`、Office 用 `python-pptx`/`python-docx`/`openpyxl` 等），统一输出 Markdown/纯文本。
- 图片 OCR（可选）：当 `imgNum > 0` 时，提取文档中的图片发送至视觉大模型（qwen2half-vl-72b）进行文字识别，将识别结果追加到文本末尾。

### 请求参数

| 参数 | 类型 | 位置 | 必填 | 说明 |
|------|------|------|------|------|
| `file` | file | form-data | 是 | 待转换的文件（支持 .ofd / .pdf / .docx / .pptx / .xlsx 等） |
| `imgNum` | int | form-data | 否 | 需要OCR识别的图片数量，默认 0（不识别） |

### 请求示例

```bash
# 基础转换（不识别图片）
curl -X POST http://localhost:5000/convert \
  -F "file=@document.pdf" \
  -o document.txt

# 带图片OCR识别（识别前3张图片）
curl -X POST http://localhost:5000/convert \
  -F "file=@document.pdf" \
  -F "imgNum=3" \
  -o document.txt
```

### 响应

- **成功**：`200 OK`，返回纯文本文件（`text/plain`）
- **失败**：`500`，返回 JSON 错误信息

| 响应头 | 说明 |
|--------|------|
| `X-Request-ID` | 请求唯一标识 |
| `X-File-Size` | 返回文件大小（字节） |

---

## 2. POST `/ofd_to_pdf` — OFD 转 PDF

### 功能说明

将 OFD（开放版式文档）文件转换为标准 PDF 文件。

### 原理

```
上传OFD → 读取为二进制 → base64编码 → easyofd.read()解析OFD结构 → ofd.to_pdf()渲染PDF → 返回.pdf
```

**核心依赖**：
- `easyofd`：OFD 文件本质上是一个 ZIP 压缩包，内部包含 XML 描述文件（文档结构、页面布局、文字/图片/图形等）和资源文件（图片、字体等）。`easyofd` 的工作流程为：
  1. 解压 ZIP，解析 `OFD.xml`（文档入口）→ `Document.xml`（页面引用）→ `Page.xml`（页面内容）
  2. 根据 XML 中定义的 TextObject、PathObject、ImageObject 等图元对象，使用 `reportlab` 在 PDF 画布上重新绘制
  3. 输出标准 PDF 字节流

### 请求参数

| 参数 | 类型 | 位置 | 必填 | 说明 |
|------|------|------|------|------|
| `file` | file | form-data | 是 | OFD 文件（仅支持 .ofd 格式） |

### 请求示例

```bash
curl -X POST http://localhost:5000/ofd_to_pdf \
  -F "file=@contract.ofd" \
  -o contract.pdf
```

### 响应

- **成功**：`200 OK`，返回 PDF 文件（`application/pdf`）
- **非OFD文件**：`400`，返回 `{"detail": "Only OFD files are supported"}`
- **转换失败**：`500`，返回 JSON 错误信息

| 响应头 | 说明 |
|--------|------|
| `X-Request-ID` | 请求唯一标识 |
| `X-File-Size` | 返回文件大小（字节） |
| `Content-Encoding` | 固定为 `identity`（不压缩） |

---

## 3. POST `/markdown_to_word` — Markdown 转 Word

### 功能说明

将 Markdown 文件转换为格式化的 Word（.docx）文档，保留标题层级、加粗、斜体、列表、表格、代码块等样式。

### 原理

```
上传.md → md2html()将Markdown转为HTML → DocxProcessor解析HTML DOM → 按样式配置生成docx段落/表格 → 返回.docx
```

**核心依赖**：
- `md2word` 模块（项目自研），转换分为两步：
  1. **Markdown → HTML**：使用 `markdown` 库将 Markdown 语法解析为 HTML 标签树，支持扩展语法（表格、代码高亮等）
  2. **HTML → DOCX**：`DocxProcessor` 遍历 HTML DOM 树，将每个标签映射为 `python-docx` 的段落/run 对象：
     - `<h1>~<h6>` → Word 标题样式（Heading 1~6）
     - `<strong>` / `<em>` → 加粗 / 斜体 run 属性
     - `<ul>` / `<ol>` → Word 列表样式
     - `<table>` → Word 表格对象
     - `<code>` / `<pre>` → 等宽字体 run
  3. 样式细节（字号、行距、页边距等）由 `config/default_style.yaml` 配置文件控制

### 请求参数

| 参数 | 类型 | 位置 | 必填 | 说明 |
|------|------|------|------|------|
| `file` | file | form-data | 是 | Markdown 文件（.md 格式） |

### 请求示例

```bash
curl -X POST http://localhost:5000/markdown_to_word \
  -F "file=@report.md" \
  -o report.docx
```

### 响应

- **成功**：`200 OK`，返回 Word 文件（`application/vnd.openxmlformats-officedocument.wordprocessingml.document`）
- **失败**：`500`，返回 JSON 错误信息

| 响应头 | 说明 |
|--------|------|
| `X-Request-ID` | 请求唯一标识 |
| `X-File-Size` | 返回文件大小（字节） |
| `Content-Encoding` | 固定为 `identity` |

---

## 通用说明

### 请求追踪

所有接口支持通过请求头 `X-Request-ID` 传入自定义追踪 ID，未传入时服务端自动生成 UUID。

### 临时文件清理

所有接口在返回响应后通过 FastAPI `BackgroundTasks` 异步清理临时文件（上传文件 + 输出文件），避免磁盘泄漏。异常情况下通过 `finally` 块 + 双重保障机制确保清理。

### 线程模型

- 文件转换（CPU 密集型）在共享 `ThreadPoolExecutor` 中执行，避免阻塞 FastAPI 事件循环
- 图片 OCR 识别使用独立线程池，与主转换流程并行

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PORT` | 5000 | 服务监听端口 |
| `SERVER_WORKERS` | 4 | Uvicorn 工作进程数 |
| `MD_WORKER` | 4 | 文档转换线程池大小 |
| `IMG_WORKER` | 4 | 图片OCR线程池大小 |
| `IMAGE_UPLOAD_URL` | 空 | 图片OCR服务地址（需配置后 imgNum 才生效） |
| `IMAGE_OUTPUT_DIR` | /tmp/shared_all/assert | 图片临时输出目录 |
