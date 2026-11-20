"""Resolve an app's package_name to its latest scanned Appknox file_id."""

from typing import Any

from appknox_mcp.app import READ_ONLY, client, mcp
from appknox_mcp.client import AppknoxAPIError


@mcp.tool(title="Resolve latest build", annotations=READ_ONLY)
async def resolve_latest_file(
    package_name: str, platform: str | None = None
) -> dict[str, Any]:
    """Find the Appknox project for an app and return its latest build.

    ``package_name`` is the Android applicationId or the iOS bundle id.
    ``platform`` is "android" or "ios"; it tells apart an Android and an iOS
    project that share an identifier. When several projects match, the one with
    the most recently scanned build is returned. Returns an error when no
    project matches or no build has completed a scan.
    """
    projects = await client.list_projects(package_name)
    if platform is not None:
        want = platform.strip().lower()
        projects = [p for p in projects if (p.platform_display or "").lower() == want]

    if not projects:
        scope = f" ({platform})" if platform else ""
        raise AppknoxAPIError(
            f"No Appknox project found for package_name '{package_name}'{scope}. "
            "Upload a build for this app first."
        )

    # Several projects may share the identifier — use the one with the newest build.
    scanned = [p for p in projects if p.last_file_id]
    if not scanned:
        raise AppknoxAPIError(
            f"No scanned file yet for package_name '{package_name}'. "
            "Upload a build first."
        )

    project = max(scanned, key=lambda p: p.last_file_id or 0)
    return {
        "package_name": project.package_name,
        "project_id": project.id,
        "platform": project.platform,
        "platform_display": project.platform_display,
        "file_id": project.last_file_id,
        "file_count": project.file_count,
    }
