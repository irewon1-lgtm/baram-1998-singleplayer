extends "res://../../tools/rebuild/v2/test_progression.gd"
## Same earned four-job journey on G2. Navigation uses production masks/A*;
## no map/character/rule edits or grants. Simulation time is accelerated.
const Navigation=preload("res://input/grid_navigation.gd")
func path_to(map_id: String,target: Vector2i,near: int=0,_allow_exit: bool=false) -> Array:
	if str(char_state().map_id)!=map_id:return []
	return Navigation.route(game,target,near)
