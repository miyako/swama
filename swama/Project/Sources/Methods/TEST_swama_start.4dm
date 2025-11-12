//%attributes = {"invisible":true}
var $swama : cs:C1710.server
$swama:=cs:C1710.server.new()

$isRunning:=$swama.isRunning()

$swama.start({host: "127.0.0.1"; port: 8080})