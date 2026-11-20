"""User-invoked MCP prompts carrying the fix-and-verify workflow.

Prompts run only when the user picks them (they show up as slash commands in
clients that support MCP prompts), so the workflow reaches every client as the
user's own request — not as server instructions steering the model, which
connector directories reject. The text comes from instructions.py, the single
source of truth for the workflow.
"""

from appknox_mcp.app import mcp
from appknox_mcp.instructions import workflow_text

# Set by server._run_remote: the upload step differs in remote mode.
_mode = {"remote": False}


def set_remote_mode(remote: bool) -> None:
    _mode["remote"] = remote


def _with_workflow(task: str) -> str:
    return f"{task}\n\n---\n\n{workflow_text(_mode['remote'])}"


@mcp.prompt(
    name="triage",
    title="Triage Appknox findings",
    description="List the vulnerabilities Appknox found in this app's latest build, "
    "most exploitable first, and pick which to fix.",
)
def triage(package_name: str = "", platform: str = "") -> str:
    target = (
        f" for {package_name}" + (f" ({platform})" if platform else "")
        if package_name
        else " for this repository's app"
    )
    return _with_workflow(
        f"Triage the Appknox KnoxIQ findings{target}. Follow steps 1-4 of the "
        "workflow below, then stop and wait for my selection."
    )


@mcp.prompt(
    name="fix",
    title="Fix Appknox findings",
    description="Fix selected Appknox findings in this repository and verify each "
    "with its proof-of-concept.",
)
def fix(selection: str, file_id: str = "") -> str:
    build = f" in build {file_id}" if file_id else ""
    return _with_workflow(
        f"Fix these Appknox findings{build}: {selection}. Follow steps 5-6 of the "
        "workflow below (resolve the build first with steps 1-2 if no file_id is "
        "known)."
    )


@mcp.prompt(
    name="verify",
    title="Verify fixes with a re-scan",
    description="Upload the rebuilt app, wait for the Appknox re-scan, and report "
    "which findings were resolved.",
)
def verify(binary_path: str = "", new_file_id: str = "") -> str:
    if new_file_id:
        task = f"Verify my fixes against re-scanned build {new_file_id}."
    elif binary_path:
        task = f"Upload {binary_path} for re-scan and verify my fixes."
    else:
        task = "Upload my rebuilt app for re-scan and verify my fixes."
    return _with_workflow(f"{task} Follow step 7 of the workflow below.")
