property model : 4D:C1709.Folder
property name : Text
property _started : Boolean

Class extends _models

Class constructor($port : Integer; $huggingfaces : cs:C1710.event.huggingfaces; $options : Object; $formula : 4D:C1709.Function; $event : cs:C1710.event.event)
	
	Super:C1705($port; $huggingfaces; $options; $formula; $event)
	
	If (Not:C34(This:C1470.offline))
		This:C1470.download()
	End if 
	
Function models() : cs:C1710.event.models
	
	var $models : Collection
	$models:=[]
	
	var $_model : Text
	For each ($_model; This:C1470._models)
		$models.push(cs:C1710.event.model.new($_model; True:C214))
	End for each 
	
	return cs:C1710.event.models.new($models)
	
Function onDownload($oid : Text)
	
	var $downloaded : cs:C1710.event.huggingface
	$downloaded:=This:C1470.files.query("oid == :1"; $oid).first()
	
	If ($downloaded#Null:C1517)
		var $model : Object
		$model:=OB Instance of:C1731($downloaded.folder; 4D:C1709.Folder)\
			 ? $downloaded.folder.folder($downloaded.path).parent : $downloaded.folder
		
		This:C1470.options.model:=$model
		This:C1470.options.name:=$downloaded.name#"" ? $downloaded.name : $model.fullName
	End if 
	
	Super:C1706.onDownload($oid)
	
Function _onNothingToDownload()
	
	var $model : Object
	$model:=This:C1470.options.model
	If ((OB Instance of:C1731($model; 4D:C1709.Folder)) || (OB Instance of:C1731($model; 4D:C1709.File)))
		If ($model.exists)
			If (Value type:C1509(This:C1470.options.name)#Is text:K8:3) || (This:C1470.options.name="")
				This:C1470.options.name:=$model.fullName
			End if 
			This:C1470.start()
			return 
		End if 
	End if 
	var $message : Text
	$message:="no model to load: nothing to download and options.model is not an existing folder or file"
	If ((OB Instance of:C1731($model; 4D:C1709.Folder)) || (OB Instance of:C1731($model; 4D:C1709.File)))
		$message+=": "+$model.path
	End if 
	LOG EVENT:C667(Into 4D debug message:K38:5; "swama: "+$message)
	This:C1470._notifyError(cs:C1710.event.error.new(2; $message; cs:C1710.event.models.new()))
	
Function start()
	
	If (This:C1470._started)
		return 
	End if 
	This:C1470._started:=True:C214
	var $swama : cs:C1710.workers.worker
	$swama:=cs:C1710.workers.worker.new(cs:C1710._server)
	$swama.start(This:C1470.options.port; This:C1470.options)
	
	If (This:C1470.event#Null:C1517) && (OB Instance of:C1731(This:C1470.event; cs:C1710.event.event))
		This:C1470.event.onSuccess.call(This:C1470; This:C1470.options; This:C1470.models())
	End if 