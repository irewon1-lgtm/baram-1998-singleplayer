extends RefCounted
## Game/save directions are U,L,D,R. Original EPF sheets are U,R,D,L.
## One render mapping for all layers and input sources; no input reversal.
static func sprite(direction: int) -> int:
    return [0,3,2,1][posmod(direction,4)]

static func toward(offset: Vector2i) -> int:
    return (3 if offset.x>0 else 1) if absi(offset.x)>absi(offset.y) else (2 if offset.y>0 else 0)
