"""Pure body rendering and local image files; no browser or network client."""
import base64
import hashlib
import struct
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from markdownify import markdownify
from .common import error_kind, public_content_link


def png_size(path):
    data = Path(path).read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("invalid_png")
    return struct.unpack(">II", data[16:24])


def image_extension(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("unsupported_image")


def render_markdown(html, title, base_url, output, fetch, image_nodes=(), image_indices=None):
    """Convert only the body; a failed image remains an explicit local marker."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script, style, iframe, object, embed"):
        tag.decompose()
    heading = soup.find("h1")
    if (heading and heading.get_text(" ", strip=True) == title.strip()
            and not any(str(text).strip() for text in heading.find_all_previous(string=True))):
        heading.decompose()
    images, failures, ignored = [], [], []
    observed = {node["index"]: node for node in image_nodes}
    image_dir = Path(output) / "images"
    image_dir.mkdir(exist_ok=True)
    tags = soup.select("img")
    if image_indices is not None and (len(image_indices) != len(tags)
            or len(set(image_indices)) != len(image_indices)
            or any(type(index) is not int or index < 0 for index in image_indices)):
        raise ValueError("body_image_mapping_mismatch")
    for position, tag in enumerate(tags):
        index = image_indices[position] if image_indices is not None else position
        source = tag.get("data-src") or tag.get("src") or ""
        node = observed.get(index, {})
        # Observed on the real sample: an unpopulated, hidden footer avatar,
        # not a missing article illustration. Unknown nodes remain failures.
        if (tag.get("id") == node.get("id") == "js_tail_panel_account_avatar"
                and not source and node.get("has_source") is False
                and node.get("visible") is False
                and all(node.get(key) == 0 for key in
                        ("natural_width", "natural_height", "rendered_width", "rendered_height"))):
            ignored.append({"index": index, "id": node["id"], "reason": "observed_hidden_empty_account_avatar"})
            tag.decompose()
            continue
        url = urljoin(base_url, source)
        try:
            if not source:
                raise ValueError("missing_image_source")
            if source.startswith("data:image/") and ";base64," in source:
                data = base64.b64decode(source.split(",", 1)[1], validate=True)
            else:
                if urlsplit(url).scheme not in {"https", "http"}:
                    raise ValueError("unsupported_image_url")
                data = fetch(url)
            if not data or len(data) > 25 * 1024 * 1024:
                raise ValueError("image_size_limit")
            digest = hashlib.sha256(data).hexdigest()
            relative = "images/" + digest[:24] + image_extension(data)
            destination = Path(output) / relative
            if not destination.exists():
                destination.write_bytes(data)
            tag["src"] = relative
            for attribute in ("srcset", "data-src", "data-original"):
                tag.attrs.pop(attribute, None)
            images.append({"index": index, "path": relative, "sha256": digest, "bytes": len(data)})
        except Exception as exc:
            known = {"missing_image_source", "unsupported_image", "unsupported_image_url", "image_size_limit", "image_http_error", "unverified_image_host"}
            reason = str(exc) if isinstance(exc, ValueError) and str(exc) in known else error_kind(exc)
            failures.append({"index": index, "reason": reason, "source_host": urlsplit(url).hostname if source else None})
            tag.replace_with(soup.new_string(f"[配图 {index + 1} 下载失败]"))
    for tag in soup.select("a[href]"):
        link = urljoin(base_url, tag["href"])
        tag["href"] = public_content_link(link) if urlsplit(link).scheme in {"https", "http"} else "#"
    content = markdownify(str(soup), heading_style="ATX", strip=["video", "audio"])
    (Path(output) / "article.md").write_text(f"# {title}\n\n{content.strip()}\n", encoding="utf-8")
    return {"images": images, "image_failures": failures, "ignored_image_nodes": ignored,
            "body_sha256": hashlib.sha256(content.encode()).hexdigest()}
