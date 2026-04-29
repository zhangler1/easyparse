import docx
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn, nsdecls
from docx.shared import Pt, RGBColor
from docx.styles.style import _ParagraphStyle
from docx.enum.style import WD_STYLE_TYPE
from docx.styles.styles import Styles

from md2word.provider.simple_style import SimpleStyle
from md2word.utils.style_enum import MDX_STYLE


class StyleManager:
    def __init__(self, doc: Document, yaml_conf: dict):
        self.styles: Styles = doc.styles
        self.style_conf = yaml_conf
        self.doc = doc  # 保存文档引用

    def init_styles(self):
        # 设置heading 1~4
        for i in range(1, 7):
            s = SimpleStyle(
                f"WPSHeading{i}",  # 第一个参数是样式名称
                f"Heading {i}",  # 第二个参数是基础样式名
                self.style_conf[f"h{i}"]  # 第三个参数是样式配置
            )
            self.set_style(s)

        # 设置Normal样式
        s = SimpleStyle(
            MDX_STYLE.PLAIN_TEXT,  # 样式名称
            "Normal",  # 基础样式名
            self.style_conf["normal"]  # 样式配置
        )
        self.set_style(s)

        # 可选：设置其他样式
        self._fix_wps_heading_styles()  # 专门修复WPS标题问题

    def set_style(self, _style: SimpleStyle):
        # 创建或获取样式
        if _style.style_name not in self.styles:
            new_style = self.styles.add_style(_style.style_name, WD_STYLE_TYPE.PARAGRAPH)
            new_style.base_style = self.styles[_style.base_style_name]
        else:
            new_style = self.styles[_style.style_name]

        # 通用样式设置
        new_style.quick_style = True

        # 字体设置
        self._set_font_properties(new_style, _style)

        # 段落设置
        self._set_paragraph_properties(new_style, _style)

        return new_style

    def _set_font_properties(self, style, _style):
        """专门处理字体设置，解决WPS兼容性问题"""
        # 基础字体设置
        style.font.name = _style.font_default
        style.font.size = Pt(_style.font_size)
        style.font.color.rgb = RGBColor.from_string(_style.font_color)

        # 显式设置所有字体类型（解决WPS问题）
        rpr = style._element.get_or_add_rPr()
        rfonts = OxmlElement('w:rFonts')

        # 设置所有可能的字体属性
        rfonts.set(qn('w:ascii'), _style.font_default)  # 西文字体
        rfonts.set(qn('w:hAnsi'), _style.font_default)  # 拉丁字体
        rfonts.set(qn('w:eastAsia'), _style.font_east_asia)  # 中文字体
        rfonts.set(qn('w:cs'), _style.font_east_asia)  # 复杂脚本字体

        # 移除可能存在的旧字体设置
        for e in rpr.xpath('.//w:rFonts'):
            rpr.remove(e)
        rpr.append(rfonts)

        # 字体样式
        style.font.bold = _style.font_bold
        style.font.italic = _style.font_italic
        style.font.underline = _style.font_underline
        style.font.strike = _style.font_strike

    def _set_paragraph_properties(self, style, _style):
        """段落属性设置"""
        p_format = style.paragraph_format

        # 缩进设置
        p_format.first_line_indent = Pt(_style.font_size * _style.first_line_indent)

        # 间距设置
        p_format.space_before = Pt(_style.space_before)
        p_format.space_after = Pt(_style.space_after)
        p_format.line_spacing = _style.line_spacing

        # 分页控制
        p_format.keep_together = False
        p_format.keep_with_next = False

    def _fix_wps_heading_styles(self):
        """专门修复WPS标题样式问题"""
        for i in range(1, 5):
            style_name = f"Heading{i}"
            if style_name in self.styles:
                style = self.styles[style_name]

                # 强制重新应用字体设置
                font_conf = self.style_conf[f"h{i}"]["font"]
                style.font.name = font_conf["default"]
                style._element.rPr.rFonts.set(qn('w:eastAsia'), font_conf["east-asia"])

                # 确保样式可见
                style.quick_style = True
                style.hidden = False
