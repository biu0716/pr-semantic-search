# Hugging Face / Zeabur · Docker 部署
# 服务监听平台注入的 $PORT（没有则 7860），自动以 DEMO_MODE 运行（走脱敏示例库 + 限流）。

FROM python:3.11-slim

# torch 运行需要的系统库（slim 镜像默认缺 libgomp，会报 libgomp.so.1 找不到 → 构建/启动崩溃）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 用非 root 用户，避免权限问题
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    HF_ENDPOINT=https://hf-mirror.com \
    DEMO_MODE=1

WORKDIR $HOME/app

# 装依赖（用清华镜像，国内服务器更快更稳）
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 注：embedding 模型在首次访问时下载（走上面的 HF_ENDPOINT 镜像），
# 不在构建期下载，这样构建一定能过；首次打开页面会多等十几秒，仅一次。

COPY --chown=user . .

EXPOSE 7860
# shell 形式，兼容平台注入的 $PORT；没有则默认 7860
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}
