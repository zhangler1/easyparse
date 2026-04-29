# Easyparse 测试文档

## 1. 项目简介

Easyparse 是一个**文件解析与转换服务**，支持以下功能：

- OFD 转 PDF
- Markdown 转 Word
- PDF 文本提取

## 2. 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| PDF 处理 | pdfminer.six |
| OFD 解析 | easyofd |
| 文档转换 | python-docx |

## 3. 示例代码

```python
from md2word.markdocx import md2word

md2word("input.md", "output.docx")
```

## 4. 注意事项

> 本服务仅支持 `.md` 格式文件上传，输出为 `.docx` 格式。

### 4.1 文件大小限制

单次上传文件不超过 **50MB**。

### 4.2 支持的 Markdown 语法

1. 标题（h1 ~ h6）
2. 加粗、斜体、删除线
3. 有序/无序列表
4. 表格
5. 代码块
6. 引用

---

*文档生成时间：2026-04-29*
