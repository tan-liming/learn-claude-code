import os
import subprocess
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."


def safe_path(p: str) -> Path:
    # WORKDIR 是当前工作目录（项目根目录）,/ p 将用户传入的路径拼接到工作目录后 .resolve() 将路径转换为绝对路径，并解析所有符号链接和相对引用（如 ../）
    path = (WORKDIR / p).resolve()
    # 检查解析后的路径是否仍在工作目录范围内
    # is_relative_to() 判断路径是否是 WORKDIR 的子路径
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(
            command,  # 执行这个命令
            shell=True,  # 通过 bash 执行
            cwd=WORKDIR,  # 在这个目录下执行
            capture_output=True,  # 捕获所有输出
            text=True,  # 返回字符串
            timeout=120  # 最多等 2 分钟
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: int = None) -> str:
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        # 将列表 lines 中的所有元素用换行符 \n 连接成一个字符串。
        return "\n".join(lines)[:50000]
    except Exception:
        return f"Error: {Exception}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"{old_text} not found in content"
        # 将第一次出现的 old_text 替换为 new_text
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error {e}"


TOOL_HANDLERS = {
    "bash": lambda **kwargs: run_bash(kwargs["command"]),
    # kwargs["path"]：行为：直接从字典中获取键为 "path" 的值
    # 如果键不存在：会抛出 KeyError 异常
    # 适用场景：确定该键一定存在（必填参数）
    # kwargs.get("limit")：行为：从字典中获取键为 "limit" 的值
    # 如果键不存在：不会报错，返回 None（或指定的默认值）
    # 适用场景：该键可能不存在（可选参数）
    # 直接访问
    # kwargs["path"]
    # 等同于
    # kwargs.get("path")  # 但如果 path 不存在会返回 None
    # 安全访问带默认值
    # kwargs.get("limit", 100)  # 如果 limit 不存在，返回 100
    # kwargs["path"]：必填参数，读取文件必须指定路径，没有路径就无法操作，所以直接访问
    # kwargs.get("limit")：可选参数，限制行数不是必须的，如果没有传就返回 None，run_read 函数会使用默认行为（不限制行数）
    # 这种设计体现了参数的必要性区分：必填参数用 []，可选参数用 .get()
    "read_file": lambda **kwargs: run_read(kwargs["path"], kwargs.get("limit")),
    "write_file": lambda **kwargs: run_write(kwargs["path"], kwargs["content"]),
    "edit_file": lambda **kwargs: run_edit(kwargs["path"], kwargs["old_text"], kwargs["new_text"]),
}

TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
]