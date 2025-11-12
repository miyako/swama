![version](https://img.shields.io/badge/version-20%2B-E23089)
![platform](https://img.shields.io/static/v1?label=platform&message=mmac-arm&color=blue)
[![license](https://img.shields.io/github/license/miyako/swama)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/swama/total)

# swama
Local inference engine [`swama`](https://github.com/Trans-N-ai/swama)

## Usage

* List models

```4d
var $swama : cs.swama.swama
$swama:=cs.swama.swama.new()

var $models : Collection
$models:=$swama.list()

```

* Install model

```4d
If (Count parameters=0)
	
	CALL WORKER(1; Current method name; {})
	
Else 
	
	var $swama : cs.swama.swama
	$swama:=cs.swama.swama.new()
	
	var $models : Collection
	$swama.install({model: "gemma3"}; Formula(onInstall))
	
End if 
```

* Uninstall model

```4d
If (Count parameters=0)
	
	CALL WORKER(1; Current method name; {})
	
Else 
	
	var $swama : cs.swama.swama
	$swama:=cs.swama.swama.new()
	
	var $models : Collection
	$swama.uninstall({model: "gemma3"}; Formula(onUninstall))
	
End if 
```

* Serve model

```4d
var $swama : cs.swama.server
$swama:=cs.swama.server.new()
$isRunning:=$swama.isRunning()
$swama.start({host: "127.0.0.1"; port: 8080})
```

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
