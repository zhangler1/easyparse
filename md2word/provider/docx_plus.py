import docx
from docx.oxml.ns import qn
from docx.oxml.shared import OxmlElement

def add_hyperlink(paragraph, url, text):
    """在段落中插入一个超链接（蓝色下划线文字）。

    正确的 OOXML 结构：
      <w:p>
        <w:hyperlink r:id="...">
          <w:r>
            <w:rPr>
              <w:color w:val="0000FF"/>
              <w:u w:val="single"/>
            </w:rPr>
            <w:t>文字</w:t>
          </w:r>
        </w:hyperlink>
      </w:p>

    原实现把同一个 hyperlink 节点先 append 到 paragraph 再 append 到 run 内，
    lxml 节点只能有一个父节点，最终 hyperlink 会被嵌套在空 run 内，
    形成非法结构 <w:r><w:hyperlink>...</w:hyperlink></w:r>，Word 不会渲染。
    """
    # 注册外部关系，获取 r:id
    part = paragraph.part
    r_id = part.relate_to(
        url,
        docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK,
        is_external=True,
    )

    # 创建 <w:hyperlink r:id="...">
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    # 内部 <w:r>
    new_run = OxmlElement("w:r")

    # <w:rPr>：颜色 + 下划线
    rPr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0000FF")
    rPr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rPr.append(underline)
    new_run.append(rPr)

    # <w:t>
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text if text else url
    new_run.append(t)

    hyperlink.append(new_run)
    # 关键：hyperlink 必须是 <w:p> 的直接子元素
    paragraph._p.append(hyperlink)
    return hyperlink

