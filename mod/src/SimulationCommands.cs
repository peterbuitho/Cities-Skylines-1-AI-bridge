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

            return CommandResult.FromJson("{\"ok\":true,\"paused\":" + JsonUtil.Bool(simulation.SimulationPaused) +
                ",\"selectedSpeed\":" + simulation.SelectedSimulationSpeed +
                ",\"finalSpeed\":" + simulation.FinalSimulationSpeed + "}");
        }

        // POST /commands/set-ui {"visible":false}: hides or shows the whole game interface, for
        // screenshots and video. Street names are drawn in the world and stay.
        private static int linesVisibleBefore;

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

            // Report, then switch off, the overlays that paint coloured bands over the city.
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
            if (!visible)
            {
                // The game switches these maps back on by itself when their info view is opened.
                Singleton<WaterManager>.instance.WaterMapVisible = false;
                Singleton<WaterManager>.instance.HeatingMapVisible = false;
                Singleton<ElectricityManager>.instance.ElectricityMapVisible = false;
                districts.DistrictsVisible = false;
                districts.ParksVisible = false;
                if (paths != null)
                {
                    paths.PathsVisible = false;
                }
            }

            // Transport lines are drawn as wide coloured bands over everything; take them away too.
            TransportManager transport = Singleton<TransportManager>.instance;
            if (!visible)
            {
                if (transport.LinesVisible != 0)
                {
                    linesVisibleBefore = transport.LinesVisible;
                }
                transport.LinesVisible = 0;
            }
            else if (linesVisibleBefore != 0)
            {
                transport.LinesVisible = linesVisibleBefore;
                linesVisibleBefore = 0;
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
