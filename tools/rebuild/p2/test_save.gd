extends SceneTree
## Full headless runner adds real process termination to the reusable platform suite.
const Suite = preload("res://storage/save_self_test.gd")
const Store = preload("res://storage/save_store.gd")
var store = Store.new()

func subprocess(arguments: Array) -> Dictionary:
	var output: Array = []
	var args: PackedStringArray = ["--headless", "--path", ProjectSettings.globalize_path("res://"), "--script", get_script().resource_path, "--"]
	for argument in arguments:
		args.append(str(argument))
	var exit_code: int = OS.execute(OS.get_executable_path(), args, output, true)
	return {"exit_code": exit_code, "output": "".join(output)}

func kill_at_phase(phase: String, expected_phase: String) -> void:
	if phase == expected_phase:
		print("P2_SAVE_CRASH_BOUNDARY=" + phase)
		OS.kill(OS.get_process_id())

func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var suite = Suite.new()
	if args.size() >= 3 and args[0] == "--child-read":
		var result = store.read_state(args[1], Suite.OWNER, suite.catalog())
		var good: bool = result.status in ["OK", "RECOVERED_BACKUP"] and int(result.get("state", {}).get("meta", {}).get("revision", -1)) == int(args[2])
		print("P2_SAVE_CHILD_READ=" + JSON.stringify({"status": result.status, "expected_revision": int(args[2]), "match": good}))
		quit(0 if good else 51)
		return
	if args.size() >= 3 and args[0] == "--child-crash":
		store.phase_observer = kill_at_phase.bind(args[2])
		var result = store.write_state(args[1], suite.fixture(2), Suite.OWNER, suite.catalog())
		print("P2_SAVE_CHILD_MISSED_CRASH=" + JSON.stringify(result))
		quit(52)
		return
	var output_directory: String = "/workspace/p2-private/save-tests"
	if args.size() >= 2 and args[0] == "--root":
		output_directory = args[1]
	var summary: Dictionary = suite.run(output_directory) if args.has("--local-only") else suite.run(output_directory, subprocess)
	quit(int(summary.failures) if summary.failures > 0 else 0)
