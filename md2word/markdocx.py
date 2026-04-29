import argparse
import os
import sys

import yaml
from yaml import FullLoader

from md2word.parser.md_parser import md2html

from md2word.provider.docx_processor import DocxProcessor

config: dict = {"version": "0.1.0"}


# 生成资源文件目录访问路径
def resource_path(relative_path):
    if getattr(sys, "frozen", False):  # 是否Bundle Resource
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def load_style_config():
    """Load YAML style config once and cache it."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 构建配置文件的完整路径（指向 md2word/config/default_style.yaml）
    config_path = os.path.join(script_dir, "config", "default_style.yaml")
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.load(file, FullLoader)


def md2word(inputFile, outputFile):
    htmlString = md2html(inputFile)
    processor = DocxProcessor(style_conf=load_style_config())  # 每次新建实例
    processor.html2docx(htmlString, outputFile)


if __name__ == "__main__":
    md2word("./example.md", "./a.docx")
