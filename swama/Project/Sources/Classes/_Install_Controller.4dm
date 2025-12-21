property stdOut : Text
property stdErr : Text
property count : Integer
property total : Integer
property fileName : Text

Class extends _Normal_Controller

Class constructor($CLI : cs:C1710._CLI)
	
	Super:C1705($CLI)
	
	This:C1470.clear()
	
Function onData($worker : 4D:C1709.SystemWorker; $params : Object)
	
	Super:C1706.onData($worker; $params)
	
	var $stdOut : Text
	$stdOut:=This:C1470.stdOut
	
	ARRAY LONGINT:C221($pos; 0)
	ARRAY LONGINT:C221($len; 0)
	
	If (Match regex:C1019("\\[(\\d+)\\/(\\d+)\\] Downloading: (.+)"; $stdOut; 1; $pos; $len))
		This:C1470.count:=Num:C11(Substring:C12($stdOut; $pos{1}; $len{1}))
		This:C1470.total:=Num:C11(Substring:C12($stdOut; $pos{2}; $len{2}))
		This:C1470.fileName:=Substring:C12($stdOut; $pos{3}; $len{3})
	End if 
	
	$i:=1
	While (Match regex:C1019("\\[[= >]*\\]\\s+(\\d+)"; $stdOut; $i; $pos; $len))
		$percentage:=Num:C11(Substring:C12($stdOut; $pos{1}; $len{1}))
		$i:=$pos{0}+$len{0}
		var $instance : cs:C1710._server
		$instance:=This:C1470.instance
		If ($instance.onData#Null:C1517) && (OB Instance of:C1731($instance.onData; 4D:C1709.Function))
			$context:={}
			$context.count:=This:C1470.count
			$context.total:=This:C1470.total
			$context.fileName:=This:C1470.fileName
			$context.percentage:=$percentage
			$instance.onData.call(This:C1470; $worker; $context)
		End if 
	End while 
	
	This:C1470.stdOut:=Substring:C12($stdOut; $i)