Class extends _swama

Class constructor($controller : 4D:C1709.Class)
	
	Super:C1705($controller)
	
Function list() : Collection
	
	If (Is Windows:C1573) || (Get system info:C1571.macRosetta)
		return 
	End if 
	
	var $models : Collection
	$models:=[]
	
	var $command : Text
	$command:=This:C1470.escape(This:C1470.executablePath)
	$command+=" list "
	
	var $worker : 4D:C1709.SystemWorker
	$worker:=This:C1470.controller.execute($command).worker
	$worker.wait()
	
	var $resultText : Text
	$resultText:=This:C1470.controller.stdOut
	
	ARRAY LONGINT:C221($pos; 0)
	ARRAY LONGINT:C221($len; 0)
	
	var $i : Integer
	$i:=1
	
	While (Match regex:C1019("(?m)^(\\S+)"; $resultText; $i; $pos; $len))
		$models.push(Substring:C12($resultText; $pos{1}; $len{1}))
		$i:=$pos{0}+$len{0}
	End while 
	
	If ($models.length#0)
		$models.shift()
	End if 
	
	return $models
	
Function install($option : Variant; $formula : 4D:C1709.Function) : Collection
	
	If (Is Windows:C1573) || (Get system info:C1571.macRosetta)
		return 
	End if 
	
	var $stdOut; $isStream; $isAsync : Boolean
	var $options : Collection
	var $results : Collection
	$results:=[]
	
	Case of 
		: (Value type:C1509($option)=Is object:K8:27)
			$options:=[$option]
		: (Value type:C1509($option)=Is collection:K8:32)
			$options:=$option
		Else 
			$options:=[]
	End case 
	
	var $commands : Collection
	$commands:=[]
	
	If (OB Instance of:C1731($formula; 4D:C1709.Function))
		$isAsync:=True:C214
		This:C1470.controller.onResponse:=$formula
	End if 
	
	For each ($option; $options)
		
		If ($option=Null:C1517) || (Value type:C1509($option)#Is object:K8:27)
			continue
		End if 
		
		$stdOut:=Not:C34(OB Instance of:C1731($option.output; 4D:C1709.File))
		
		$command:=This:C1470.escape(This:C1470.executablePath)
		$command+=" pull "
		
		If (Value type:C1509($option.model)=Is text:K8:3) && ($option.model#"")
			$command+=" "
			$command+=This:C1470.escape($option.model)
		Else 
			continue  //mandatory
		End if 
		
		var $worker : 4D:C1709.SystemWorker
		$worker:=This:C1470.controller.execute($command; Null:C1517; $option.data).worker
		
		If (Not:C34($isAsync))
			$worker.wait()
		End if 
		
		If ($stdOut) && (Not:C34($isAsync))
			//%W-550.26
			//%W-550.2
			$results.push(This:C1470.controller.stdOut)
			This:C1470.controller.clear()
			//%W+550.2
			//%W+550.26
		End if 
		
	End for each 
	
	If ($stdOut) && (Not:C34($isAsync))
		return $results
	End if 
	
Function uninstall($option : Variant; $formula : 4D:C1709.Function) : Collection
	
	If (Is Windows:C1573) || (Get system info:C1571.macRosetta)
		return 
	End if 
	
	var $stdOut; $isStream; $isAsync : Boolean
	var $options : Collection
	var $results : Collection
	$results:=[]
	
	Case of 
		: (Value type:C1509($option)=Is object:K8:27)
			$options:=[$option]
		: (Value type:C1509($option)=Is collection:K8:32)
			$options:=$option
		Else 
			$options:=[]
	End case 
	
	var $commands : Collection
	$commands:=[]
	
	If (OB Instance of:C1731($formula; 4D:C1709.Function))
		$isAsync:=True:C214
		This:C1470.controller.onResponse:=$formula
	End if 
	
	For each ($option; $options)
		
		If ($option=Null:C1517) || (Value type:C1509($option)#Is object:K8:27)
			continue
		End if 
		
		$stdOut:=Not:C34(OB Instance of:C1731($option.output; 4D:C1709.File))
		
		$command:=This:C1470.escape(This:C1470.executablePath)
		$command+=" rm "
		
		If (Value type:C1509($option.model)=Is text:K8:3) && ($option.model#"")
			$command+=" "
			$command+=This:C1470.escape($option.model)
		Else 
			continue  //mandatory
		End if 
		
		var $worker : 4D:C1709.SystemWorker
		$worker:=This:C1470.controller.execute($command; Null:C1517; $option.data).worker
		
		If (Not:C34($isAsync))
			$worker.wait()
		End if 
		
		If ($stdOut) && (Not:C34($isAsync))
			//%W-550.26
			//%W-550.2
			$results.push(This:C1470.controller.stdOut)
			This:C1470.controller.clear()
			//%W+550.2
			//%W+550.26
		End if 
		
	End for each 
	
	If ($stdOut) && (Not:C34($isAsync))
		return $results
	End if 