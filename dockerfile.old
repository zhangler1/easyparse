FROM python:3.10-slim-bullseye

# 设置非交互模式
ENV DEBIAN_FRONTEND=noninteractive
ENV EXIFTOOL_PATH=/usr/bin/exiftool
ENV FFMPEG_PATH=/usr/bin/ffmpeg

# 换用清华源
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list && \
    sed -i 's|security.debian.org|mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list

# 安装运行时依赖（添加 procps 包以包含 watch 命令）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    exiftool \
    procps \
    zip \
    unzip \
    procps \
    vim \
    fontconfig \
    xfonts-utils \
    && rm -rf /var/lib/apt/lists/*

# 设置 pip 使用清华源
RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple/

WORKDIR /app
COPY . /app


RUN pip install --no-cache-dir \
    reportlab==3.6.11 \
    xmltodict==0.13.0 \
    loguru==0.7.2 \
    fontTools==4.43.1 \
    pyasn1==0.6.1 \
    fastapi \
    uvicorn \
    python-multipart \
    werkzeug \
    pdf2image \
    pdfminer.six \
    requests \     
    pillow  \
    apscheduler

# 安装 Python 依赖`
RUN pip --no-cache-dir install \
    -e /app/packages/markitdown[all] \
    -e /app/packages/markitdown-sample-plugin

RUN mkdir -p /usr/share/fonts/my_fonts && \
    unzip -j Fonts.zip -d /usr/share/fonts/my_fonts && \
    mkfontscale /usr/share/fonts/my_fonts && \
    rm Fonts.zip


# FROM easyparse:latest 

# WORKDIR /app

# # 基础参数（通常不变）
# ENTRYPOINT ["uvicorn", "server:app", "--host", "0.0.0.0"]

# # 默认端口和workers（可通过 docker run 覆盖）
# CMD ["--port", "5000", "--workers", "4"]