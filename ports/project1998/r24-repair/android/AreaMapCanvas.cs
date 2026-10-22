using Godot;
using P1998.Embedded;

// Draws only while the map panel is visible. Panning/zooming never ticks the world,
// reads saves, or walks the terrain cache of other visited maps.
public partial class AreaMapCanvas : Control
{
    public ArtCatalog Art {get;set;}=null!;
    public ModelTerrainSnapshot Terrain {get;set;}=null!;
    public AreaGuide.Place[] Places {get;set;}=Array.Empty<AreaGuide.Place>();
    public Vector2 Player {get;set;}=new(-1,-1);
    public int Width {get;set;}
    public int Height {get;set;}
    public event Action<int,int>? TileSelected;
    private Vector2 _center,_pressedAt;private bool _pressed,_dragged,_overview;
    private float _zoom=.7f;private ImageTexture? _overviewTexture;
    public void FocusTile(int x,int y){_center=new(x+.5f,y+.5f);_overview=false;QueueRedraw();}
    public void Overview(){_overview=true;QueueRedraw();}
    public void Zoom(float factor){_overview=false;_zoom=Math.Clamp(_zoom*factor,.3f,2f);QueueRedraw();}
    private Rect2 OverviewRect()
    {float unit=Math.Min((Size.X-16)/Math.Max(1,Width),(Size.Y-16)/Math.Max(1,Height));var size=new Vector2(Width,Height)*unit;return new((Size-size)/2,size);}
    public override void _Ready(){ClipContents=true;MouseFilter=MouseFilterEnum.Stop;TextureFilter=TextureFilterEnum.Nearest;Resized+=QueueRedraw;}
    public override void _GuiInput(InputEvent input)
    {
        if(input is InputEventMouseButton {ButtonIndex:MouseButton.Left} click)
        {
            if(click.Pressed){_pressed=true;_dragged=false;_pressedAt=click.Position;}
            else if(_pressed)
            {
                _pressed=false;
                if(!_dragged && new Rect2(Vector2.Zero,Size).HasPoint(click.Position))
                {
                    Vector2 tile=_overview?(click.Position-OverviewRect().Position)/OverviewRect().Size*new Vector2(Width,Height)
                        :(click.Position-Size/2)/(_zoom*24)+_center;
                    int x=(int)Math.Floor(tile.X),y=(int)Math.Floor(tile.Y);
                    if(x>=0&&y>=0&&x<Width&&y<Height){TileSelected?.Invoke(x,y);if(_overview)FocusTile(x,y);}
                }
            }
            AcceptEvent();
        }
        else if(input is InputEventMouseMotion motion && _pressed)
        {
            if(motion.Position.DistanceTo(_pressedAt)>4)_dragged=true;
            if(_dragged&&!_overview){_center-=motion.Relative/(_zoom*24);_center=_center.Clamp(Vector2.Zero,new(Width,Height));QueueRedraw();}AcceptEvent();
        }
        else if(input is InputEventMouseButton {Pressed:true} wheel && wheel.ButtonIndex is MouseButton.WheelUp or MouseButton.WheelDown)
        {Zoom(wheel.ButtonIndex==MouseButton.WheelUp?1.25f:.8f);AcceptEvent();}
    }
    public override void _Draw()
    {
        DrawRect(new(Vector2.Zero,Size),new Color("151c1b"));if(Terrain is null)return;
        Vector2 Point(float x,float y)=>_overview?OverviewRect().Position+new Vector2((x+.5f)/Width,(y+.5f)/Height)*OverviewRect().Size
            :Size/2+(new Vector2(x+.5f,y+.5f)-_center)*(_zoom*24);
        if(_overview)
        {
            if(_overviewTexture is null)
            {
                var image=Image.CreateEmpty(Width,Height,false,Image.Format.Rgba8);
                foreach(var c in Terrain)image.SetPixel(c.X,c.Y,new Color((c.Ground>>14)!=0?"394441":c.Object!=0?"82704e":"c7b889"));
                _overviewTexture=ImageTexture.CreateFromImage(image);
            }
            DrawTextureRect(_overviewTexture,OverviewRect(),false);
        }
        else
        {
            Vector2 top=_center-Size/(_zoom*48);Vector2 bottom=_center+Size/(_zoom*48);
            var visible=Terrain.Where(c=>c.X>=top.X-8&&c.X<=bottom.X+8&&c.Y>=top.Y-10&&c.Y<=bottom.Y+8).ToArray();
            DrawSetTransform(Size/2-_center*(_zoom*24),0,new(_zoom,_zoom));
            foreach(var c in visible)if(Art.GroundFrame(c.Ground) is {} frame)Art.DrawTerrainFrame(this,frame,new(c.X*24,c.Y*24));
            foreach(var c in visible)foreach(var frame in Art.ObjectFrames(c.Object))Art.DrawTerrainFrame(this,frame,new(c.X*24,c.Y*24));
            DrawSetTransform(Vector2.Zero);
        }
        var font=GetThemeDefaultFont();
        for(int i=0;i<Places.Length;i++)
        {
            var p=Places[i];Vector2 point=Point(p.X,p.Y);if(!new Rect2(Vector2.Zero,Size).HasPoint(point))continue;
            DrawCircle(point,5,p.Kind=="NPC"?new Color("76e4a1"):new Color("7bcfff"));
            DrawString(font,point+new Vector2(5,-4),(i+1).ToString(),HorizontalAlignment.Left,-1,12,Colors.White);
        }
        if(Player.X>=0)
        {Vector2 point=Point(Player.X,Player.Y);DrawCircle(point,7,new Color("ffe47c"));DrawArc(point,10,0,Mathf.Tau,24,Colors.Black,2);DrawString(font,point+new Vector2(10,4),"나",HorizontalAlignment.Left,-1,16,new Color("ffe47c"));}
        DrawRect(new(Vector2.Zero,Size),new Color("b7a276"),false,1);
    }
}
