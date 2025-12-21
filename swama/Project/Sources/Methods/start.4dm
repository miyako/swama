//%attributes = {"invisible":true,"preemptive":"capable"}
#DECLARE($options : Object)

var $swama : cs:C1710._server
$swama:=cs:C1710._server.new(cs:C1710._Install_Controller)

$lines:=$swama.install($options.event; $options.models.map(Formula:C1597($1.result:={model: $1.value})); Formula:C1597(onModel))

cs:C1710.workers.worker.new(cs:C1710._server).start($options.options.port; $options.options)