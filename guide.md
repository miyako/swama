---
layout: default
title: Use with 4D
description: Install Swama for 4D, manage a local model and connect AI Kit to its HTTP server.
guide: true
---

# Bring Swama into your 4D application

The component manages model downloads, registration and a background Swama process. Its default port is **8080**, independently of the standalone upstream default. Use either the component or a foreground CLI server to manage a given port, not both.

## Installation

1. Download the [signed component {{ site.component_version }}]({{ site.github.repository_url }}/releases/tag/{{ site.component_version }}) and copy the complete `swama.4dbase` folder into your host project's `Components` folder.
2. Install its declared `event`, `workers` and `tcp` dependencies in the host project. The versions used to compile this release are [event 20.0.19](https://github.com/miyako/event/releases/tag/20.0.19), [workers 20.0.19](https://github.com/miyako/workers/releases/tag/20.0.19) and [tcp 20.0.10](https://github.com/miyako/tcp/releases/tag/20.0.10). The [dependency manifest]({{ site.github.repository_url }}/blob/main/native/components.json) records their checksums and source revisions.
3. Use 4D 20+ on Apple Silicon with macOS 15.4 or newer. Preserve all of `Resources/bin/macOS`; there is no Intel or Windows native executable in this distribution.

The published component was compiled with tool4d 20.7. Direct CLI use needs neither 4D nor those component dependencies.

## Usage

Instantiate `cs.swama.swama` in your **On Startup** database method. The simplest form uses the component's default model and loopback binding:

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

<aside class="callout"><strong>Registration is not readiness.</strong><p>The current component's success callback does not guarantee HTTP readiness or successful inference. Check errors and wait for <code>/v1/models</code> before sending a request. Re-registering an existing model directory can fail; inspect registration output rather than treating an existing folder as a new successful download.</p></aside>

The `event` argument is optional; without it, startup still proceeds but no callbacks are delivered. Each instance requests at most one launch and delivers `onSuccess` at most once. The server's stdout and stderr are deliberately not forwarded to `event.onStdOut`/`onStdErr`, because a long-running server can produce large amounts of output; only `onTerminate` is bound.

If no Hugging Face entry resolves to a file to download (for example a mistyped repository, or a file name that is not in the repository) and the repository is reachable, the component starts only when `options.model` is an existing local model `4D.Folder` (or `4D.File`). Otherwise it calls `onError` with code `2`, naming the path if one was given, and does not launch. When Hugging Face is unreachable, the configured local folder is used as before.

In a terminal, confirm the listener is available:

```sh
curl --fail http://127.0.0.1:8080/v1/models
```

Use the registered identifier returned by that endpoint in requests. The custom model above is **not** the standalone CLI's `qwen3` alias.

## AI Kit

Point AI Kit at the same port:

```4d
var $AIClient : cs.AIKit.OpenAI
$AIClient:=cs.AIKit.OpenAI.new()
$AIClient.baseURL:="http://127.0.0.1:8080/v1"
```

Use a discovered model identifier with AI Kit's chat APIs. Vision and tool-call responses depend on the selected model; your client is responsible for executing any tool calls. See the [endpoint support table]({{ '/#api' | relative_url }}) before relying on OpenAI-specific features.

## Embeddings

A chat model is not an embedding model. With the CLI, download a compatible embedding model separately:

```sh
./swama pull mlx-community/Qwen3-Embedding-0.6B-8bit
```

Run this in the complete native distribution directory, using the same `SWAMA_MODELS` directory as your CLI server. A component-managed server may use a different model directory: register the model through that component's download configuration instead of assuming a CLI pull makes it visible there.

After `/v1/models` lists the identifier, send an embedding request:

```sh
curl --fail http://127.0.0.1:8080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"mlx-community/Qwen3-Embedding-0.6B-8bit","input":["Hello world","Text embeddings"]}'
```

## Shutdown

Stop the server managed by the component using the instance for its port:

```4d
$swama.terminate()
```

For the default port, the component's documented pattern can reacquire its interface:

```4d
var $swama : cs.swama.swama
$swama:=cs.swama.swama.new()
$swama.terminate()
```

Only use that default-port pattern when the default server is already running; constructing an instance otherwise initiates startup. Keep the original instance when using a custom port.

## Configuration

<div class="table-wrap" markdown="1">

| Setting | Meaning |
|---|---|
| `SWAMA_MODELS` | CLI model directory; default `~/.swama/models` |
| `SWAMA_PORT` | Standalone default port; explicit `--port` takes precedence |
| `--context-limit` / `SWAMA_CONTEXT_LIMIT` | Context length |
| `SWAMA_REGISTRY` | `HUGGING_FACE` or `MODEL_SCOPE` |
| `SWAMA_PROMPT_CACHE=0` | Disable prompt caching |

</div>

These are upstream CLI settings. The 4D constructor also configures its own home folder, downloaded model and worker options; do not assume those paths equal the CLI defaults. Use explicit `host: "127.0.0.1"` in the component options or `--host 127.0.0.1` with the CLI. Real-number component options are passed to the CLI with a `.` decimal separator regardless of the system locale.

For all current server options, run `./swama serve --help` or read the [upstream README at the pinned revision](https://github.com/Trans-N-ai/swama/blob/545894b3e9bda3a18453bf46fbff9e2f55f6f363/README.md).

[Back to the standalone quickstart]({{ '/#quickstart' | relative_url }}) · [Native builds and provenance]({{ '/build.html' | relative_url }})
