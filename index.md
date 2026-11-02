---
layout: default
---

# Use Swama from 4D

[Swama](https://github.com/Trans-N-ai/swama) is a native Swift/MLX inference server for **Apple Silicon Macs running macOS 15.4+**. This repository supplies source-build automation and a 4D 20+ integration. Intel Macs, Windows and Linux are not supported by this build.

## Downloads and source identity

The default source is upstream **2.5.1** at [`545894b3e9bda3a18453bf46fbff9e2f55f6f363`](https://github.com/Trans-N-ai/swama/commit/545894b3e9bda3a18453bf46fbff9e2f55f6f363), resolved from `main` on 2026-11-02. It is newer than the identically versioned `v2.5.1` tag.

Use the [Native CLI workflow artifacts](https://github.com/miyako/swama/actions/workflows/native-build.yml) for source-built CLI packages (GitHub login required; retained 30 days), or look for `native-v<version>-<sha12>` packages on the [Releases page](https://github.com/miyako/swama/releases). The [Publish native CLI workflow](https://github.com/miyako/swama/actions/workflows/native-release.yml) publishes only with an explicit main-branch request and never changes the latest component release. The `20.x` releases are **4D components**, not standalone CLI archives. No native release is created merely by this documentation update.

Extract the artifact ZIP, then the `.tar.gz`. Keep `swama`, **all adjacent `.bundle` directories, Swift compatibility dylibs and `mlx.metallib` together**. Models are not included. Packages include upstream/dependency/runtime licenses, `Package.resolved`, build/source provenance in `BUILD_INFO.json`, and `SHA256SUMS`; an external `.sha256` verifies the archive itself. Xcode-specific runtime search paths are removed, so the installed CLI does not require Xcode.

These CLI packages are ad-hoc signed, **not Developer ID signed or notarized**. Gatekeeper or managed-device policies may require approval. The existing component signing workflow is separate. The legacy binary in the Git source checkout is not automatically refreshed; build/install the complete package before local 4D use.

In component releases, `BUILD_INFO.json` and `SOURCE_BUILD_SHA256SUMS` identify the verified **pre-sign native input**. They are not an inventory of final signed component bytes, since signing may alter executables and bundles.

Production component releases require timestamped Developer ID/hardened-runtime signatures for all nested code, explicit **Accepted** Apple notarization, a validated stapled DMG ticket and Gatekeeper acceptance. The mounted DMG and extracted ZIP must pass final nested-signature, checksum and CLI/server checks before publication. Use the component's post-sign `SHA256SUMS` and the release's external `SHA256SUMS` for final-byte verification; see `Resources/RELEASE_INFO.json`, `SIGNING_REPORT.json` and `NOTARIZATION.json` for provenance and evidence. The ZIP contains the same signed component; the stapled offline ticket is on the DMG. Existing releases/tags are never overwritten.

Both component Publish paths now wait for a source build, verify the archive, and install the entire distribution before packaging. The [repository README](https://github.com/miyako/swama#build-locally) documents local builds using Xcode 26.6/Swift 6.3.3 (including Metal tools) and Python 3.12+, pinned defaults and optional upstream ref overrides.

## Standalone server

From the extracted package directory:

```sh
shasum -a 256 --check SHA256SUMS
./swama --version
./swama pull qwen3
./swama serve --host 127.0.0.1 --port 8080
```

Upstream defaults to **`0.0.0.0:28100`**. Always set `--host 127.0.0.1` for local use, and use the same port in clients. Do not expose this unauthenticated server to untrusted networks.

```sh
curl http://127.0.0.1:8080/v1/models
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3","messages":[{"role":"user","content":"Hello!"}],"max_tokens":100,"stream":true}'
```

`SWAMA_MODELS` selects the model directory (default `~/.swama/models`); `SWAMA_PORT` sets the default port. Use `--context-limit` or `SWAMA_CONTEXT_LIMIT` for context length, `SWAMA_REGISTRY` for `HUGGING_FACE`/`MODEL_SCOPE`, and `SWAMA_PROMPT_CACHE=0` to disable prompt caching. See `./swama serve --help` and the [pinned upstream README](https://github.com/Trans-N-ai/swama/blob/545894b3e9bda3a18453bf46fbff9e2f55f6f363/README.md) for details.

## Existing 4D component API

Instantiate `cs.swama.swama` in your **On Startup** database method. This API manages its own model download/registration and defaults to port **8080**, independently of the standalone upstream default.

```4d
var $swama : cs.swama.swama
$swama:=cs.swama.swama.new()
```

For an explicit model, port, home directory and loopback binding:

```4d
var $swama : cs.swama.swama
var $homeFolder; $folder : 4D.Folder
var $port : Integer
var $path; $URL : Text
var $options : Object
var $chat : cs.event.huggingface
var $huggingfaces : cs.event.huggingfaces
var $event : cs.event.event

$port:=8080
$homeFolder:=Folder(fk home folder).folder(".MLX")
$homeFolder.create()
$folder:=$homeFolder.folder("Qwen3-4B-Thinking-2507")
$path:="keisuke-miyako/Qwen3-4B-Thinking-2507-mlx-4bit"
$URL:=$path
$chat:=cs.event.huggingface.new($folder; $URL; $path)
$huggingfaces:=cs.event.huggingfaces.new([$chat])
$options:={host: "127.0.0.1"}
$event:=cs.event.event.new()
$event.onError:=Formula(ALERT($2.message))
$event.onSuccess:=Formula(ALERT($2.models.extract("name").join(",")+" registered"))
$swama:=cs.swama.swama.new($port; $huggingfaces; $homeFolder; $options; $event)
```

Use the registered name returned by `/v1/models` in requests. The downloaded model example above is not the standalone `qwen3` alias. Registration does not mean model inference has already succeeded.

### AI Kit

```4d
var $AIClient : cs.AIKit.OpenAI
$AIClient:=cs.AIKit.OpenAI.new()
$AIClient.baseURL:="http://127.0.0.1:8080/v1"
```

Embeddings require a separately downloaded/registered embedding model, for example `./swama pull mlx-community/Qwen3-Embedding-0.6B-8bit`. A chat model is not a substitute for an embedding model:

```sh
curl http://127.0.0.1:8080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"mlx-community/Qwen3-Embedding-0.6B-8bit","input":["Hello world","Text embeddings"]}'
```

Stop the server managed by the component:

```4d
var $swama : cs.swama.swama
$swama:=cs.swama.swama.new()
$swama.terminate()
```

## API compatibility

| API | Support |
|---|---|
| `/v1/models` | Model listing |
| `/v1/chat/completions` | Chat; vision/tool calling depend on model |
| `/v1/embeddings` | Requires an embedding model |
| `/v1/responses` | Partial OpenAI compatibility; see upstream support matrix |
| `/v1/audio/transcriptions`, `/v1/audio/speech` | Require suitable audio models |
| Image generation, moderation, files | Not provided by this integration |

Tool calls are returned to clients, not executed by the server. No blanket 4-bit-only restriction or manual `config.json` edit is prescribed for current upstream. Follow the selected model's instructions and upstream compatibility documentation.
