extends RefCounted
## Private KR2001 profile consumer for P2 inspection; no game mutations.
const PROFILE := "KR_GUIDE_2001_WORKING_PROVISIONAL"
const SOURCE_PROFILE := "KR_GUIDE_2001_SNAPSHOT"
const JOBS := ["전사", "도적", "주술사", "도사"]
var data: Dictionary = {}
var skills: Dictionary = {}
var npcs: Dictionary = {}
var errors: Array[String] = []
var consumed: Dictionary = {}

func open_rules(path: String) -> bool:
	data.clear()
	skills.clear()
	npcs.clear()
	errors.clear()
	consumed.clear()
	if not FileAccess.file_exists(path):
		errors.append("RULE_FILE_MISSING")
		return false
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		errors.append("RULE_JSON_INVALID")
		return false
	if parsed.get("schema", "") != "baram.work.priority_rules/1" or parsed.get("profile", "") != PROFILE or parsed.get("source_profile", "") != SOURCE_PROFILE:
		errors.append("RULE_SCHEMA_OR_PROFILE_MISMATCH")
		return false
	if parsed.get("p3_transactions_enabled", true):
		errors.append("P3_TRANSACTIONS_FORBIDDEN")
		return false
	for unit in ["skills", "npcs", "facilities", "crafting_facts", "growth_and_transport"]:
		if typeof(parsed.get(unit)) != TYPE_ARRAY or parsed[unit].is_empty():
			errors.append("RULE_UNIT_MISSING:"+unit)
			continue
		for entry: Dictionary in parsed[unit]:
			if entry.get("source_profile", "") != SOURCE_PROFILE or entry.get("id", "").is_empty() or typeof(entry.get("value")) != TYPE_DICTIONARY:
				errors.append("RULE_ENTRY_INVALID:"+unit)
			elif unit == "skills":
				if skills.has(entry.id) or not entry.value.has("job") or not entry.value.has("learn_level"):
					errors.append("SKILL_ID_OR_CONDITIONS_INVALID:"+entry.id)
				else:
					skills[entry.id] = entry
			elif unit == "npcs":
				if npcs.has(entry.id) or entry.get("map_placement_enabled", true):
					errors.append("NPC_DUPLICATE_OR_AUTO_PLACEMENT:"+entry.id)
				else:
					npcs[entry.id] = entry
	var policy: Dictionary = parsed.get("new_character_policy", {})
	if int(policy.get("level", -1)) != 1 or policy.get("actual_job", "") != "commoner" or not policy.has("desired_job") or policy.get("desired_job") != null or policy.get("learned_attack_skills", [-1]).size() != 0 or int(policy.get("minimum_job_change_level", 0)) != 5:
		errors.append("NEW_CHARACTER_POLICY_INVALID")
	if not errors.is_empty():
		skills.clear()
		npcs.clear()
		return false
	data = parsed
	consumed["rules_file"] = path
	return true

func skill_ids(job: String = "") -> Array:
	var result: Array = []
	for id: String in skills:
		if job.is_empty() or skills[id].value.job == job or skills[id].value.job == "COMMON_FOUR_STARTER_JOBS":
			result.append(id)
	return result

func npc_ids() -> Array:
	return npcs.keys()

func skill_record(id: String) -> Dictionary:
	if not skills.has(id): return {}
	consumed["skill:"+id] = true
	return skills[id].duplicate(true)

func learning_contract(id: String, job: String, level: int) -> Dictionary:
	if not skills.has(id):
		return {"status":"BLOCKED", "reason":"SKILL_ID_UNKNOWN", "eligible":false, "job_level_eligible":false, "transaction_enabled":false}
	var record: Dictionary = skill_record(id)
	var value: Dictionary = record.value
	var result := {"skill_id":id, "job":value.job, "learn_level":int(value.learn_level), "eligible":false, "job_level_eligible":false, "transaction_enabled":false, "learn_money":value.get("learn_money"), "ingredients":value.get("ingredients"), "profile":PROFILE}
	if job in ["평민", "commoner"]:
		result.merge({"status":"REFUSED", "reason":"JOB_CHANGE_REQUIRED"})
	elif (value.job != job and value.job != "COMMON_FOUR_STARTER_JOBS") or (value.job == "COMMON_FOUR_STARTER_JOBS" and job not in JOBS and job != "COMMON_FOUR_STARTER_JOBS"):
		result.merge({"status":"REFUSED", "reason":"WRONG_JOB"})
	elif level < int(value.learn_level):
		result.merge({"status":"REFUSED", "reason":"LEVEL_TOO_LOW"})
	else:
		# Matching job/level is real consumption, never a claim of granted skill.
		result.merge({"status":"BLOCKED", "reason":"P3_TRANSACTION_NOT_IMPLEMENTED", "resource_check":"NOT_RUN"})
		result.job_level_eligible = true
		if not value.has("learn_money") or not value.has("ingredients"):
			result.reason = "RESOURCE_REQUIREMENTS_PARTLY_UNKNOWN"
	return result

func new_character_contract() -> Dictionary:
	consumed["new_character_policy"] = true
	return data.get("new_character_policy", {}).duplicate(true)

func job_change_contract(actual_job: String, desired_job: String, level: int) -> Dictionary:
	consumed["job_change_level"] = true
	if actual_job not in ["commoner", "평민"]:
		return {"status":"REFUSED", "reason":"ALREADY_HAS_JOB", "eligible":false, "job_level_eligible":false, "transaction_enabled":false}
	if desired_job not in JOBS:
		return {"status":"REFUSED", "reason":"UNKNOWN_JOB", "eligible":false, "job_level_eligible":false, "transaction_enabled":false}
	if level < int(data.get("new_character_policy", {}).get("minimum_job_change_level", 5)):
		return {"status":"REFUSED", "reason":"LEVEL_TOO_LOW", "eligible":false, "job_level_eligible":false, "transaction_enabled":false}
	return {"status":"BLOCKED", "reason":"P3_JOB_CHANGE_NOT_IMPLEMENTED", "eligible":false, "job_level_eligible":true, "transaction_enabled":false}

func npc_contract(id: String) -> Dictionary:
	if not npcs.has(id):
		return {"status":"BLOCKED", "reason":"NPC_ID_UNKNOWN"}
	consumed["npc:"+id] = true
	var record: Dictionary = npcs[id].duplicate(true)
	var value: Dictionary = record.value
	var stock: Dictionary = record.get("resolved_stock_reference", value)
	return {"id":id, "name":record.name, "profile":PROFILE, "source_id":record.source_id,
		"status":"INSPECTION_ONLY", "services":value.get("services", []),
		"location_label":value.get("location_label_documented"),
		"sale_tokens":stock.get("sale_tokens", []), "buy_only_tokens":stock.get("buy_only_tokens", []),
		"stock_categories_or_other_listed_tokens":value.get("listed_stock_documented"),
		"stock_alias_target":record.get("resolved_stock_reference", {}).get("target_npc_id"),
		"coordinate_reference":value.get("coordinate_point"), "coordinate_placement_enabled":false,
		"dialogue":null, "buy_price":null, "sell_price":null, "transaction_enabled":false,
		"name_group_relation":value.get("name_group_relation"),
		"trade_restriction":value.get("trade_restriction_documented"),
		"remaining_unknowns":["NPC_LOOK_AND_DIALOGUE", "EXACT_TRADE_PRICES", "P3_TRANSACTION_IMPLEMENTATION"]}
