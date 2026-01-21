![version](https://img.shields.io/badge/version-20%2B-E23089)
![platform](https://img.shields.io/static/v1?label=platform&message=mmac-arm&color=blue)
[![license](https://img.shields.io/github/license/miyako/swama)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/swama/total)

# swama
Local inference engine

**aknowledgements**: [Trans-N-ai/swama](https://github.com/Trans-N-ai/swama)

## Build Remarks

* Swama/CLI/Run.swift

`Task.detached` causes compilation error

```swift
@MainActor // add
func startAnimation() {
  animationDisplayTask = Task/*.detached*/ {
  ...
  }
}
```

### Convert Model

```
mlx_lm.convert \
	--hf-path Qwen/Qwen3-4B-Instruct-2507   \
	--mlx-path ~/Desktop/Qwen3-4B-Instruct-2507-4  \
	--quantize \
	--q-bits 4 \
	--q-group-size 64
```

Remove from `config.json`

```json
{
  "mode": "affine"
}
```

Only f16 or 4bit is compatible with swama; not 8bit.
