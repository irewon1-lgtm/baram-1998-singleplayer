import android.os.SystemClock;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.MotionEvent;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import org.json.JSONArray;
import org.json.JSONObject;

/** CI-only shell input driver. Never packaged in the player APK. */
public final class PointerDriver {
    public static void main(String[] args) throws Exception {
        Class<?> cls = Class.forName("android.hardware.input.InputManagerGlobal");
        Object manager = cls.getMethod("getInstance").invoke(null);
        Method inject = cls.getMethod("injectInputEvent", InputEvent.class, int.class);
        BufferedReader lines = new BufferedReader(new InputStreamReader(System.in));
        long downTime = 0;
        String line;
        while ((line = lines.readLine()) != null) {
            JSONObject command = new JSONObject(line);
            int action = command.getInt("action");
            JSONArray points = command.getJSONArray("points");
            long now = SystemClock.uptimeMillis();
            if ((action & 255) == MotionEvent.ACTION_DOWN) downTime = now;
            MotionEvent.PointerProperties[] props = new MotionEvent.PointerProperties[points.length()];
            MotionEvent.PointerCoords[] coords = new MotionEvent.PointerCoords[points.length()];
            for (int i=0; i<points.length(); i++) {
                JSONArray p = points.getJSONArray(i);
                props[i] = new MotionEvent.PointerProperties();
                props[i].id = p.getInt(0); props[i].toolType = MotionEvent.TOOL_TYPE_FINGER;
                coords[i] = new MotionEvent.PointerCoords();
                coords[i].x = (float)p.getDouble(1); coords[i].y = (float)p.getDouble(2);
                coords[i].pressure = 1; coords[i].size = 0.1f;
            }
            MotionEvent event = MotionEvent.obtain(downTime, now, action, points.length(), props,
                coords, 0, 0, 1, 1, 0, 0, InputDevice.SOURCE_TOUCHSCREEN, 0);
            boolean ok = (Boolean)inject.invoke(manager, event, 2);
            event.recycle();
            System.out.println(ok ? "INJECTED" : "REJECTED"); System.out.flush();
            if (!ok) System.exit(2);
        }
    }
}
