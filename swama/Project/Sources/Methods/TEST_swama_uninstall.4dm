//%attributes = {"invisible":true}
If (Count parameters:C259=0)
	
	CALL WORKER:C1389(1; Current method name:C684; {})
	
Else 
	
	var $swama : cs:C1710.swama
	$swama:=cs:C1710.swama.new()
	
	var $models : Collection
	$swama.uninstall({model: "gemma3"}; Formula:C1597(onUninstall))
	
End if 