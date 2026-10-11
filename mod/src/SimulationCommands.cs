using System;
using ColossalFramework;
using UnityEngine;

namespace SkylinesAgentBridge
{
    public static class SimulationCommands
    {
        public static CommandResult SetSimulationSpeed(string body)
        {
            bool paused = JsonUtil.GetBool(body, "paused", false);
            int speed = (int)JsonUtil.GetNumber(body, "speed", 1f);

            if (speed < 1)
            {
                speed = 1;
            }
            if (speed > 3)
            {
                speed = 3;
            }

            SimulationManager simulation = Singleton<SimulationManager>.instance;
            simulation.ForcedSimulationPaused = false;
            simulation.SelectedSimulationSpeed = speed;
            simulation.SimulationPaused = paused;
            DemandBoost.Fast = JsonUtil.GetBool(body, "fastDemand", DemandBoost.Fast);

            return CommandResult.FromJson("{\"ok\":true,\"paused\":" + JsonUtil.Bool(simulation.SimulationPaused) +
                ",\"fastDemand\":" + JsonUtil.Bool(DemandBoost.Fast) +
                ",\"selectedSpeed\":" + simulation.SelectedSimulationSpeed +
                ",\"finalSpeed\":" + simulation.FinalSimulationSpeed + "}");
        }

        // POST /commands/set-ui {"visible":false}: hides or shows the whole game interface, for
        // screenshots and video. Street names are drawn in the world and stay.
        private static bool overlayWasShown;
        private static bool dayNightBefore;
        private static bool dayNightSaved;

