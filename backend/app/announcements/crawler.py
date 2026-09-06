from dataclasses import dataclass
from pathlib import Path
import tempfile

from backend.app.announcements.security import FetchConfig, SecureFetcher


@dataclass(slots=True)
class TemporaryDownload:
    path: Path
    content_type: str


async def download_temporary(url: str, *, allowed_hosts: set[str] | None = None, config: FetchConfig | None = None) -> TemporaryDownload:
    result = await SecureFetcher(config).fetch(url, allowed_hosts=allowed_hosts)
    suffix = ".bin"
    if "pdf" in result.content_type:
        suffix = ".pdf"
    elif "html" in result.content_type:
        suffix = ".html"
    fd, name = tempfile.mkstemp(prefix="announcement-", suffix=suffix)
    Path(name).write_bytes(result.content)
    import os
    os.close(fd)
    return TemporaryDownload(Path(name), result.content_type)

