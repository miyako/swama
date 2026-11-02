//%attributes = {"invisible":true}
var $arguments : Text
var $parameter : Integer
$parameter:=Get database parameter(User param value; $arguments)

var $params; $options; $status : Object
$params:=JSON Parse($arguments)
$options:={generateSymbols: False; generateSyntaxFile: False; components: []}
$options.targets:=["arm64_macOS_lib"; "x86_64_generic"]

var $path : Text
For each ($path; $params.components)
	$options.components.push(File($path; fk posix path))
End for each

$status:=Compile project(File($params.project; fk posix path); $options)
File($params.report; fk posix path).setText(JSON Stringify($status))
QUIT 4D
