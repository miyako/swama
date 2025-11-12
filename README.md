![version](https://img.shields.io/badge/version-20%2B-E23089)
![platform](https://img.shields.io/static/v1?label=platform&message=mmac-arm&color=blue)
![downloads](https://img.shields.io/github/downloads/miyako/swama/total)

# swama
Local inference engine [`swama`](https://github.com/Trans-N-ai/swama)

## build

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
