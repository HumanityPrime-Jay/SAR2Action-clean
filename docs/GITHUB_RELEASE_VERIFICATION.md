# GitHub release verification

Status: GITHUB PRIVATE RELEASE — PUBLISHED (2026-11-13).

| Gate | Result |
|---|---|
| Python 3.12 install and declared dependencies | PASS in ignored secure-copy .venv |
| Backend import / FastAPI health | PASS / HTTP 200 |
| Evidence schema and agent contract focused tests | PASS, 30 tests |
| Full pytest with authorized data in disposable test mirror | PASS with six skips; mirror deleted |
| Full pytest in publication copy without private data | PASS with explicit private-data skips; skipped checks remain unverified without data |
| Frontend tests / TypeScript / Vite build | PASS: 9/9, PASS, PASS |
| Clean npm ci with scripts disabled | PASS |
| npm audit | PASS: zero vulnerabilities |
| Staged secret and forbidden-path scan | PASS: 210 paths at last staged-tree scan |
| Trusted antivirus folder scan | UNVERIFIED coverage; acknowledged by release owner for private publication |
| GitHub CLI | Installed, v2.104.0 |
| GitHub account authentication | PASS: authenticated as HumanityPrime-Jay via GitHub CLI; HTTPS Git operations |
| Repository / visibility / main / commit / remote files | PASS: private HumanityPrime-Jay/SAR2Action, main, initial release commit 568465d, 210 files |
| Remote clone and install/build | Clone and content check PASS; clone install/build not rerun |

The original project and B-team data were not changed. The safe copy contains no original unsafe Git history. Private publication is verified; malware scan coverage remains unverified and is not labeled PASS.




## Historical Safety Scanner release gate, 2026-11-13

Provider: Microsoft Safety Scanner v1.463. Final run 23:11:20–23:20:11, "No infection found", return code 0. Coverage: NOT VERIFIED for D:\SAR2Action-github-safe because msert.log contains no target path and other checked Windows records supply no target evidence. Earlier Quick Scan found and removed VirTool:Win32/DefenderTamperingRestore on a Defender registry value. Malware Scan Gate: BLOCKED. GitHub account: HumanityPrime-Jay. Repository URL, visibility, commit SHA, push, remote check, and clone check: NOT RUN / unavailable. Python and frontend verification results above remain valid; only reports changed after those tests.

## Historical competition publication decision, 2026-11-13

Current authorization: user-requested PRIVATE publication to HumanityPrime-Jay/SAR2Action. Malware scan result: Microsoft Safety Scanner final run reported no infection, but D:\SAR2Action-github-safe coverage was not independently confirmed. Gate classification: UNVERIFIED and acknowledged; never recorded as PASS. The earlier Defender registry detection/remediation is disclosed in MALWARE_AUDIT.md. README commands and scientific/provenance descriptions were checked against source and the authorized local cache. Repository and remote verification details will be recorded only after actual GitHub operations.


## Verified private publication, 2026-11-13

Repository: https://github.com/HumanityPrime-Jay/SAR2Action
Owner: HumanityPrime-Jay
Visibility: PRIVATE
Default branch: main
Initial release commit: 568465d52253a7875a305756515a00e6ac184291
Initial committed files: 210
Push: successful without force.

GitHub API confirmed the initial main ref matched the local release commit, the remote tree was complete (210 blobs, not truncated), and backend, frontend, README, and pyproject.toml were present. The remote tree contained no credential file, .env, private B-team cache JSON, HDF5/GeoTIFF, model weights, Hermes runtime, Python virtual environment, or node_modules. GitHub returned a rendered README with a Mermaid output container and explicit provenance warning. The remote README blob matched the local Git blob. A fresh authenticated private clone matched the initial main SHA and 210-file tree; normalized README text matched. The clone was deleted after verification. Installation and build were validated in the release source copy, not repeated in the disposable clone.

Microsoft Safety Scanner's final run reported no infection, but coverage of the release directory remains unverified. The earlier Defender-tampering registry finding and reported removal remain disclosed. This is an acknowledged limitation of the user-authorized PRIVATE competition release, not a malware-scan PASS.
