extends RefCounted
var path: String
var character_name:=""
var display_name:=""
var volume:=0.65
var error:=""
func _init(root: String) -> void:
	path=root.path_join("profile-p6.json")
	if not FileAccess.file_exists(path):return
	var parsed=JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary or int(parsed.get("schema",0))!=1:error="이름·소리 설정을 읽지 못했습니다. 기존 파일을 보존합니다.";return
	character_name=str(parsed.get("character_name",""));display_name=str(parsed.get("display_name",""));volume=clampf(float(parsed.get("volume",0.65)),0,1)
func valid_name(value: String) -> bool:
	var regex:=RegEx.new();regex.compile("^(?:[가-힣]{2,12}|[A-Za-z]{3,16})$")
	return regex.search(value)!=null
func native_name(value: String) -> String:
	var ascii_only:=true
	for c in value:
		if c.unicode_at(0)>127:ascii_only=false;break
	if ascii_only and value.length()<=11:return value
	var letters:="K"
	for c in value.sha256_text().left(9):letters+=String.chr(97+"0123456789abcdef".find(c))
	return letters
func shown(native: String) -> String:
	return display_name if native==character_name and valid_name(display_name) else native
func save(native: String,nickname: String) -> bool:
	if error!="" or not valid_name(nickname):return false
	var payload:={"schema":1,"character_name":native,"display_name":nickname,"volume":volume}
	var file:=FileAccess.open(path+".pending",FileAccess.WRITE)
	if file==null:return false
	file.store_string(JSON.stringify(payload,"\t"));file.flush();file.close()
	if DirAccess.rename_absolute(path+".pending",path)!=OK:return false
	character_name=native;display_name=nickname;return true
