using Godot;

public partial class GameCore : RefCounted
{
    public string SkipTutorial()
    {
        if (_playing && _session.P6SkipTutorial()) Save();
        return ReadState();
    }
}
