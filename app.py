"""
PR Agent —— FastAPI 后端入口。

运行：
    uvicorn app:app --reload --port 8000

跑起来后，浏览器打开 http://127.0.0.1:8000/docs
就能看到全部接口，还能直接在网页上点按钮测试，不用写任何前端代码。

这个后端完全不依赖 Streamlit；你原来的 streamlit_app.py 不受影响，照样能跑。
"""

from io import BytesIO

import os
import time
from collections import defaultdict
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from services.retrieval import search as retrieve
from services.generation import (
    generate_pr_two_stage,
    regenerate_generate_section,
    split_two_stage_result,
    GENERATE_SECTION_HEADERS,
)
from services.refine import refine_existing_result, run_refine_with_uploaded_text
from services.terms import parse_terms_table
from services.documents import read_uploaded_text
from services.export import get_export_payload


app = FastAPI(title="PR Agent API", version="1.0")

# 允许前端（比如 GitHub Pages 上的页面）跨域调用。
# 上线后建议把 "*" 换成你前端的具体域名。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================
# 限流（只在 DEMO_MODE=1 时生效，保护你的 API key 不被刷）
# 本地自己用（不设 DEMO_MODE）完全不限。
# ==============================
DEMO_MODE = os.environ.get("DEMO_MODE") == "1"
RL_PER_MIN = int(os.environ.get("RL_PER_MIN", "6"))    # 每访客每分钟
RL_PER_DAY = int(os.environ.get("RL_PER_DAY", "60"))   # 每访客每天
_hits: dict[str, list[float]] = defaultdict(list)


def _client_key(request: Request) -> str:
    # 线上多在反代后面，真实 IP 在 X-Forwarded-For 里
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request):
    """给烧钱的 LLM 接口用的简单限流依赖。"""
    if not DEMO_MODE:
        return
    key = _client_key(request)
    now = time.time()
    recent = [t for t in _hits[key] if now - t < 86400]
    if sum(1 for t in recent if now - t < 60) >= RL_PER_MIN:
        raise HTTPException(429, f"操作太频繁啦，歇一分钟再试（演示版每分钟限 {RL_PER_MIN} 次）")
    if len(recent) >= RL_PER_DAY:
        raise HTTPException(429, f"今天的演示额度用完了（每人每天 {RL_PER_DAY} 次），明天再来玩～")
    recent.append(now)
    _hits[key] = recent


# ==============================
# 请求体定义（前端发什么、字段叫什么，一目了然）
# ==============================

class SearchRequest(BaseModel):
    query: str
    k: int = 5


class GenerateRequest(BaseModel):
    query: str
    top_k: int = 5
    extra_terms: dict[str, str] | None = None
    uploaded_text: str | None = None
    source_name: str | None = None


class RegenerateSectionRequest(BaseModel):
    section_key: str  # angles / titles / social
    query: str
    current_result: str
    top_k: int = 5
    extra_terms: dict[str, str] | None = None
    uploaded_text: str | None = None
    source_name: str | None = None


class RefineRequest(BaseModel):
    mode: str           # generate / check / normalize / rewrite ...
    current_result: str
    instruction: str


class RefineDocRequest(BaseModel):
    mode: str           # check / normalize / rewrite
    source_text: str
    instruction: str = ""
    extra_terms: dict[str, str] | None = None


class ExportRequest(BaseModel):
    text: str
    format: str = "docx"   # docx / md / txt
    title: str = "PR Agent 导出结果"


# ==============================
# 接口
# ==============================

@app.get("/")
def index():
    """打开 http://127.0.0.1:8000/ 就是前端页面。"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/health")
def health():
    """探活，确认后端起来了。"""
    return {"ok": True}


@app.post("/api/search")
def api_search(req: SearchRequest):
    results = retrieve(req.query, req.k)
    return {"results": results}


@app.post("/api/generate", dependencies=[Depends(rate_limit)])
def api_generate(req: GenerateRequest):
    full = generate_pr_two_stage(
        query=req.query,
        top_k=req.top_k,
        extra_terms=req.extra_terms,
        uploaded_text=req.uploaded_text,
        source_name=req.source_name,
    )
    stage1, stage2 = split_two_stage_result(full)
    return {"result": full, "stage1": stage1, "stage2": stage2}


@app.post("/api/generate/regenerate-section", dependencies=[Depends(rate_limit)])
def api_regenerate_section(req: RegenerateSectionRequest):
    if req.section_key not in GENERATE_SECTION_HEADERS:
        raise HTTPException(
            status_code=400,
            detail=f"section_key 仅支持: {list(GENERATE_SECTION_HEADERS)}",
        )
    try:
        result = regenerate_generate_section(
            section_key=req.section_key,
            query=req.query,
            current_result=req.current_result,
            top_k=req.top_k,
            extra_terms=req.extra_terms,
            uploaded_text=req.uploaded_text,
            source_name=req.source_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"result": result}


@app.post("/api/refine", dependencies=[Depends(rate_limit)])
def api_refine(req: RefineRequest):
    result = refine_existing_result(
        mode=req.mode,
        current_result=req.current_result,
        instruction=req.instruction,
    )
    return {"result": result}


@app.post("/api/refine-doc", dependencies=[Depends(rate_limit)])
def api_refine_doc(req: RefineDocRequest):
    result = run_refine_with_uploaded_text(
        mode=req.mode,
        source_text=req.source_text,
        instruction_text=req.instruction,
        extra_terms=req.extra_terms,
    )
    return {"result": result}


@app.post("/api/upload/read")
async def api_upload_read(file: UploadFile = File(...)):
    file_bytes = await file.read()
    try:
        text = read_uploaded_text(file_bytes, file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"text": text, "source_name": file.filename}


@app.post("/api/upload/terms")
async def api_upload_terms(file: UploadFile = File(...)):
    file_bytes = await file.read()
    try:
        terms = parse_terms_table(file_bytes, file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"terms": terms}


@app.post("/api/export")
def api_export(req: ExportRequest):
    content, mime, filename = get_export_payload(req.text, req.format, req.title)
    return StreamingResponse(
        BytesIO(content),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