        // Reads, and with a value sets, the Image Overlay Renewal mod's "show image" setting.
        // Returns what it was, or null when that mod is not there.
        private static bool? ImageOverlayShown(bool? show)
        {
            try
            {
                foreach (System.Reflection.Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
                {
                    if (assembly.GetName().Name != "ImageOverlayRenewal")
                    {
                        continue;
                    }
                    const System.Reflection.BindingFlags any = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Static |
                        System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic;
                    Type domainType = assembly.GetType("CSLModsCommon.Manager.Domain");
                    Type managerType = assembly.GetType("ImageOverlayRenewal.Managers.ImageOverlayManager");
                    object domain = domainType.GetProperty("DefaultDomain", any).GetValue(null, null);
                    object manager = domainType.GetMethod("GetManager", any).MakeGenericMethod(managerType).Invoke(domain, null);
                    object setting = managerType.GetField("_modSetting", any).GetValue(manager);
                    System.Reflection.PropertyInfo property = setting.GetType().GetProperty("ShowImage", any);
                    bool before = (bool)property.GetValue(setting, null);
                    if (show.HasValue)
                    {
                        property.SetValue(setting, show.Value, null);
                    }
                    return before;
                }
            }
            catch (Exception e)
            {
                Debug.Log("[SkylinesAgentBridge] Image overlay switch failed: " + e.Message);
            }
            return null;
        }

        // POST /commands/set-camera-pose: the fields of set-camera plus
        // {"eye":{"x":..,"y":..,"z":..},"yaw":..,"pitch":..}
        // The game's camera logic keeps running with the set-camera view, so street names, culling
        // and detail levels work as usual, but it smooths and clamps a little on its own, which
        // makes a frame-by-frame recording bob. So the exact eye point and direction are put on the
        // camera at the last moment before each frame is drawn. Ends when set-ui shows the interface.
        private static bool poseActive;
        private static System.Reflection.FieldInfo roadNameAlpha;
        private static bool poseHooked;
        private static Vector3 posePosition;
        private static Quaternion poseRotation;

        public static CommandResult SetCameraPose(string body)
        {
            CameraController controller = ToolsModifierControl.cameraController;
            if (controller == null)
            {
                return CommandResult.Fail("Camera controller is not available.");
            }
            SetCamera(body);
            posePosition = new Vector3(JsonUtil.GetPointNumber(body, "eye", "x", 0f), JsonUtil.GetPointNumber(body, "eye", "y", 100f),
                JsonUtil.GetPointNumber(body, "eye", "z", 0f));
            poseRotation = Quaternion.Euler(JsonUtil.GetNumber(body, "pitch", 30f), JsonUtil.GetNumber(body, "yaw", 0f), 0f);
            poseActive = true;

            // The free camera mode that hides the interface also fades the street names out.
            // Hold them fully visible for as long as poses keep coming.
            NetManager net = Singleton<NetManager>.instance;
            net.RoadNamesVisible = true;
            if (roadNameAlpha == null)
            {
                roadNameAlpha = typeof(NetManager).GetField("m_roadNameAlpha",
                    System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            }
            if (roadNameAlpha != null)
            {
                roadNameAlpha.SetValue(net, 1f);
            }
            if (!poseHooked)
            {
                Camera.onPreCull += ApplyPose;
                poseHooked = true;
            }
            return CommandResult.FromJson("{\"ok\":true,\"frame\":" + Time.frameCount + "}");
        }

        private static void ApplyPose(Camera camera)
        {
            CameraController controller = ToolsModifierControl.cameraController;
            if (poseActive && controller != null && camera.transform == controller.transform)
            {
                camera.transform.position = posePosition;
                camera.transform.rotation = poseRotation;
            }
        }

        // GET /state/camera: where the camera is and which way it looks.
        public static CommandResult CameraState()
        {
            CameraController controller = ToolsModifierControl.cameraController;
            if (controller == null)
            {
                return CommandResult.Fail("Camera controller is not available.");
            }
            Vector3 p = controller.transform.position;
            Vector3 r = controller.transform.rotation.eulerAngles;
            return CommandResult.FromJson("{\"ok\":true,\"eye\":{\"x\":" + JsonUtil.Number(p.x) + ",\"y\":" + JsonUtil.Number(p.y) +
                ",\"z\":" + JsonUtil.Number(p.z) + "},\"yaw\":" + JsonUtil.Number(r.y) + ",\"pitch\":" + JsonUtil.Number(r.x) +
                ",\"frame\":" + Time.frameCount + "}");
        }

        public static CommandResult SetUi(string body)
        {
            bool visible = JsonUtil.GetBool(body, "visible", true);
            // The game's own free camera mode is what hides every panel; UIView.Show leaves the toolbar.
            CameraController camera = ToolsModifierControl.cameraController;
            if (camera != null)
            {
                camera.m_freeCamera = !visible;
            }
            ColossalFramework.UI.UIView.Show(visible);

            // Report the overlays that can paint coloured bands over the city. They were all off when the
            // bands turned out to be the Image Overlay mod; setting them here hid the street names.
            DistrictManager districts = Singleton<DistrictManager>.instance;
            PathVisualizer paths = Singleton<NetManager>.instance.PathVisualizer;
            string overlays = "{\"infoMode\":\"" + Singleton<InfoManager>.instance.CurrentMode + "\"" +
                ",\"districtsVisible\":" + JsonUtil.Bool(districts.DistrictsVisible) +
                ",\"parksVisible\":" + JsonUtil.Bool(districts.ParksVisible) +
                ",\"pathsVisible\":" + JsonUtil.Bool(paths != null && paths.PathsVisible) +
                ",\"waterMapVisible\":" + JsonUtil.Bool(Singleton<WaterManager>.instance.WaterMapVisible) +
                ",\"heatingMapVisible\":" + JsonUtil.Bool(Singleton<WaterManager>.instance.HeatingMapVisible) +
                ",\"electricityMapVisible\":" + JsonUtil.Bool(Singleton<ElectricityManager>.instance.ElectricityMapVisible) +
                ",\"linesVisible\":" + Singleton<TransportManager>.instance.LinesVisible + "}";
            // Full daylight while the interface is hidden: a recording made at dusk comes out dark and hazy.
            SimulationManager simulation = Singleton<SimulationManager>.instance;
            if (!visible)
            {
                if (!dayNightSaved)
                {
                    dayNightBefore = simulation.m_enableDayNight;
                    dayNightSaved = true;
                }
                simulation.m_enableDayNight = false;
            }
            else if (dayNightSaved)
            {
                simulation.m_enableDayNight = dayNightBefore;
                dayNightSaved = false;
            }

            // The pointer tool highlights whatever building is under the mouse in blue; rest it meanwhile.
            ToolController tools = ToolsModifierControl.toolController;
            if (tools != null && tools.CurrentTool != null)
            {
                tools.CurrentTool.enabled = visible;
            }

            // A tracing image laid over the map by the Image Overlay mod goes away for the picture too.
            if (!visible)
            {
                bool? shown = ImageOverlayShown(null);
                if (shown.HasValue && shown.Value)
                {
                    overlayWasShown = true;
                    ImageOverlayShown(false);
                }
            }
            else
            {
                if (overlayWasShown)
                {
                    ImageOverlayShown(true);
                    overlayWasShown = false;
                }
                poseActive = false;   // hand the camera back to the game
            }

            return CommandResult.FromJson("{\"ok\":true,\"visible\":" + JsonUtil.Bool(visible) + ",\"overlaysBefore\":" + overlays + "}");
        }

        public static CommandResult SetCamera(string body)
        {
            CameraController camera = ToolsModifierControl.cameraController;
            if (camera == null)
            {
                return CommandResult.Fail("Camera controller is not available.");
            }

            float x = JsonUtil.GetPointNumber(body, "position", "x", 0f);
            float z = JsonUtil.GetPointNumber(body, "position", "z", 0f);
            float size = JsonUtil.GetNumber(body, "size", 300f);
            // "height" fixes the height of the spot looked at. Without it the camera follows the ground,
            // which makes a moving camera bob over every bump.
            float y = JsonUtil.GetNumber(body, "height", float.NaN);
            if (float.IsNaN(y))
            {
                y = Singleton<TerrainManager>.instance.SampleRawHeightSmooth(new Vector3(x, 0f, z));
            }

            camera.m_targetPosition = new Vector3(x, y, z);
            camera.m_currentPosition = camera.m_targetPosition;
            camera.m_targetSize = size;
            camera.m_currentSize = size;

            // Optional view direction: "rotation" turns the camera round the spot (0 looks north),
            // "tilt" is the angle down from the horizon (90 is straight down, 20 is nearly level).
            float rotation = JsonUtil.GetNumber(body, "rotation", float.NaN);
            float tilt = JsonUtil.GetNumber(body, "tilt", float.NaN);
            if (!float.IsNaN(rotation) || !float.IsNaN(tilt))
            {
                Vector2 angle = camera.m_targetAngle;
                if (!float.IsNaN(rotation)) angle.x = rotation;
                if (!float.IsNaN(tilt)) angle.y = Mathf.Clamp(tilt, 0f, 90f);
                camera.m_targetAngle = angle;
                camera.m_currentAngle = angle;
            }

            // "y" is the height looked at; "frame" lets a recorder wait until this view has been drawn.
            return CommandResult.FromJson("{\"ok\":true,\"x\":" + JsonUtil.Number(x) +
                ",\"z\":" + JsonUtil.Number(z) +
                ",\"y\":" + JsonUtil.Number(y) +
                ",\"frame\":" + Time.frameCount +
                ",\"size\":" + JsonUtil.Number(size) + "}");
        }

        // GET /state/frame: the number of the frame the game is drawing now.
        public static CommandResult Frame()
        {
            return CommandResult.FromJson("{\"ok\":true,\"frame\":" + Time.frameCount + "}");
        }
    }
}
