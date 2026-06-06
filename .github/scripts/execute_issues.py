"""
Claude Haiku GitHub Issue Executor
Runs in GitHub Actions, reads open issues, executes them via Claude API with tool use.
"""
import os
import json
import subprocess
import requests
import anthropic

REPO = os.environ["REPO"]
GH_TOKEN = os.environ["GH_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

GH_HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── Tools для Claude ────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "read_file",
        "description": "Read contents of a file in the repository",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write or overwrite a file in the repository",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root"},
                "content": {"type": "string", "description": "Full file content to write"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path relative to repo root", "default": "."}
            }
        }
    },
    {
        "name": "run_shell",
        "description": "Run a shell command (git, gh, python, etc.). Returns stdout+stderr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"}
            },
            "required": ["command"]
        }
    }
]

# ── Tool executors ──────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"ERROR: {e}"


def write_file(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"OK: written {len(content)} chars to {path}"
    except Exception as e:
        return f"ERROR: {e}"


def list_files(path: str = ".") -> str:
    try:
        result = subprocess.run(
            ["find", path, "-type", "f", "-not", "-path", "*/.git/*"],
            capture_output=True, text=True
        )
        return result.stdout[:3000]
    except Exception as e:
        return f"ERROR: {e}"


def run_shell(command: str) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60
        )
        out = result.stdout + result.stderr
        return out[:3000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out"
    except Exception as e:
        return f"ERROR: {e}"


def execute_tool(name: str, inputs: dict) -> str:
    if name == "read_file":
        return read_file(inputs["path"])
    elif name == "write_file":
        return write_file(inputs["path"], inputs["content"])
    elif name == "list_files":
        return list_files(inputs.get("path", "."))
    elif name == "run_shell":
        return run_shell(inputs["command"])
    return f"ERROR: unknown tool {name}"


# ── GitHub API ──────────────────────────────────────────────────────────────

def get_open_issues() -> list[dict]:
    url = f"https://api.github.com/repos/{REPO}/issues"
    resp = requests.get(url, headers=GH_HEADERS, params={"state": "open", "per_page": 10})
    resp.raise_for_status()
    # фильтруем PR (у них есть pull_request поле)
    return [i for i in resp.json() if "pull_request" not in i]


def close_issue(number: int, comment: str) -> None:
    # Добавить комментарий
    requests.post(
        f"https://api.github.com/repos/{REPO}/issues/{number}/comments",
        headers=GH_HEADERS,
        json={"body": comment}
    )
    # Закрыть issue
    requests.patch(
        f"https://api.github.com/repos/{REPO}/issues/{number}",
        headers=GH_HEADERS,
        json={"state": "closed"}
    )


def add_comment(number: int, comment: str) -> None:
    requests.post(
        f"https://api.github.com/repos/{REPO}/issues/{number}/comments",
        headers=GH_HEADERS,
        json={"body": comment}
    )


# ── Claude agent ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an autonomous coding agent working on the Armada Company v2 project.
The project is a turn-based naval tactics web game: Python 3.12 + FastAPI backend, Vanilla JS + Canvas frontend.

Project structure:
- armada/domain/ — game logic (enums, models, factories, movement, modules, battle_loop, ai)
- armada/api/ — REST API (game.py, main.py)
- static/ — frontend (index.html, game.js)
- docs/ — documentation

Your job: read the GitHub issue, understand what needs to be implemented or fixed, make the changes, commit them.

Rules:
1. Always read existing files before editing them
2. Make minimal, focused changes — only what the issue asks
3. After making changes, run: git add -A && git commit -m "fix: <description> (closes #<issue_number>)"
4. If you cannot implement something, explain why in a comment — don't close the issue
5. Write commit messages in English

When done, respond with either:
- "DONE: <brief summary of changes made>"
- "SKIP: <reason why this issue cannot be completed>"
"""


def run_agent_on_issue(issue: dict) -> str:
    """Run Claude Haiku agent on a single issue. Returns 'DONE:...' or 'SKIP:...'"""
    number = issue["number"]
    title = issue["title"]
    body = issue["body"] or ""

    print(f"\n{'='*60}")
    print(f"Processing issue #{number}: {title}")
    print(f"{'='*60}")

    user_message = f"""GitHub Issue #{number}: {title}

{body}

Please implement this issue. Start by listing the project files to understand the structure, then read relevant files, make the changes, and commit."""

    messages = [{"role": "user", "content": user_message}]

    # Agentic loop
    for iteration in range(20):  # максимум 20 итераций
        print(f"  Iteration {iteration + 1}...")

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Добавить ответ ассистента в историю
        messages.append({"role": "assistant", "content": response.content})

        # Проверить стоп-условие
        if response.stop_reason == "end_turn":
            # Собрать финальный текст
            final_text = " ".join(
                block.text for block in response.content
                if hasattr(block, "text")
            )
            print(f"  Agent finished: {final_text[:200]}")
            return final_text

        # Выполнить tool calls
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  Tool: {block.name}({list(block.input.keys())})")
                    result = execute_tool(block.name, block.input)
                    print(f"  Result: {result[:100]}...")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            print(f"  Unexpected stop_reason: {response.stop_reason}")
            break

    return "SKIP: reached iteration limit without completing"


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("Claude Haiku Issue Executor starting...")
    issues = get_open_issues()
    print(f"Found {len(issues)} open issue(s)")

    if not issues:
        print("No open issues. Done.")
        return

    for issue in issues:
        number = issue["number"]
        try:
            result = run_agent_on_issue(issue)

            if result.startswith("DONE"):
                close_issue(number, f"✅ Automated fix applied by Claude Haiku agent.\n\n{result}")
                print(f"✅ Issue #{number} closed")
            else:
                add_comment(number, f"⚠️ Agent could not complete this issue:\n\n{result}")
                print(f"⚠️ Issue #{number} skipped: {result[:100]}")

        except Exception as e:
            print(f"❌ Error on issue #{number}: {e}")
            add_comment(number, f"❌ Agent error: {e}")


if __name__ == "__main__":
    main()
