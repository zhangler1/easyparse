# noinspection PyProtectedMember
#
import io
import os
import re
from urllib.request import urlopen

from bs4 import BeautifulSoup
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import *
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import qn, nsdecls
from docx.shape import InlineShape
from docx.shared import Inches, RGBColor, Pt
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from requests import HTTPError
from log_manager import logger
from md2word.provider.docx_plus import add_hyperlink
from md2word.provider.style_manager import StyleManager
from md2word.utils.style_enum import MDX_STYLE
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt

debug_state: bool = False
auto_open: bool = True
show_image_desc: bool = (
    True  # 是否显示图片的描述，即 `![desc](md2word/img)` 中 desc的内容
)


def debug(*args):
    print(*args) if debug_state else None


class DocxProcessor:
    def __init__(self, style_conf: dict, footer_text=None, footer_enabled=None):
        self.document = Document()
        self.style_conf = style_conf or {}
        if style_conf is not None:
            StyleManager(self.document, style_conf).init_styles()
        self._add_footer(footer_text, footer_enabled)

    def _add_footer(self, footer_text, footer_enabled=None):
        """为文档的默认 Section 添加页脚声明文案。

        footer_enabled 参数的语义:
        - None   : 未传入，按 footer_text / YAML 回退逻辑处理
        - True   : 启用页脚，使用 footer_text 指定的文案
        - False  : 显式禁用页脚，不赴 YAML 回退

        footer_text 参数的语义（仅当 footer_enabled 不是 False 时生效）:
        - None   : 未传入，赴 YAML 回退默认值
        - "xxx"  : 使用调用方指定的文案

        文案优先级：footer_enabled=False 禁用 > footer_text 参数 > style_conf['footer']['text'] > 无页脚
        """
        # footer_enabled=False = 显式禁用页脚
        if footer_enabled is False:
            return

        logger.info(f"footer_text: -{footer_text}- footer_enabled: -{footer_enabled}-")

        # 确定最终文案
        actual_text = footer_text
        if actual_text is None:
            footer_conf = self.style_conf.get("footer", {})
            actual_text = footer_conf.get("text")
        if not actual_text:
            return  # 无文案，不设置页脚

        # 获取默认 Section 的页脚
        section = self.document.sections[0]
        footer = section.footer
        footer.is_linked_to_previous = False  # 断开继承，否则写入内容不会显示

        # 添加页脚文案段落
        paragraph = footer.paragraphs[0]

        # 对齐方式
        footer_conf = self.style_conf.get("footer", {})
        alignment_str = footer_conf.get("font", {}).get("alignment", footer_conf.get("alignment", "center"))
        alignment_map = {
            "center": WD_PARAGRAPH_ALIGNMENT.CENTER,
            "left": WD_PARAGRAPH_ALIGNMENT.LEFT,
            "right": WD_PARAGRAPH_ALIGNMENT.RIGHT,
        }
        paragraph.alignment = alignment_map.get(alignment_str, WD_PARAGRAPH_ALIGNMENT.CENTER)

        # 添加 run
        run = paragraph.add_run(actual_text)

        # 字体样式配置
        font_conf = footer_conf.get("font", {})
        font_default = font_conf.get("default", "Times New Roman")
        font_east_asia = font_conf.get("east-asia", "宋体")
        font_size = font_conf.get("size", 9)
        font_color = font_conf.get("color", "999999")

        # 字号
        run.font.size = Pt(font_size)

        # 颜色
        run.font.color.rgb = RGBColor.from_string(font_color)

        # 西文字体
        run.font.name = font_default

        # 中文字体（WPS 兼容：通过 OxmlElement 显式设置 w:eastAsia）
        rpr = run._element.get_or_add_rPr()
        rfonts = OxmlElement('w:rFonts')
        rfonts.set(qn('w:eastAsia'), font_east_asia)
        # 移除可能存在的旧字体设置，避免冲突
        for e in rpr.xpath('.//w:rFonts'):
            rpr.remove(e)
        rpr.append(rfonts)

    # h1, h2, ...
    def add_heading(self, content, tag: str):
        """添加标题。content 支持字符串或 BeautifulSoup 节点。

        当标题内含嵌套标签（如 <strong>/<a>）时，tag.string 会返回 None，
        导致标题为空且链接丢失；这里统一走 children 遍历，识别超链接。
        """
        from bs4 import NavigableString

        level: int = int(tag.__getitem__(1))
        p = self.document.add_paragraph(style="WPSHeading%d" % level)

        if isinstance(content, str):
            p.add_run(content)
            return p
        if content is None:
            return p

        for elem in content.contents:
            if isinstance(elem, NavigableString):
                text = str(elem)
                if text and text != "\n":
                    p.add_run(text)
                continue
            if elem.name == "a":
                link_text = elem.get_text() or elem.get("href", "")
                self.add_link(p, link_text, elem.get("href", ""))
                continue
            text = elem.get_text()
            if text:
                p.add_run(text)
        return p

    # noinspection PyMethodMayBeStatic
    def add_run(self, p: Paragraph, content: str, char_style: str = "plain"):
        # fixme 行内的样式超过一个的句子会被忽略，如：
        # <u>**又加粗又*斜体*又下划线**</u>
        debug("[%s]:" % char_style, content)
        run = p.add_run(content)

        # 不应当使用形如 run.bold = (char_style=="strong") 的方式
        # 因为没有显式加粗，不意味着整体段落不加粗。
        if char_style == "strong":
            run.bold = True
        if char_style == "em":
            run.italic = True
        if char_style == "u":
            run.underline = True
        if char_style == "strike":
            run.font.strike = True
        if char_style == "sub":
            run.font.subscript = True
        if char_style == "sup":
            run.font.superscript = True
        run.font.highlight_color = (
            WD_COLOR_INDEX.YELLOW if char_style == "highlight" else None
        )

        # if char_style == "code":
        #     run.font.name = "Consolas"

    def add_code_block(self, pre_tag):
        # TODO 代码块样式
        # TODO 设置代码块（表格）中的中文字体，似乎只能通过指定 已设置好中文字体的样式 来达到目的
        code_table = self.document.add_table(0, 1, style=MDX_STYLE.TABLE)
        row_cells = code_table.add_row().cells
        run = (
            row_cells[0].paragraphs[0].add_run(pre_tag.contents[0].string[:-1])
        )  # -1是为了去除行末的换行符
        run.font.name = "Consolas"

    def add_picture(self, img_tag):
        pass
        # p: Paragraph = self.document.add_paragraph()
        # p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        # run: Run = p.add_run()
        # p.paragraph_format.first_line_indent = 0

        # img_src: str
        # scale: float = 100  # 优先级最高，单位 %
        # width_px: int = 100
        # height_px: int = 100
        # # 设置宽度
        # if img_tag.get("style"):
        #     style_content: str = img_tag["style"]
        #     img_attr: list = style_content.strip().split(";")
        #     # print(img_attr)
        #     attr: str
        #     for attr in img_attr:
        #         if attr.find("width") != -1:
        #             # TODO 处理 style 中的宽度和高度属性
        #             width_px = int(re.findall(r"\d+", attr)[0])
        #         if attr.find("height") != -1:
        #             height_px = int(re.findall(r"\d+", attr)[0])
        #         if attr.find("zoom") != -1:
        #             scale = int(re.findall(r"\d+", attr)[0])

        # if img_tag["src"] != "":
        #     img_src = img_tag["src"]
        #     # 网络图片
        #     if img_src.startswith("http://") or img_src.startswith("https://"):
        #         pass
        #         # print("[IMAGE] fetching:", img_src)
        #         # try:
        #         #     image_bytes = urlopen(img_src, timeout=10).read()
        #         #     data_stream = io.BytesIO(image_bytes)
        #         #     run.add_picture(data_stream, width=Inches(5.7 * scale / 100))
        #         # except Exception as e:
        #         #     print("[RESOURCE ERROR]:", e)
        #     else:
        #         pass
        #         # 本地图片
        #         # run.add_picture(img_src, width=Inches(5.7 * scale / 100))
        # else:
        #     # 网络图片
        #     img_src = img_tag["title"]
        #     print("[IMAGE] fetching:", img_src)
        #     try:
        #         image_bytes = urlopen(img_src, timeout=10).read()
        #         data_stream = io.BytesIO(image_bytes)
        #         run.add_picture(data_stream, width=Inches(5.7 * scale / 100))
        #     except Exception as e:
        #         print("[RESOURCE ERROR]:", e)

        # # 如果选择展示图片描述，那么描述会在图片下方显示
        # if show_image_desc and img_tag.get("alt"):
        #     # TODO 图片描述的显示样式
        #     desc: Paragraph = self.document.add_paragraph(
        #         img_tag["alt"], style=MDX_STYLE.CAPTION
        #     )
        #     desc.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        #     desc.style.font.color.rgb = RGBColor(11, 11, 11)
        #     desc.style.font.bold = False
        #     desc.paragraph_format.first_line_indent = 0

    def _render_inline(self, p, node):
        """Render inline HTML content into paragraph p.

        Handles NavigableString, <a> (hyperlinks), <strong>/<em>/<u>/<strike>/<sub>/<sup>
        (formatting), transparent containers (<p>/<span>/<div>), and <img>.
        Stops at <ul>/<ol> (nested list boundaries).
        Returns True if any visible content was written.
        """
        from bs4 import NavigableString
        TRANSPARENT_TAGS = {"p", "span", "div"}

        wrote_any = False
        for content in node.contents:
            if isinstance(content, NavigableString):
                s = str(content)
                if s and s != "\n":
                    p.add_run(s)
                    if s.strip():
                        wrote_any = True
                continue
            if content.name in ("ul", "ol"):
                continue  # Nested list boundary
            if content.name in TRANSPARENT_TAGS:
                wrote_any = self._render_inline(p, content) or wrote_any
                continue
            if content.name == "a":
                href = content.get("href", "")
                text = content.get_text()
                if text:
                    self.add_link(p, text, href)
                    wrote_any = True
                continue
            if content.name == "img":
                self.add_picture(content)
                continue
            # Format tags: strong, em, u, strike, sub, sup
            text = content.get_text()
            if text:
                self.add_run(p, text, content.name)
                wrote_any = True
        return wrote_any

    def add_table(self, table_root):
        # 统计列数
        col_count: int = 0
        for col in table_root.thead.tr.contents:
            if col.string != "\n":
                col_count += 1

        table = self.document.add_table(
            0, col_count, style=MDX_STYLE.TABLE
        )  # TODO 表格样式
        # 设置表格自动调整列宽以适应内容
        table.autofit = True
        table.allow_autofit = True
        # 表格头行
        head_row_cells = table.add_row().cells
        i = 0
        for col in table_root.thead.tr.contents:
            if col.string == "\n":
                continue
            cell_p = head_row_cells[i].paragraphs[0]
            cell_p.paragraph_format.first_line_indent = Inches(0)  # 清除缩进
            # Render inline content (links, bold, text) instead of col.string
            self._render_inline(cell_p, col)
            # Bold all runs in header cells
            for run in cell_p.runs:
                run.bold = True
            i += 1

        # 数据行
        if table_root.tbody:
            for tr in table_root.tbody:
                if tr.string == "\n":
                    continue
                row_cells = table.add_row().cells
                i = 0
                for td in tr.contents:
                    if td.string == "\n":
                        continue
                    cell_p = row_cells[i].paragraphs[0]
                    cell_p.paragraph_format.first_line_indent = Inches(0)  # 清除缩进
                    # Render inline content instead of td.string
                    self._render_inline(cell_p, td)
                    i += 1

    def add_number_list(self, number_list, current_level=1, max_level=4):
        """动态生成有序列表，支持嵌套无序/TODO列表"""
        from docx.shared import Pt
        from bs4 import NavigableString

        # 终止条件
        if current_level > max_level:
            return

        # 处理当前层级
        num = 1
        for item in number_list.children:
            if isinstance(item, NavigableString) and item.strip() == "":
                continue

            # 提取文本
            text = ""
            for content in item.contents:
                if isinstance(content, NavigableString):
                    text += str(content).strip()
                else:
                    break  # 遇到第一个非文本子元素就停止

            text = text.strip()
            if not text:
                continue

            # 添加列表项
            prefix = ".".join(str(i) for i in range(1, current_level)) + f".{num}" if current_level > 1 else str(num)
            paragraph = self.add_paragraph(text, prefix=f"{prefix}. ", p_style=None)  # 不使用样式

            # 直接设置段落格式
            paragraph.paragraph_format.left_indent = Pt(12 * current_level)  # 缩进
            paragraph.paragraph_format.space_after = Pt(1)  # 段后间距

            # 处理嵌套
            if not isinstance(item, NavigableString):
                if item.find("ul"):  # 嵌套无序列表
                    self.add_bullet_list(item.ul, current_level + 1, max_level)
                if item.find("ol"):  # 嵌套有序列表
                    self.add_number_list(item.ol, current_level + 1, max_level)
                # if text.startswith(("[ ]", "[x]")):  # 嵌套TODO列表
                #     self.add_todo_list(item, current_level + 1, max_level)

            num += 1

    def add_bullet_list(self, bullet_list, current_level=1, max_level=4):
        """动态生成无序列表，支持嵌套有序/TODO列表"""
        from bs4 import NavigableString
        from docx.shared import Pt

        # 终止条件
        if current_level > max_level:
            return

        # 配置符号和缩进
        BULLET_SYMBOLS = ["• ", "◦ ", "▪ ", "▫ ", "→ ", "‣ "]
        symbol = BULLET_SYMBOLS[min(current_level - 1, len(BULLET_SYMBOLS) - 1)]
        indent = Pt(12 * current_level)

        # 处理当前层级
        for item in bullet_list.children:
            if isinstance(item, NavigableString) and item.strip() == "":
                continue

            # 提取文本
            text = ""
            for content in item.contents:
                if isinstance(content, NavigableString):
                    text += str(content).strip()
                else:
                    break  # 遇到第一个非文本子元素就停止

            text = text.strip()
            if not text:
                continue

            # 添加列表项
            p = self.document.add_paragraph(style=None)
            p.add_run(" " * (current_level - 1) * 2 + symbol + text)
            p.paragraph_format.left_indent = indent
            p.paragraph_format.space_after = Pt(1)

            # 处理嵌套
            if not isinstance(item, NavigableString):
                if item.find("ol"):  # 嵌套有序列表
                    self.add_number_list(item.ol, current_level + 1, max_level)
                if item.find("ul"):  # 嵌套无序列表
                    self.add_bullet_list(item.ul, current_level + 1, max_level)
                # if text.startswith(("[ ]", "[x]")):  # 嵌套TODO列表
                #     self.add_todo_list(item, current_level + 1, max_level)

    def add_number_list(self, number_list, current_level=1, max_level=4, parent_numbers=None):
        """
        动态生成有序列表，支持嵌套无序/TODO列表

        参数:
            number_list: BeautifulSoup解析的ol列表对象
            current_level: 当前嵌套层级，默认为1
            max_level: 最大嵌套层级，默认为4
            parent_numbers: 父级编号列表，用于构建多级编号
        """
        from docx.shared import Pt
        from bs4 import NavigableString

        # 终止条件：防止无限递归
        if current_level > max_level:
            return

        # 初始化父级编号（首次调用时）
        if parent_numbers is None:
            parent_numbers = []

        # 处理当前层级的所有列表项
        num = 1  # 当前层级的起始编号
        for item in number_list.children:
            # 跳过空文本节点
            if isinstance(item, NavigableString) and item.strip() == "":
                continue

            # 判空：使用 get_text() 深度提取（含链接文字，跳过嵌套列表）
            full_text = ""
            for content in item.contents:
                if isinstance(content, NavigableString):
                    full_text += str(content)
                elif content.name in ("ul", "ol"):
                    break
                else:
                    full_text += content.get_text()
            full_text = full_text.strip()
            if not full_text:
                continue

            # 构建当前编号（如"1.2.3"）
            current_numbers = parent_numbers + [num]
            prefix = ".".join(str(n) for n in current_numbers)

            # 创建列表项段落：先写入编号，再通过 _render_li_inline 渲染内联（识别超链接）
            p = self.document.add_paragraph(f"{prefix}. ", style=None)
            self._render_li_inline(p, item)
            p.paragraph_format.left_indent = Pt(12 * current_level)  # 根据层级设置缩进
            p.paragraph_format.space_after = Pt(1)  # 设置段后间距

            # 处理嵌套列表（递归调用）
            if not isinstance(item, NavigableString):
                # 检查并处理嵌套的无序列表
                if item.find("ul"):
                    self.add_bullet_list(item.ul, current_level + 1, max_level)
                # 检查并处理嵌套的有序列表（传递当前编号用于子列表）
                if item.find("ol"):
                    self.add_number_list(item.ol, current_level + 1, max_level, current_numbers)
                # 检查并处理嵌套的TODO列表
                if full_text.startswith(("[ ]", "[x]")):
                    self.add_todo_list(item, current_level + 1, max_level)

            num += 1  # 递增当前层级编号

    def add_bullet_list(self, bullet_list, current_level=1, max_level=4):
        """
        动态生成无序列表，支持嵌套有序/TODO列表

        参数:
            bullet_list: BeautifulSoup解析的ul列表对象
            current_level: 当前嵌套层级，默认为1
            max_level: 最大嵌套层级，默认为4
        """
        from bs4 import NavigableString
        from docx.shared import Pt

        # 终止条件：防止无限递归
        if current_level > max_level:
            return

        # 配置不同层级的符号和缩进
        BULLET_SYMBOLS = ["• ", "◦ ", "▪ ", "▫ ", "→ ", "‣ "]
        symbol = BULLET_SYMBOLS[min(current_level - 1, len(BULLET_SYMBOLS) - 1)]  # 防止索引越界
        indent = Pt(12 * current_level)  # 根据层级设置缩进

        # 处理当前层级的所有列表项
        for item in bullet_list.children:
            # 跳过空文本节点
            if isinstance(item, NavigableString) and item.strip() == "":
                continue

            # 判空：使用 get_text() 深度提取（含链接文字，跳过嵌套列表）
            full_text = ""
            for content in item.contents:
                if isinstance(content, NavigableString):
                    full_text += str(content)
                elif content.name in ("ul", "ol"):
                    break
                else:
                    full_text += content.get_text()
            if not full_text.strip():
                continue

            # 创建列表项段落：先写入符号，再通过 _render_li_inline 渲染内联（识别超链接）
            p = self.document.add_paragraph(style=None)
            p.add_run(" " * (current_level - 1) * 2 + symbol)
            self._render_li_inline(p, item)
            p.paragraph_format.left_indent = indent  # 设置段落缩进
            p.paragraph_format.space_after = Pt(1)  # 设置段后间距

            # 处理嵌套列表（递归调用）
            if not isinstance(item, NavigableString):
                # 检查并处理嵌套的有序列表
                if item.find("ol"):
                    self.add_number_list(item.ol, current_level + 1, max_level)
                # 检查并处理嵌套的无序列表
                if item.find("ul"):
                    self.add_bullet_list(item.ul, current_level + 1, max_level)

    def add_todo_list(self, todo_list, current_level=1, max_level=3, parent_path=""):
        """
        动态生成TODO列表，支持嵌套

        参数:
            todo_list: BeautifulSoup解析的TODO列表对象
            current_level: 当前嵌套层级，默认为1
            max_level: 最大嵌套层级，默认为3
            parent_path: 父路径标识，用于防止重复处理
        """
        from docx.shared import Pt
        from bs4 import NavigableString

        # 终止条件：防止无限递归
        if current_level > max_level:
            return

        # 配置不同层级的符号和缩进
        BULLET_SYMBOLS = ["• ", "◦ ", "▪ ", "▫ ", "→ ", "‣ "]
        symbol = BULLET_SYMBOLS[min(current_level - 1, len(BULLET_SYMBOLS) - 1)]  # 防止索引越界
        indent = Pt(12 * current_level)  # 根据层级设置缩进

        # 处理当前层级的所有列表项
        for item in todo_list.children:
            # 跳过空文本节点
            if isinstance(item, NavigableString) and item.strip() == "":
                continue

            # 提取文本（忽略子标签内容）
            text_parts = []
            for content in item.contents:
                if isinstance(content, NavigableString):
                    text_parts.append(str(content).strip())
                else:
                    break  # 遇到第一个非文本子元素就停止

            text = "".join(text_parts).strip()
            # 跳过空文本项
            if not text:
                continue

            # === 关键改进：动态去重 ===
            # 生成唯一标识：父路径+当前文本+层级+符号，防止重复处理相同内容
            item_id = f"{parent_path}|{text}|{current_level}|{symbol}"
            if hasattr(self, '_processed_items'):
                if item_id in self._processed_items:
                    continue  # 如果已处理过，跳过避免重复
            else:
                self._processed_items = set()  # 初始化已处理项集合

            self._processed_items.add(item_id)  # 标记为已处理

            # 添加当前项到文档
            self._add_single_todo_item(text, symbol, indent)

    def _add_single_todo_item(self, text, symbol, indent):
        """
        添加单个TODO项到文档

        参数:
            text: 待处理的文本内容
            symbol: 当前层级使用的符号
            indent: 当前层级的缩进值
        """
        p = self.document.add_paragraph(style=None)
        # 根据文本内容添加不同的复选框状态
        if text.startswith("[x]"):
            p.add_run(f"{symbol}[√] ").font.name = "Consolas"  # 使用等宽字体
            p.add_run(text[3:].strip())  # 移除"[x]"前缀
        elif text.startswith("[ ]"):
            p.add_run(f"{symbol}[ ] ").font.name = "Consolas"  # 使用等宽字体
            p.add_run(text[3:].strip())  # 移除"[ ]"前缀
        else:
            p.add_run(f"{symbol}{text}")  # 普通文本项
        p.paragraph_format.left_indent = indent  # 设置段落缩进
        p.paragraph_format.space_after = Pt(1)  # 设置段后间距

    # 分割线，转换为 Word 中的分页符
    def add_split_line(self):
        self.document.add_page_break()

    # 超链接
    def add_link(self, p: Paragraph, text: str, href: str):
        debug("[link]:", text, "[href]:", href)
        add_hyperlink(p, href, text)
        # run = p.add_run(text)

    def _render_li_inline(self, p, item):
        """将 <li> 的内联内容渲染到段落 p 中。
        遇到嵌套的 <ul>/<ol> 则停止（返回 sentinel），由上层递归处理。
        返回 (wrote_any, should_stop) 元组。
        """
        from bs4 import NavigableString
        TRANSPARENT_TAGS = {"p", "span", "div"}

        def _walk(node):
            wrote_any = False
            for content in node.contents:
                if isinstance(content, NavigableString):
                    s = str(content)
                    if s and s != "\n":
                        p.add_run(s)
                        if s.strip():
                            wrote_any = True
                    continue
                if content.name in ("ul", "ol"):
                    return wrote_any, True
                if content.name in TRANSPARENT_TAGS:
                    child_wrote, should_stop = _walk(content)
                    wrote_any = wrote_any or child_wrote
                    if should_stop:
                        return wrote_any, True
                    continue
                # Use _render_inline for all other inline content
                child_wrote = self._render_inline(p, content)
                wrote_any = wrote_any or child_wrote
            return wrote_any, False

        wrote, _ = _walk(item)
        return wrote

    def add_paragraph(self, children, p_style: str = None, prefix: str = ""):
        """
        children: list|str
        一个段落内的元素（包括图片）。根据有无样式来划分，组成一个列表。
        有样式文字如加粗、斜体、图片、等。
        如`I am plain _while_ he is **bold**`将转为：
        ["I am plain", "while", "he is", "bold"]
        """
        p = self.document.add_paragraph(prefix, style=p_style)
        if type(children) == str:
            p.add_run(children)
            return p
        for elem in children.contents:  # 遍历一个段落内的所有元素
            if elem.name == "a":
                self.add_link(p, elem.string, elem["href"])
            elif elem.name == "img":
                self.add_picture(elem)
            elif elem.name is not None:  # 有字符样式的子串
                self.add_run(p, elem.string, elem.name)
            elif not elem.string == "\n":  # 无字符样式的子串
                self.add_run(p, elem)
        return p

    # from docx.enum.style import WD_STYLE
    def add_blockquote(self, children):
        # TODO 将引用块放在1x1的表格中，优化引用块的显示效果
        #  设置左侧缩进，上下行距
        table: Table = self.document.add_table(0, 1)
        row_cells = table.add_row().cells
        p = row_cells[0].paragraphs[0]

        for child in children.contents:
            if child.string != "\n":
                # self.add_paragraph(p, p_style=MDX_STYLE.BLOCKQUOTE)
                if type(child) == str:
                    p.add_run(child)
                    return p
                for elem in child.contents:  # 遍历一个段落内的所有元素
                    if elem.name == "a":
                        self.add_link(p, elem.string, elem["href"])
                    elif elem.name == "img":
                        self.add_picture(elem)
                    elif elem.name is not None:  # 有字符样式的子串
                        self.add_run(p, elem.string, elem.name)
                    elif not elem.string == "\n":  # 无字符样式的子串
                        self.add_run(p, elem)

        shading_elm_1 = parse_xml(r'<w:shd {} w:fill="efefef"/>'.format(nsdecls("w")))
        table.rows[0].cells[0]._tc.get_or_add_tcPr().append(shading_elm_1)
        # table_format = table.style.paragraph_format

        # 直接操作 Oxml 的方式设置左侧缩进和表格宽度
        # noinspection PyProtectedMember
        tbl_pr = table._element.xpath("w:tblPr")
        # if tbl_pr:
        # 左侧缩进
        # e = OxmlElement('w:tblInd')
        # e.set(qn('w:w'), "300")
        # e.set(qn('w:type'), 'dxa')
        # tbl_pr[0].append(e)
        # 设置表格宽度
        # w = OxmlElement('w:tblW')
        # w.set(qn('w:w'), "4700")
        # w.set(qn('w:type'), "pct")
        # tbl_pr[0].append(w)

    def _filter_style_tags(self, element):
        """专用过滤方法（仅用于ol/ul列表）"""
        from bs4 import BeautifulSoup

        tags_to_filter = ['strong', 'em', 'u', 'strike', 'sub', 'sup']
        for tag_name in tags_to_filter:
            for tag in element.find_all(tag_name):
                tag.replace_with(tag.get_text())
        return element



    def html2docx(self, html_string: str, docx_path: str):
        # 打开HTML
        soup = BeautifulSoup(html_string, "html.parser")
        body_tag = soup.contents[2]

        # Get the directory path for the output file
        output_dir = os.path.dirname(os.path.abspath(docx_path))

        # Change to the output directory if needed
        if output_dir:
            os.chdir(output_dir)
        # 逐个解析标签，并写到word中
        for root in body_tag.children:
            try:
                if root.string != "\n":
                    # debug("<%s>" % root.name)
                    if root.name == "p":  # 普通段落
                        self.add_paragraph(root, p_style=MDX_STYLE.PLAIN_TEXT)
                    if root.name == "blockquote":  # 引用块
                        self.add_blockquote(root)
                    if root.name == "ol":  # 数字列表
                        root = self._filter_style_tags(root)  # 仅过滤当前列表
                        self.add_number_list(root)
                    if root.name == "ul":  # 无序列表 或 TODO_List
                        root = self._filter_style_tags(root)  # 仅过滤当前列表
                        self.add_bullet_list(root)
                    if root.name == "table":  # 表格
                        self.add_table(root)
                    if root.name == "hr":
                        self.add_split_line()
                    if root.name == "pre":
                        self.add_code_block(root)
                    if (
                        root.name == "h1"
                        or root.name == "h2"
                        or root.name == "h3"
                        or root.name == "h4"
                        or root.name == "h5"
                    ):
                        # 传入 root 节点而非 root.string：标题内含嵌套标签时 tag.string 为 None
                        self.add_heading(root, root.name)
            except Exception as e:
                print(f"解析标签发生错误: {str(e)}")

        self.document.save(docx_path)
