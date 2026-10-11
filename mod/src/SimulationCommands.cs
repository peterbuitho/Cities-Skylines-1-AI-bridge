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
            float y = Singleton<TerrainManager>.instance.SampleRawHeightSmooth(new Vector3(x, 0f, z));

            camera.m_targetPosition = new Vector3(x, y, z);
            camera.m_currentPosition = camera.m_targetPosition;
            camera.m_targetSize = size;
            camera.m_currentSize = size;

            return CommandResult.FromJson("{\"ok\":true,\"x\":" + JsonUtil.Number(x) +
                ",\"z\":" + JsonUtil.Number(z) +
                ",\"size\":" + JsonUtil.Number(size) + "}");
        }
    }
}
