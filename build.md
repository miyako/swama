---
layout: default
title: Native builds
description: Build the Swama CLI from pinned upstream source and understand its runtime resources, signing and provenance.
build: true
---

# Native builds and provenance

For a ready-to-run, signed download, start with [component {{ site.component_version }}]({{ '/#downloads' | relative_url }}). Its native CLI can also be used without 4D. This page covers source-build artifacts and how they differ from that signed release.

## CLI artifacts

The [Native CLI workflow]({{ site.github.repository_url }}/actions/workflows/native-build.yml) produces `swama-native-macos-arm64` Actions artifacts, retained 30 days; downloading requires a GitHub login. Extract the artifact ZIP, then its `.tar.gz`.

Standalone native publication is a separate, explicit main-branch [Publish native CLI]({{ site.github.repository_url }}/actions/workflows/native-release.yml) request with `publish_release` enabled. Such releases use `native-v<version>-<sha12>` tags, never overwrite a release and never replace the latest 4D component release. **The published {{ site.component_version }} download is a 4D component**, not a standalone native archive.

Source-build CLI packages are ad-hoc signed, **not Developer ID signed or notarized**. Their copied Swift runtime retains its vendor signature. Managed Macs or Gatekeeper may require your organization's approval. The CLI inside the published signed component is re-signed with the component's Developer ID.

## Reproducible source identity

The default is upstream **2.5.1** at [`545894b3e9bda3a18453bf46fbff9e2f55f6f363`](https://github.com/Trans-N-ai/swama/commit/545894b3e9bda3a18453bf46fbff9e2f55f6f363), resolved from upstream `main` on 2026-11-02 and pinned in [`native/upstream.json`]({{ site.github.repository_url }}/blob/main/native/upstream.json). It is newer than the identically versioned `v2.5.1` tag; the version alone is not a source identity.

SwiftPM uses `--force-resolved-versions`. Lockfile drift and unbundled non-system dynamic-library imports fail the build. The manifest records the requested ref, resolved commit, dependency revisions, compiler/SDK, deployment target, Metal source hashes, runtime hashes and packaging revision.

## Build locally

Use an Apple Silicon Mac, **Xcode 26.6 including Metal tools and Swift 6.3.3**, and Python 3.12+. CI selects that Xcode on `macos-26`. Upstream's package declares Swift 6.2 as its minimum and notes a Swift 6.2.1 compiler issue; older toolchains are not validated here.

```sh
python3 -m unittest discover -s native -p 'test_*.py'
python3 native/build.py
# Optional evaluation build: upstream tag, branch or full SHA
python3 native/build.py --upstream-ref main --output dist/evaluation
```

Default output is `dist/native/swama-2.5.1-545894b3e9bd-macos-arm64.tar.gz` and `.sha256`. Use a fresh output directory for each run. `.native-build` keeps the source/dependency cache. A ref override resolves once to a recorded commit; it does not change the default pin or 4D dependency versions.

Install the entire verified archive for local 4D development:

```sh
python3 native/install.py dist/native/*.tar.gz swama/Resources/bin/macOS
```

This replaces the whole resource directory, preventing stale bundles. The binary tracked in Git is legacy; cloning the repository does not rebuild it.

## Runtime resources

Keep the complete distribution together:

- `swama`, all SwiftPM `.bundle` directories and the freshly compiled MLX `mlx.metallib`.
- Required Swift compatibility libraries, `Package.resolved` and upstream/dependency/runtime licenses.
- `BUILD_INFO.json` and the complete `SHA256SUMS` inventory.

Apple's `swift-stdlib-tool` copies required runtime libraries; the source-build packager removes Xcode-specific search paths before ad-hoc signing the CLI. The installed distribution does not require Xcode. Model weights are downloaded separately.

## Signed component integrity

Published component {{ site.component_version }} passed Developer ID signing with secure timestamps and hardened runtime, Apple notarization **Accepted**, validated DMG stapling and Gatekeeper assessment. The DMG has the offline ticket; the ZIP preserves the same signed component. Both archives passed nested-signature, complete final-byte and CLI/HTTP checks.

| File | What it describes |
|---|---|
| `Resources/bin/macOS/BUILD_INFO.json` | Native source-build provenance, before component signing |
| `Resources/bin/macOS/SOURCE_BUILD_SHA256SUMS` | Verified pre-sign input; not the final signed bytes |
| Component and native `SHA256SUMS` | Complete post-sign file inventories |
| `Resources/RELEASE_INFO.json` | Component version commit, workflow revision and run URL |
| Release `SHA256SUMS` | Final archive and verification-report hashes |
| Release `NOTARIZATION.json` / `SIGNING_REPORT.json` | Accepted request, staple/Gatekeeper results and nested code hashes |

Compare downloaded assets against their entries in the external inventory. `shasum -a 256 --check SHA256SUMS` checks all listed assets, so download every listed file first or compare the hash for your chosen archive individually. Within the extracted native directory, the same command checks its complete installed resources.

All component build paths install checksum-pinned `event`, `workers` and `tcp` releases from [`native/components.json`]({{ site.github.repository_url }}/blob/main/native/components.json), retain dependency licenses, and require structured compilation `success=true, errors=[]`. An external packaging action's exit code alone is not proof of clean compilation.

## Validation boundaries

Native builds verify architecture, deployment target, runtime imports, checksums and executable mode, then exercise the extracted CLI's version, help, metadata-fixture create/list and loopback `/v1/models` with explicit and implicit serve. Component publication repeats checks after signing and after archive extraction, and compares uploaded assets before publication.

These model-free checks do **not** certify inference, streaming, audio or embeddings with downloaded weights. The declared runtime minimum is macOS 15.4; CI ran on macOS 26.6.2 and local verification on 26.7, not the minimum OS. Hosted production publication is verified; self-hosted ARM64 production execution remains unverified.

[Start with the download and quickstart]({{ '/#downloads' | relative_url }}) · [Use Swama with 4D]({{ '/guide.html' | relative_url }})
