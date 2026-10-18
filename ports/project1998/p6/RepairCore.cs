using Godot;

public partial class GameCore : RefCounted
{
    public string NpcPlacementAudit() => System.Text.Json.JsonSerializer.Serialize(_world.P6PlacementAudit);
    public string DropItem(int slot,bool all)
    {
        if(_playing && _session.P4Dialog is null){_session.P6Drop(slot,all);Save();}
        return ReadState();
    }
    public string SkipTutorial()
    {
        if (_playing && _session.P6SkipTutorial()) Save();
        return ReadState();
    }
}
