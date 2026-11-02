![4D](https://img.shields.io/badge/4D-20%2B-E23089)
![platform](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon-blue)
[![license](https://img.shields.io/github/license/miyako/swama)](LICENSE)

# Swama

Run the [Trans-N-ai/swama](https://github.com/Trans-N-ai/swama) native MLX inference server, standalone or from 4D. **Apple Silicon and macOS 15.4+ are required.** There are no Intel, Windows or Linux builds. Model weights are downloaded separately.

## Source builds and downloads

The default upstream is **2.5.1**, pinned to [`545894b3e9bda3a18453bf46fbff9e2f55f6f363`](https://github.com/Trans-N-ai/swama/commit/545894b3e9bda3a18453bf46fbff9e2f55f6f363) in [`native/upstream.json`](native/upstream.json). This was upstream `main` on 2026-11-02, newer than the `v2.5.1` release tag; the version alone does not identify this source.

- [Native CLI workflow](https://github.com/miyako/swama/actions/workflows/native-build.yml): PR/main checks and manual builds produce a `swama-native-macos-arm64` Actions artifact (30-day retention; GitHub login required). Extract the artifact ZIP, then the contained `.tar.gz`.
- [Releases](https://github.com/miyako/swama/releases): future standalone CLI releases use `native-v<version>-<sha12>` tags, `.tar.gz` packages and external SHA-256 files. They are published **only** by a manual, main-branch [Publish native CLI](https://github.com/miyako/swama/actions/workflows/native-release.yml) run with `publish_release` enabled, never marked latest and never overwrite an existing release. Older `20.x` releases are 4D components, not these native packages.
- [Publish workflow](.github/workflows/publish.yml): builds the same native package first, then installs **all** its files into `swama/Resources/bin/macOS` before either hosted or self-hosted 4D component packaging. Component versions in `package.json` are independent of upstream CLI versions. No generated binary update is committed automatically.

The self-hosted option selects an **ARM64 macOS** runner for 4D packaging; it still depends on the hosted native build. That runner must meet the CLI's macOS requirements and support the existing tool4d/signing setup.

Native CI also downloads that same artifact in a separate read-only job, compiles an **unsigned 4D component**, and smoke-tests its packaged native resources. Its `swama-component-validation-macos-arm64` artifact is retained 14 days. This check does not bump versions, sign, notarize or publish. Pages pull requests build the site but skip deployment.

Every native package contains `swama`, all SwiftPM `.bundle` resources, MLX kernels freshly compiled from the locked dependency source (`mlx.metallib`), required Swift compatibility dylibs, `Package.resolved`, upstream/dependency/runtime licenses, `BUILD_INFO.json` and a complete `SHA256SUMS` inventory. Apple's `swift-stdlib-tool` copies required Swift runtime libraries unmodified; Xcode-specific search paths are removed from the CLI before ad-hoc signing. The manifest records the requested ref, resolved commit, dependency revisions, compiler/SDK, deployment target, Metal source hashes, runtime hashes and packaging revision. SwiftPM uses `--force-resolved-versions`; lockfile drift and unbundled non-system dynamic-library imports fail the build.

**Keep the entire extracted directory together**, including the bundles, dylibs and `mlx.metallib`; copying only `swama` is not a supported installation. The CLI is ad-hoc signed and its copied Swift runtime retains its vendor signature; the distribution is **not Developer ID signed or notarized**. Managed Macs/Gatekeeper may require your organization's approval. Existing 4D component signing is separate.

For component publication, the verified native inventory is retained as `SOURCE_BUILD_SHA256SUMS`: it and `BUILD_INFO.json` describe the **pre-sign source-build input**, not final component bytes. Component signing can change executable/bundle hashes; do not use that input inventory to verify the signed component.

## Build locally

Use an Apple Silicon Mac with **Xcode 26.6 (including Metal tools and Swift 6.3.3)** and Python 3.12+. CI selects this Xcode on `macos-26`, matching the validated local compiler. Upstream declares Swift 6.2 as its package minimum, but notes a Swift 6.2.1 compiler issue; older toolchains are not validated here. Dependencies and sources require network access; builds/smoke tests do not download models.

```sh
python3 -m unittest discover -s native -p 'test_*.py'
python3 native/build.py
# Optional evaluation build: tag, branch, or full SHA from Trans-N-ai/swama
python3 native/build.py --upstream-ref main --output dist/evaluation
```

Default output: `dist/native/swama-2.5.1-545894b3e9bd-macos-arm64.tar.gz` and `.sha256`. Use a fresh `--output` directory for each run. `.native-build` keeps the source/dependency build cache. Ref overrides are resolved once to a commit and recorded in the manifest; they do not edit the checked-in pin. To adopt a newer default, update the revision/version together in `native/upstream.json` and review the resulting source build.

The build checks architecture/deployment target/runtime imports, verifies archive contents and executable mode, then runs the **extracted** CLI's `--version`, `serve --help`, local metadata-fixture `create`/`list`, and loopback `/v1/models` requests with both explicit `serve` and the implicit default subcommand used by 4D. Tests run from an unrelated temporary working directory without weights or downloads. This is a model-free startup check, not an inference or minimum-OS certification.

For local 4D development, install the complete archive (requires Python 3.12+):

```sh
python3 native/install.py dist/native/*.tar.gz swama/Resources/bin/macOS
```

This verifies and replaces the resource directory, so no old bundle is retained. The binary already tracked in the repository is legacy; merely cloning this repository does **not** rebuild it.

## Run the server

After extracting a native package:

```sh
cd swama-2.5.1-545894b3e9bd-macos-arm64
shasum -a 256 --check SHA256SUMS
./swama --version
./swama pull qwen3
./swama serve --host 127.0.0.1 --port 8080
```

Upstream defaults to **`0.0.0.0:28100`**, not localhost:8080. Bind explicitly to `127.0.0.1` for local use; do not expose an unauthenticated inference server to untrusted networks.

```sh
curl http://127.0.0.1:8080/v1/models
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3","messages":[{"role":"user","content":"Hello!"}],"max_tokens":100}'
```

`SWAMA_MODELS` changes the model directory (default `~/.swama/models`); `SWAMA_PORT` changes the default port. `serve --context-limit 16384` sets the context token limit (also `SWAMA_CONTEXT_LIMIT`). `SWAMA_REGISTRY` selects `HUGGING_FACE` or `MODEL_SCOPE`; `SWAMA_PROMPT_CACHE=0` disables prompt caching. See `./swama serve --help` and [upstream documentation at the pinned revision](https://github.com/Trans-N-ai/swama/blob/545894b3e9bda3a18453bf46fbff9e2f55f6f363/README.md) for aliases, model compatibility, diagnostics and additional APIs.

Chat completions, embeddings, vision, speech and function-tool calling are model-dependent. Responses API support is partial, not complete OpenAI parity. The old blanket claims that only f16/4-bit models work, tool calling is unsupported, or `config.json` must be edited do not apply to this update.

## 4D integration

See the [GitHub Pages guide](https://miyako.github.io/swama/) for the existing 4D 20+ component API, server examples and AI Kit configuration. Use the complete source-built resource directory or a newly built component, not a standalone executable copied over the legacy binary.

Upstream and this integration use MIT licensing; dependency terms accompany the native package.
