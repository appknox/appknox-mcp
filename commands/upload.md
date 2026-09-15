---
description: Upload an app binary to the Appknox VAPT platform and start a scan
argument-hint: "<binary-path>"
---

# Appknox Upload

Upload a built app binary (APK / IPA / AAB, etc.) to the Appknox VAPT platform.
This is the re-upload half of the workflow's step 7 (RE-SCAN, ground truth) — see
the `appknox` MCP server's instructions. After fixing vulnerabilities and building
a fresh binary, upload it here, then run `/appknox:verify` once the scan
completes to confirm the findings are gone.

Arguments:
- `$1` — **binary-path** (required): path to the built binary on this machine.

Print each phase's status line exactly (`⏳` working, `✓` success, `✗` failure).

## Phase 0 — Locate the binary

If `$1` is missing or the file doesn't exist, print `✗ No binary at "<$1>" — pass
the path to your built APK/IPA` and stop. If it looks like a build directory
rather than a file, ask which artifact to upload.

## Phase 1 — Upload

Print `⏳ Uploading <basename> to Appknox…`, then call
`upload_binary(file_path=$1)`. This requests a presigned URL, uploads the file,
triggers validation + scan, and waits until Appknox assigns a `file_id`.

- On error, print `✗ <message>` and stop. Common causes: the service account
  lacks the **App: Upload** scope, or the binary failed validation (not a valid
  app package).
- On success, print `✓ Uploaded — new build #<file_id> (<file_name>) · scan
  started`.

## Phase 2 — What next

The scan and KnoxIQ analysis now run **asynchronously** — the `file_id` exists but
results are not ready yet. Tell the user:

> Build #<file_id> is scanning. Once it finishes, run `/appknox:verify <file_id>`
> to confirm your fixes (or `/appknox:verify <file_id> <old_file_id>` to diff
> against the build you fixed). You can check progress any time with
> `knoxiq_get_scan_status(<file_id>)`.

Do **not** claim any vulnerability is fixed here — uploading only starts the scan;
`/appknox:verify` reports the ground truth once it's ready.
