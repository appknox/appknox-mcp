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
    project that share an identifier. Only an exact (case-insensitive) match of
    the identifier counts; projects whose identifier merely contains it are
    listed in the error instead. When several projects match exactly, the one
    with the most recently scanned build is returned. Returns an error when no
    project matches or no build has completed a scan.
    """
    wanted = package_name.strip()
    candidates = await client.list_projects(wanted)
    # The API's package_name filter is a substring match (com.example.app also
    # returns com.example.app.beta); only an exact identifier match counts.
    # Case-insensitive: iOS bundle ids are, and Appknox stores them as given.
    projects = [
        p
        for p in candidates
        if (p.package_name or "").strip().lower() == wanted.lower()
    ]
    if platform is not None:
        want = platform.strip().lower()
        projects = [p for p in projects if (p.platform_display or "").lower() == want]

    if not projects:
        scope = f" ({platform})" if platform else ""
        near = sorted({p.package_name for p in candidates if p.package_name})
        hint = (
            f" Projects with similar identifiers: {', '.join(near[:10])}."
            if near
            else " Upload a build for this app first."
        )
        raise AppknoxAPIError(
            f"No Appknox project found for package_name '{wanted}'{scope}.{hint}"
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
