---
layout: default
---

![version](https://img.shields.io/badge/version-20%2B-E23089)
![platform](https://img.shields.io/static/v1?label=platform&message=mac-intel%20|%20mac-arm&color=blue)
[![license](https://img.shields.io/github/license/miyako/swama)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/swama/total)

# Use Swama from 4D

#### Abstract

[Swama](https://github.com/mudler/LocalAI) is high-performance MLX-based LLM inference engine designed specifically for macOS.

#### Usage

Instantiate `cs.swama.server` and call `.start()` in your *On Startup* database method:

```4d
var $swama : cs.swama.server
$swama:=cs.swama.server.new()
$swama.start({host: "127.0.0.1"; port: 8080})
```

Instantiate `cs.swama.swama` and call `.install()` to install a model:

```4d
If (Count parameters=0)
    
    CALL WORKER(1; Current method name; {})
    
Else 
    
    var $swama : cs.swama
    $swama:=cs.swama.new()
    
    var $models : Collection
    $swama.install({model: "gemma3"}; Formula(onInstall))
    
End if 
```

Now you can test the server:

```
curl -X POST http://127.0.0.1:8080/v1/embeddings \
     -H "Content-Type: application/json" \
     -d '{"input":"The quick brown fox jumps over the lazy dog."}'
```

Or, use AI Kit:

```4d
var $AIClient : cs.AIKit.OpenAI
$AIClient:=cs.AIKit.OpenAI.new()
$AIClient.baseURL:="http://127.0.0.1:8080/v1"

var $text : Text
$text:="The quick brown fox jumps over the lazy dog."

var $responseEmbeddings : cs.AIKit.OpenAIEmbeddingsResult
$responseEmbeddings:=$AIClient.embeddings.create($text)
```

Finally to terminate the server:

```4d
var $swama : cs.swama.server
$swama:=cs.swama.server.new()
$swama.terminate()
```

#### AI Kit compatibility

The API is compatibile with [Open AI](https://platform.openai.com/docs/api-reference/embeddings). 

|Class|API|Availability|
|-|-|:-:|
|Models|`/v1/models`|✅|
|Chat|`/v1/chat/completions`|✅|
|Images|`/v1/images/generations`||
|Moderations|`/v1/moderations`||
|Embeddings|`/v1/embeddings`|✅|
|Files|`/v1/files`||
