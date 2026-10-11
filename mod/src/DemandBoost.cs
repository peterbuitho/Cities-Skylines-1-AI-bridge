using ICities;

namespace SkylinesAgentBridge
{
    // The game moves demand towards its own computed value by 2 a step, and every new building
    // takes some away, so a city with much free zoned land grows slowly. With Fast on, demand
    // goes straight to the computed value each step. Set by POST /commands/set-simulation-speed
    // {"fastDemand":true}; not saved with the city.
    public class DemandBoost : DemandExtensionBase
    {
        public static bool Fast;

        public override int OnUpdateDemand(int lastDemand, int nextDemand, int targetDemand)
        {
            return Fast ? targetDemand : nextDemand;
        }
    }
}
