property options : Object

Class constructor($port : Integer; $models : Collection; $options : Object; $event : cs:C1710.event.event)
	
	This:C1470.options:=$options#Null:C1517 ? $options : {}
	This:C1470.options.models:=$models
	
	var $swama : cs:C1710.workers.worker
	$swama:=cs:C1710.workers.worker.new(cs:C1710._server)
	
	If (Not:C34($swama.isRunning($port)))
		
		If ($model="")
			$model:="llama3.2"
		End if 
		
		If ($port=0) || ($port<0) || ($port>65535)
			$port:=8080
		End if 
		
		This:C1470.options.port:=$port
		
		This:C1470.main($port; $models; $options; $event)
		
	End if 
	
Function onTCP($status : Object; $options : Object)
	
	If ($status.success)
		
		var $className : Text
		$className:=Split string:C1554(Current method name:C684; "."; sk trim spaces:K86:2).first()
		
		CALL WORKER:C1389($className; Formula:C1597(start); $options)
		
	Else 
		
		var $statuses : Text
		$statuses:="TCP port "+String:C10($status.port)+" is aready used by process "+$status.PID.join(",")
		var $error : cs:C1710.event.error
		$error:=cs:C1710.event.error.new(1; $statuses)
		
		If ($options.event#Null:C1517) && (OB Instance of:C1731($options.event; cs:C1710.event.event))
			$options.event.onError.call(This:C1470; $options; $error)
		End if 
		
	End if 
	
Function main($port : Integer; $models : Collection; $options : Object; $event : cs:C1710.event.event)
	
	main({port: $port; models: $models; options: $options; event: $event}; This:C1470.onTCP)
	
Function terminate()
	
	var $swama : cs:C1710.workers.worker
	$swama:=cs:C1710.workers.worker.new(cs:C1710._server)
	$swama.terminate()