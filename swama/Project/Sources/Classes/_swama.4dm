Class extends _CLI

Class constructor($controller : 4D:C1709.Class)
	
	If (Not:C34(OB Instance of:C1731($controller; cs:C1710._swama_Controller)))
		$controller:=cs:C1710._swama_Controller
	End if 
	
	Super:C1705("swama"; $controller)
	
Function get worker() : 4D:C1709.SystemWorker
	
	return This:C1470.controller.worker
	
Function terminate()
	
	This:C1470.controller.terminate()
	
Function start($option : Object) : 4D:C1709.SystemWorker
	
	If (Is Windows:C1573) || (Get system info:C1571.macRosetta)
		return 
	End if 
	
	var $command : Text
	$command:=This:C1470.escape(This:C1470.executablePath)
	
	If (Value type:C1509($option.port)=Is real:K8:4) && ($option.port>0)
		$command+=(" --port "+String:C10($option.port)+" ")
	End if 
	
	If (Value type:C1509($option.host)=Is text:K8:3) && ($option.host#"")
		$command+=(" --host "+This:C1470.escape($option.host)+" ")
	End if 
	
	return This:C1470.controller.execute($command; Null:C1517; $option.data).worker