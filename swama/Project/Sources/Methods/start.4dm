//%attributes = {"invisible":true,"preemptive":"capable"}
#DECLARE($options : Object)

//install here

var $swama : cs:C1710._server
$swama:=cs:C1710._server.new(cs:C1710._Normal_Controller)
$lines:=$swama.install($options.models.map(Formula:C1597($1.result:={model: $1.value})))

cs:C1710.workers.worker.new(cs:C1710._server).start($options.options.port; $options.options)

var $_models : Collection
$_models:=[]

var $model : cs:C1710.event.model
var $name : Text
For each ($name; $swama.list())
	$model:=cs:C1710.event.model.new($name; True:C214)
	$_models.push($model)
End for each 

var $models : cs:C1710.event.models
$models:=cs:C1710.event.models.new($_models)

If ($options.event#Null:C1517) && (OB Instance of:C1731($options.event; cs:C1710.event.event))
	$options.event.onSuccess.call(Null:C1517; $options.options; $models)
End if 