# Hugging Face Spaces · Docker 部署
# 服务监听 7860（HF Spaces 默认端口），自动以 DEMO_MODE 运行（走脱敏示例库 + 限流）。

FROM python:3.11-slim

# 用非 root 用户，避免 HF 上的权限问题
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    DEMO_MODE=1

WORKDIR $HOME/app

# 国内服务器构建用镜像，避免连 huggingface.co / PyPI 超时
ENV HF_ENDPOINT=https://hf-mirror.com

# 先装依赖（利用缓存层）
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 把 embedding 模型预先下载烤进镜像（走 hf-mirror 镜像），首次访问就不用等下载
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

# 再拷贝项目代码（含 data/sample/ 示例索引）
COPY --chown=user . .

EXPOSE 7860
# 用 shell 形式，兼容平台注入的 $PORT（Zeabur 等）；没有就默认 7860（HF）
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}
