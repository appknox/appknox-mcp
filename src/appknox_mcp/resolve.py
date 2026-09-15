"""Resolve an app's package_name to its latest scanned Appknox file_id."""

from typing import Any

from appknox_mcp.app import client, mcp
from appknox_mcp.client import AppknoxAPIError


@mcp.tool
async def resolve_latest_file(
    package_name: str, platform: str | None = None
) -> dict[str, Any]:
    """Resolve an app identifier (+ platform) to its Appknox project and latest file_id.

    Pass the app's identifier (Android ``applicationId`` or iOS bundle id) and
    the ``platform`` you detected it for (``"android"`` or ``"ios"``). Platform
    is what disambiguates when an Android and an iOS project share the same
    identifier — determine it from the repo (which file you read the identifier
    from), do not let the API guess. Returns the matching project and its most
    recent file. If several projects still share the identifier, the one with
    the newest scanned build is used. Raises ``AppknoxAPIError`` on no match
    or no completed scan.
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
