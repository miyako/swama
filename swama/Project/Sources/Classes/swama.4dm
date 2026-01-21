Class extends _interface

Class constructor($port : Integer; $huggingfaces : cs:C1710.event.huggingfaces; $HOME : 4D:C1709.Folder; $options : Object; $event : cs:C1710.event.event)
	
	Super:C1705()
	
	var $swama : cs:C1710.workers.worker
	$swama:=cs:C1710.workers.worker.new(cs:C1710._server)
	
	If (Not:C34($swama.isRunning($port)))
		
		If (Not:C34(OB Instance of:C1731($HOME; 4D:C1709.Folder))) || (Not:C34($HOME.exists))
			$HOME:=Folder:C1567(fk home folder:K87:24).folder(".MLX")
		End if 
		
		If ($huggingfaces=Null:C1517) || (Not:C34(OB Instance of:C1731($huggingfaces; cs:C1710.event.huggingfaces))) || ($huggingfaces.huggingfaces.length=0)
			$folder:=$HOME.folder("Qwen3-4B-Thinking-2507")
			$path:="keisuke-miyako/Qwen3-4B-Thinking-2507-mlx-4bit"
			$URL:="keisuke-miyako/Qwen3-4B-Thinking-2507-mlx-4bit"
			$chat:=cs:C1710.event.huggingface.new($folder; $URL; $path)
			$huggingfaces:=cs:C1710.event.huggingfaces.new([$chat])
			$options:={host: "127.0.0.1"}
		End if 
		
		If ($port=0) || ($port<0) || ($port>65535)
			$port:=8080
		End if 
		
		This:C1470._main($port; $huggingfaces; $HOME; $options; $event)
		
	End if 
	
Function _main($port : Integer; $huggingfaces : cs:C1710.event.huggingfaces; $HOME : 4D:C1709.Folder; $options : Object; $event : cs:C1710.event.event)
	
	main({name: Split string:C1554(Current method name:C684; "."; sk trim spaces:K86:2).first(); port: $port; huggingfaces: $huggingfaces; HOME: $HOME; options: $options; event: $event}; This:C1470._onTCP)