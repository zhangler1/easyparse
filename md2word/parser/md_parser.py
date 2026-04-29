import markdown

from md2word.parser.ext_md_syntax import ExtMdSyntax


def md2html(in_path: str):
    with open(in_path, "r", encoding="utf-8") as input_file:
        text = input_file.read()

    html = markdown.markdown(text, extensions=[ExtMdSyntax(), 'tables', 'sane_lists', 'fenced_code'])

    html_string = f"""<head><meta charset="utf-8"></head>\n<body>\n{html}\n</body>"""
    return html_string

if __name__ == '__main__':
    md2html("example.md", "example.html")
