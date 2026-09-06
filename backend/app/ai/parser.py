import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".csv", ".json", ".log",
    ".pdf", ".docx", ".doc",
    ".py", ".js", ".java", ".c", ".cpp", ".h", ".go", ".rs", ".rb", ".php",
    ".html", ".css", ".xml", ".yaml", ".yml", ".toml", ".ini", ".sh",
}

# 文件头签名检测
MIME_SIGNATURES = {
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/zip",  # docx 也是 zip
}


def detect_file_type(filename: str, content_header: bytes = b"") -> str:
    """检测文件真实类型"""
    ext = os.path.splitext(filename)[1].lower()

    # 文件头检测
    for sig, mime in MIME_SIGNATURES.items():
        if content_header.startswith(sig):
            if mime == "application/zip" and ext == ".docx":
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            return mime

    return ext


def is_allowed_extension(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def parse_text(content: str) -> list[dict]:
    """解析纯文本/Markdown/代码"""
    return [{"content": content, "page_no": None}]


def parse_pdf(file_path: str) -> list[dict]:
    """解析 PDF"""
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        chunks = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                chunks.append({"content": text, "page_no": i + 1})
        return chunks
    except ImportError:
        logger.warning("pypdf not installed, PDF parsing skipped")
        return []
    except Exception as e:
        logger.error("PDF parse error: %s", e)
        raise


def parse_docx(file_path: str) -> list[dict]:
    """解析 DOCX"""
    try:
        import docx2txt

        text = docx2txt.process(file_path) or ""
        text = text.strip()
        if not text:
            return []
        return [{"content": text, "page_no": None}]
    except ImportError:
        logger.warning("docx2txt not installed, DOCX parsing skipped")
        return []
    except Exception as e:
        logger.error("DOCX parse error: %s", e)
        raise


def clean_text(text: str) -> str:
    """清洗文本：去除多余空白、页眉页脚"""
    # 去除多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 去除行首行尾空白
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return text.strip()


def split_into_chunks(
    text: str,
    max_chunk_size: int = 500,
    overlap: int = 50,
    page_no: Optional[int] = None,
) -> list[dict]:
    """将文本按大小切片，带重叠窗口"""
    if len(text) <= max_chunk_size:
        return [{"content": text, "page_no": page_no}]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chunk_size
        chunk = text[start:end]

        # 尝试在句子或段落边界切分
        if end < len(text):
            last_period = max(
                chunk.rfind("。"),
                chunk.rfind(". "),
                chunk.rfind("\n"),
                chunk.rfind("；"),
                chunk.rfind("; "),
            )
            if last_period > max_chunk_size // 2:
                end = start + last_period + 1
                chunk = text[start:end]

        chunks.append({"content": chunk.strip(), "page_no": page_no})
        start = end - overlap
        if start >= len(text):
            break

    return chunks


def parse_file(file_path: str, original_name: str) -> list[dict]:
    """
    主解析入口
    返回: [{"content": str, "page_no": int|None}, ...]
    """
    ext = os.path.splitext(original_name)[1].lower()
    logger.info("Parsing file: %s (ext=%s)", original_name, ext)

    raw_chunks = []

    if ext in (".txt", ".md", ".markdown", ".csv", ".json", ".log",
               ".py", ".js", ".java", ".c", ".cpp", ".h", ".go", ".rs",
               ".rb", ".php", ".html", ".css", ".xml", ".yaml", ".yml",
               ".toml", ".ini", ".sh"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        raw_chunks = parse_text(content)

    elif ext == ".pdf":
        raw_chunks = parse_pdf(file_path)

    elif ext in (".docx", ".doc"):
        raw_chunks = parse_docx(file_path)

    else:
        logger.warning("Unsupported file type: %s", ext)
        return []

    # 清洗 + 切片
    final_chunks = []
    for raw in raw_chunks:
        cleaned = clean_text(raw["content"])
        if not cleaned:
            continue
        splitted = split_into_chunks(cleaned, page_no=raw.get("page_no"))
        final_chunks.extend(splitted)

    logger.info("Parsed %s: %d chunks", original_name, len(final_chunks))
    return final_chunks