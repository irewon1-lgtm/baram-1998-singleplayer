extends SceneTree
const Rules = preload("res://content/priority_rules.gd")
var checks: Array = []
var failures := 0
func check(id: String, good: bool) -> void:
	checks.append({"id":id, "result":"PASS" if good else "FAIL"})
	if not good: failures += 1
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var input := ""
	var report := ""
	for i in range(args.size()-1):
		if args[i] == "--rules": input=args[i+1]
		if args[i] == "--report": report=args[i+1]
	var rules = Rules.new()
	check("load_private_frozen_profile", rules.open_rules(input))
	if failures == 0:
		var before: String = JSON.stringify(rules.data)
		var wrong_job := true
		var lower_level := true
		var correct_level := true
		var commoner := true
		for id in rules.skill_ids():
			var row: Dictionary = rules.skill_record(id)
			var value: Dictionary = row.value
			wrong_job = wrong_job and rules.learning_contract(id,"invalid_job",99).reason == "WRONG_JOB"
			lower_level = lower_level and rules.learning_contract(id,value.job,int(value.learn_level)-1).reason == "LEVEL_TOO_LOW"
			var result: Dictionary = rules.learning_contract(id,value.job,int(value.learn_level))
			correct_level = correct_level and result.job_level_eligible and result.status == "BLOCKED" and not result.eligible and not result.transaction_enabled
			commoner = commoner and rules.learning_contract(id,"commoner",1).reason == "JOB_CHANGE_REQUIRED"
		check("188_skill_rows_actually_consumed", rules.skill_ids().size()==188)
		check("wrong_job_refused_all_specific_job_skills",wrong_job)
		check("below_level_refused_all_skills",lower_level)
		check("matching_job_level_is_blocked_transaction",correct_level)
		check("commoner_refused_all_skills",commoner)
		check("unknown_skill_blocked",rules.learning_contract("missing","전사",99).status=="BLOCKED")
		var initial: Dictionary = rules.new_character_contract()
		check("new_character_level1_commoner_empty_skills",initial.level==1 and initial.actual_job=="commoner" and initial.learned_attack_skills.is_empty() and initial.desired_job==null)
		var transition := true
		for job in ["전사","도적","주술사","도사"]:
			transition = transition and rules.job_change_contract("commoner",job,4).reason=="LEVEL_TOO_LOW" and rules.job_change_contract("commoner",job,5).job_level_eligible and rules.job_change_contract("commoner",job,5).status=="BLOCKED"
		check("four_job_transition_level4_refuse_level5_contract_only",transition)
		var signatures: Dictionary = {}
		var no_prices := true
		for id in rules.npc_ids():
			var npc: Dictionary = rules.npc_contract(id)
			signatures[JSON.stringify(npc.sale_tokens)] = true
			no_prices = no_prices and npc.buy_price==null and npc.sell_price==null and not npc.transaction_enabled and not npc.coordinate_placement_enabled
		check("22_distinct_npc_records_consumed",rules.npc_ids().size()==22)
		check("vendor_stocks_differ",signatures.size()>2)
		check("unknown_prices_and_npc_coordinates_not_activated",no_prices)
		var inn: Dictionary = rules.npc_contract("KRO-NPC_SERVICE-1e329bf1dc2165")
		var buyeo: Dictionary = rules.npc_contract("KRO-NPC_SERVICE-672ae033dde168")
		check("same_capture_stock_alias_only",inn.sale_tokens==buyeo.sale_tokens and inn.name!=buyeo.name and buyeo.stock_alias_target==inn.id)
		check("buy_only_item_not_added_to_sale_stock",inn.buy_only_tokens.has("호박") and not inn.sale_tokens.has("호박"))
		check("unknown_npc_blocked",rules.npc_contract("missing").status=="BLOCKED")
		check("read_only_no_rule_state_mutation",before==JSON.stringify(rules.data))
		var missing = Rules.new()
		check("missing_rule_file_fails_closed",not missing.open_rules(input+".absent"))
	var result := {"schema":"baram.priority_rules.godot_evidence/1", "platform":OS.get_name(),"engine":Engine.get_version_info(),"checks":checks,"failures":failures,"status":"PASS" if failures==0 else "FAIL","scope":"Actual private rule JSON loaded and read-only P2 contracts; no P3 transactions or native Windows/Android claim"}
	if not report.is_empty():
		var file := FileAccess.open(report,FileAccess.WRITE)
		if file: file.store_string(JSON.stringify(result,"  ")+"\n")
	print(JSON.stringify(result))
	quit(0 if failures==0 else 1)
