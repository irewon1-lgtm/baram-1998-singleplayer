namespace Server;

public sealed partial class Session
{
    private sealed class NpcReturnException : Exception { }
    private sealed class NpcNavigation
    {
        public bool SafePrelude = true, SawMenu, RootMenu, RootCanceled;
        public void BeginRound() { SafePrelude = true; SawMenu = RootMenu = RootCanceled = false; }
    }
    private NpcNavigation? _npcNavigation;
    // Lua prefixes are inspected, never replayed. A restart may only reach a root
    // navigation menu through original read-only queries and presentation. Any
    // mutation before that menu disables restarting that script.
    internal void ObserveNpcScriptOperation(string op)
    {
        if (_npcNavigation is not { SawMenu: false } nav) return;
        if (op is "say" or "sayItem" or "sayLook" or "menu" or "bubble" or "notify"
            or "hasItem" or "countItem" or "itemName" or "hasSpell" or "stage" or "reg"
            or "hasLegend" or "level" or "maxHp" or "maxMp" or "sex" or "nation"
            or "map" or "coins" or "classId" or "basePathId" or "npcName" or "eraHas"
            or "killCount" or "totalKills" or "mounted" or "gameDate" or "now"
            or "karma" or "karmaLevel" or "karmaCheck" or "canLearnDogSpells") return;
        nav.SafePrelude = false;
    }
    private bool ObserveNpcMenu(IReadOnlyList<string> options)
    {
        if (_npcNavigation is not { SawMenu: false } nav) return false;
        nav.SawMenu = true;
        // Yes/No confirmations and quizzes are not navigation roots.
        nav.RootMenu = nav.SafePrelude && (options.Count > 2 || options.Any(o =>
            o is "Buy" or "Sell" or "Deposit" or "Withdraw" or "Learn" or "Craft"));
        return nav.RootMenu;
    }
}
