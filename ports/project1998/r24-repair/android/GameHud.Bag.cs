using Godot;

public partial class GameHud
{
    private bool _bagTouchSwipe, _bagMouseSwipe, _bagMouseDragged;
    private Vector2 _bagMouseOrigin;
    private bool OnBag(Vector2 point) => _nativePanel == "inventory" && CanUseNativeRows
        && _nativeRows.GetGlobalRect().HasPoint(point);
    private void FinishBagSwipe(Vector2 from,Vector2 to)
    {
        Vector2 delta=(to-from)/NativeOverlay.GetGlobalTransformWithCanvas().Scale;
        if (Mathf.Abs(delta.X)<36 || Mathf.Abs(delta.X)<Mathf.Abs(delta.Y)*1.4f) return;
        ChangeNativePage(delta.X<0?1:-1);
    }
    private void ChangeNativePage(int step)
    {
        if (!CanUseNativeRows || _scene is null) return;
        int count=_nativePanel=="spells"?_scene.Spells.Length:_scene.Inventory.Length;
        int page=Math.Clamp(_nativePage+step,0,_nativePanel=="equipment"?2:Math.Max(0,(count-1)/10));
        ClearItemInspection();ResetItemTap();
        if(page==_nativePage)return;
        _nativePage=page;_nativeRowsVersion="";UpdateNativePanel();NativeOverlay.QueueRedraw();
    }
    private bool HandleBagMouseSwipe(InputEvent input)
    {
        if(input is InputEventMouseButton {Device:>=0,ButtonIndex:MouseButton.Left} click)
        {
            if(click.Pressed){_bagMouseSwipe=OnBag(click.Position);_bagMouseOrigin=click.Position;_bagMouseDragged=false;}
            else if(_bagMouseSwipe)
            {
                _bagMouseSwipe=false;
                if(_bagMouseDragged)
                {
                    TouchGuiMouse(new(-10000,-10000),false);ResetItemTap();
                    FinishBagSwipe(_bagMouseOrigin,click.Position);GetViewport().SetInputAsHandled();return true;
                }
            }
        }
        else if(input is InputEventMouseMotion {Device:>=0} motion && _bagMouseSwipe)
            _bagMouseDragged|=motion.Position.DistanceTo(_bagMouseOrigin)>4;
        return false;
    }
    private static string BagItemName(P1998.Embedded.SceneItemSnapshot item)
        => KoreanText.Display(item.Details is {CustomName.Length:>0} info?info.CustomName:item.BaseName);
}
