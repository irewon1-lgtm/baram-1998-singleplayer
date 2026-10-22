using Godot;

public partial class GameHud
{
    // Touch adaptation uses the original parchment palette and clear, stable cells.
    private static void ScrollChrome(Button button)
    {
        foreach(string state in new[]{"normal","hover","pressed","disabled"})
        {
            var style=new StyleBoxFlat {BgColor=new Color(state=="pressed"?"bea06c":state=="hover"?"e7d3a8":"d6bd8e"),
                BorderColor=new Color("785632"),BorderWidthLeft=1,BorderWidthRight=1,BorderWidthTop=1,BorderWidthBottom=1,
                ContentMarginLeft=2,ContentMarginRight=2,ContentMarginTop=1,ContentMarginBottom=1};
            button.AddThemeStyleboxOverride(state,style);
        }
        foreach(string state in new[]{"font_color","font_hover_color","font_pressed_color","font_focus_color","font_disabled_color"})
            button.AddThemeColorOverride(state,new Color("322315"));
        button.AddThemeColorOverride("font_shadow_color",Colors.Transparent);
        button.AddThemeConstantOverride("outline_size",0);
    }
}
