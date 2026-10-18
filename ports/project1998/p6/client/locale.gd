extends RefCounted
var data: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://p6/locale.json"))
var rules: Array=[]
var observed: Dictionary={}
var fallback: Dictionary={}
func _init() -> void:
	for rule in data.patterns:
		var regex:=RegEx.new()
		if regex.compile(rule[0])==OK:rules.append([regex,rule[1]])
func name_of(value: String) -> String:
	var clean:=value.replace("\\'","'")
	if data.names.has(clean):return str(data.names[clean])
	if clean.contains(": "):
		var colon:=clean.find(": ");var speaker:=clean.left(colon)
		if data.names.has(speaker):return name_of(speaker)+": "+text(clean.substr(colon+2))
	if clean.contains(", "):
		var parts:=PackedStringArray()
		for part in clean.split(", "):parts.append(name_of(part))
		return ", ".join(parts)
	var amount:=RegEx.new();amount.compile("^(.+) \\(([0-9]+)\\)$")
	var hit: RegExMatch=amount.search(clean)
	if hit!=null:return name_of(hit.get_string(1))+" ("+hit.get_string(2)+")"
	amount.compile("^([0-9]+) gold$");hit=amount.search(clean)
	if hit!=null:return hit.get_string(1)+"전"
	return str(data.names.get(clean,clean))
func entity(category: String,id: String,original: String) -> String:
	return str(data.entities.get(category+":"+id,name_of(original)))
func text(value: String) -> String:
	var clean:=value.replace("\\'","'")
	if clean=="":return ""
	observed[clean]=true
	if data.text.has(clean):return str(data.text[clean])
	if data.names.has(clean):return str(data.names[clean])
	for rule in rules:
		var found: RegExMatch=rule[0].search(clean)
		if found!=null:
			var answer: String=rule[1]
			for i in range(1,found.get_group_count()+1):answer=answer.replace("{"+str(i)+"}",name_of(found.get_string(i)))
			return answer
	# Sell rows carry a display suffix, while the reply remains the native slot.
	var count:=RegEx.new();count.compile("^(.+) x([0-9]+)$")
	var hit: RegExMatch=count.search(clean)
	if hit!=null:return name_of(hit.get_string(1))+" ×"+hit.get_string(2)
	if clean.contains("\n"):
		var lines:=PackedStringArray()
		for line in clean.split("\n"):lines.append(text(line))
		return "\n".join(lines)
	var latin:=RegEx.new();latin.compile("[A-Za-z]")
	var hangul:=RegEx.new();hangul.compile("[가-힣]")
	if latin.search(clean)!=null and hangul.search(clean)==null:fallback[clean]=true
	return clean
# Only explicit player-facing aliases are rewritten. Unknown Hangul is retained
# in the field and rejected before the original ASCII wire can turn it into '?'.
func command(value: String) -> String:
	var aliases: Dictionary={"완료":"Finish","끝":"Finish","마침":"Finish","동":"east","동쪽":"east","서":"west","서쪽":"west","남":"south","남쪽":"south","북":"north","북쪽":"north"}
	return str(aliases.get(value.strip_edges(),value.strip_edges()))
