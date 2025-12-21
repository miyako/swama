---
layout: default
---

![version](https://img.shields.io/badge/version-20%2B-E23089)
![platform](https://img.shields.io/static/v1?label=platform&message=mac-intel%20|%20mac-arm&color=blue)
[![license](https://img.shields.io/github/license/miyako/swama)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/swama/total)

# Use Swama from 4D

#### Abstract

[Swama](https://github.com/Trans-N-ai/swama) is high-performance MLX-based LLM inference engine designed specifically for macOS.

#### Usage

Instantiate `cs.swama.swama` in your *On Startup* database method:

```4d
var $swama : cs.swama.swama

If (False)
    $swama:=cs.swama.swama.new()  //default
Else 
    var $port : Integer
    
    var $event : cs.event.event
    $event:=cs.event.event.new()
    /*
        Function onError($params : Object; $error : cs.event.error)
        Function onSuccess($params : Object; $models : cs.event.models)
        Function onTerminate($worker : 4D.SystemWorker; $params : Object)
    */
    
    $event.onError:=Formula(ALERT($2.message))
    $event.onSuccess:=Formula(ALERT($2.models.extract("name").join(",")+" loaded!"))
    $event.onTerminate:=Formula(LOG EVENT(Into 4D debug message; (["process"; $1.pid; "terminated!"].join(" "))))
    
    $port:=8080
    $models:=["mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"; "gemma3"]
    
    $swama:=cs.swama.swama.new($port; $models; {host: "127.0.0.1"}; $event)
    
End if 
```

Now you can test the server:

```
curl -X POST http://localhost:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": ["Hello world", "Text embeddings"],
    "model": "mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"
  }'
```  

```
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma3",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "max_tokens": 100,
    "stream": true
  }'
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
var $swama : cs.swama.swama
$swama:=cs.swama.swama.new()
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
