"""Bounded verification of the two fixed samples, never article discovery."""

import time

from .common import SAMPLES, new_run, timestamp, write_json
from .http_archive import archive_http
from .state import exclusive


def check_samples(transport="python", browser=False, client=None):
    output = new_run("credentialed-samples")
    with exclusive(output.parent / ".sample-check.lock"):
        return _check_samples(output, transport, browser, client)


def _check_samples(output, transport, browser, client):
    results = []
    for sample, url in SAMPLES.items():
        if results:
            time.sleep(2)
        # archive_http checks target identity before any credentialed request.
        http = archive_http(sample, credentialed=True, transport=transport, **({"client": client} if client is not None else {}))
        page = {"status": "not_attempted", "reason": "browser_not_requested"}
        if browser:
            if (http.get("account_identity_verified") and http.get("status") == "partial"
                    and http.get("comments", {}).get("status") in {"loaded", "none", "unknown"}):
                from .archive import archive
                page = archive(url, credential_sample=sample)
            else:
                page["reason"] = "http_access_identity_or_comment_gate_not_passed"
        results.append({"sample": sample, "http": http, "original_page": page})
        # Save each finished sample, including failures, before the next one.
        write_json(output / "samples.json", {"at": timestamp(), "status": "not_verified",
                   "evidence": "live_credentialed_sample_attempt", "system_changes_made": False,
                   "formal_subscription_enabled": False, "results": results})
    return {"output": str(output), "status": "not_verified", "results": results,
            "evidence": "live_credentialed_sample_attempt", "system_changes_made": False,
            "formal_subscription_enabled": False}
