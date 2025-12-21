var $swama : cs:C1710.swama

If (False:C215)
	$swama:=cs:C1710.swama.new()  //default
Else 
	var $port : Integer
	
	var $event : cs:C1710.event.event
	$event:=cs:C1710.event.event.new()
/*
Function onError($params : Object; $error : cs.event.error)
Function onSuccess($params : Object; $models : cs.event.models)
Function onTerminate($worker : 4D.SystemWorker; $params : Object)
*/
	
	$event.onError:=Formula:C1597(ALERT:C41($2.message))
	$event.onSuccess:=Formula:C1597(ALERT:C41($2.models.extract("name").join(",")+" loaded!"))
	$event.onTerminate:=Formula:C1597(LOG EVENT:C667(Into 4D debug message:K38:5; (["process"; $1.pid; "terminated!"].join(" "))))
	
	$port:=8080
	$models:=["mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"; "gemma3"]
	
	$swama:=cs:C1710.swama.new($port; $models; {host: "127.0.0.1"}; $event)
	
End if 