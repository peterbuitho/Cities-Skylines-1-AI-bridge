using System.Text;
using ColossalFramework;
using UnityEngine;

namespace SkylinesAgentBridge
{
    // GET /state/move-in: why do new households not arrive? Outside connections, homes and who is on the way.
    public static class Diagnostics
    {
        private const int MaxSamples = 12;

        public static CommandResult BuildMoveInJson()
        {
            StringBuilder json = new StringBuilder();
            json.Append("{\"ok\":true");
            AppendOutsideNodes(json);
            AppendBuildings(json);
            AppendCitizens(json);
            json.Append(",\"pathUnits\":").Append(Singleton<PathManager>.instance.m_pathUnitCount);
            AppendProbes(json);
            json.Append("}");
            return CommandResult.FromJson(json.ToString());
        }

        // GET /state/route?fx=&fz=&tx=&tz=&drive=1: starts one car route search between two points and
        // reports every earlier search that has finished. Call it without fx to only collect results.
        private static readonly System.Collections.Generic.List<uint> RouteUnits = new System.Collections.Generic.List<uint>();
        private static readonly System.Collections.Generic.List<string> RouteLabels = new System.Collections.Generic.List<string>();

        public static CommandResult BuildRouteJson(bool start, float fx, float fz, float tx, float tz, bool driveOnly, float maxLength, string label)
        {
            PathManager paths = Singleton<PathManager>.instance;
            SimulationManager simulation = Singleton<SimulationManager>.instance;
            StringBuilder json = new StringBuilder();
            json.Append("{\"ok\":true,\"results\":[");
            bool first = true;
            for (int i = RouteUnits.Count - 1; i >= 0; i--)
            {
                PathUnit unit = paths.m_pathUnits.m_buffer[RouteUnits[i]];
                bool ready = (unit.m_pathFindFlags & PathUnit.FLAG_READY) != 0;
                bool failed = (unit.m_pathFindFlags & PathUnit.FLAG_FAILED) != 0;
                if (!ready && !failed)
                {
                    continue;
                }
                json.Append(first ? "" : ",").Append("{\"label\":\"").Append(JsonUtil.Escape(RouteLabels[i])).Append("\"");
                first = false;
                json.Append(",\"found\":").Append(JsonUtil.Bool(ready)).Append(",\"length\":").Append(JsonUtil.Number(unit.m_length)).Append("}");
                paths.ReleasePath(RouteUnits[i]);
                RouteUnits.RemoveAt(i);
                RouteLabels.RemoveAt(i);
            }
            json.Append("],\"pending\":").Append(RouteUnits.Count);

            if (start)
            {
                NetInfo.LaneType lanes = driveOnly ? NetInfo.LaneType.Vehicle : (NetInfo.LaneType.Vehicle | NetInfo.LaneType.Pedestrian);
                PathUnit.Position from;
                PathUnit.Position to;
                bool fromFound = PathManager.FindPathPosition(new Vector3(fx, 0f, fz), ItemClass.Service.Road, lanes,
                    VehicleInfo.VehicleType.Car, VehicleInfo.VehicleCategory.All, true, false, 400f, false, true, out from);
                bool toFound = PathManager.FindPathPosition(new Vector3(tx, 0f, tz), ItemClass.Service.Road, lanes,
                    VehicleInfo.VehicleType.Car, VehicleInfo.VehicleCategory.All, true, false, 400f, false, true, out to);
                // Whole numbers below 40000 with z = -1 mean "this segment id", for roads stacked above each other.
                if (fz == -1f) fromFound = SegmentPosition((ushort)fx, out from);
                if (tz == -1f) toFound = SegmentPosition((ushort)tx, out to);
                json.Append(",\"fromSegment\":").Append(from.m_segment).Append(",\"toSegment\":").Append(to.m_segment);
                uint created = 0;
                bool ok = fromFound && toFound && paths.CreatePath(out created, ref simulation.m_randomizer, simulation.m_currentBuildIndex, from,
                    default(PathUnit.Position), to, default(PathUnit.Position), default(PathUnit.Position), lanes, VehicleInfo.VehicleType.Car,
                    VehicleInfo.VehicleCategory.All, maxLength, false, false, false, false, false, false, false, false, false);
                json.Append(",\"started\":").Append(JsonUtil.Bool(ok));
                if (ok)
                {
                    RouteUnits.Add(created);
                    RouteLabels.Add(label);
                }
            }
            json.Append("}");
            return CommandResult.FromJson(json.ToString());
        }

        private static bool SegmentPosition(ushort segment, out PathUnit.Position position)
        {
            position = default(PathUnit.Position);
            NetInfo info = NetManager.instance.m_segments.m_buffer[segment].Info;
            for (int l = 0; info != null && info.m_lanes != null && l < info.m_lanes.Length; l++)
            {
                if ((info.m_lanes[l].m_laneType & NetInfo.LaneType.Vehicle) != 0)
                {
                    position.m_segment = segment;
                    position.m_lane = (byte)l;
                    position.m_offset = 128;
                    return true;
                }
            }
            return false;
        }

        // Each call reports the route searches started by the call before it, then starts new ones:
        // from every road connection that sends traffic in, to one house, as a resident's car would drive.
        private static readonly System.Collections.Generic.List<uint[]> Probes = new System.Collections.Generic.List<uint[]>();
        private static readonly float[] ProbeLengths = { 20000f, 200000f };

        private static void AppendProbes(StringBuilder json)
        {
            PathManager paths = Singleton<PathManager>.instance;
            BuildingManager buildings = BuildingManager.instance;
            SimulationManager simulation = Singleton<SimulationManager>.instance;
            const NetInfo.LaneType lanes = NetInfo.LaneType.Vehicle | NetInfo.LaneType.Pedestrian;

            json.Append(",\"probeResults\":[");
            for (int i = 0; i < Probes.Count; i++)
            {
                uint[] p = Probes[i];
                PathUnit unit = paths.m_pathUnits.m_buffer[p[0]];
                json.Append(i == 0 ? "" : ",").Append("{\"from\":").Append(p[1]).Append(",\"to\":").Append(p[2]);
                json.Append(",\"maxLength\":").Append(p[3]);
                json.Append(",\"ready\":").Append(JsonUtil.Bool((unit.m_pathFindFlags & PathUnit.FLAG_READY) != 0));
                json.Append(",\"failed\":").Append(JsonUtil.Bool((unit.m_pathFindFlags & PathUnit.FLAG_FAILED) != 0));
                json.Append(",\"length\":").Append(JsonUtil.Number(unit.m_length)).Append("}");
                paths.ReleasePath(p[0]);
            }
            Probes.Clear();
            json.Append("]");

            ushort house = 0;
            for (int i = 1; i < buildings.m_buildings.m_buffer.Length && house == 0; i++)
            {
                Building b = buildings.m_buildings.m_buffer[i];
                if ((b.m_flags & Building.Flags.Created) != 0 && b.Info != null && b.Info.m_class.m_service == ItemClass.Service.Residential)
                {
                    house = (ushort)i;
                }
            }

            json.Append(",\"probesStarted\":[");
            if (house != 0)
            {
                PathUnit.Position end;
                bool endFound = PathManager.FindPathPosition(buildings.m_buildings.m_buffer[house].m_position, ItemClass.Service.Road, lanes,
                    VehicleInfo.VehicleType.Car, VehicleInfo.VehicleCategory.All, false, false, 32f, false, true, out end);
                bool first = true;
                for (int i = 1; i < buildings.m_buildings.m_buffer.Length; i++)
                {
                    Building b = buildings.m_buildings.m_buffer[i];
                    if ((b.m_flags & Building.Flags.Created) == 0 || b.Info == null || !(b.Info.m_buildingAI is OutsideConnectionAI) ||
                        b.Info.m_class.m_service != ItemClass.Service.Road || (b.m_flags & Building.Flags.Outgoing) == 0)
                    {
                        continue;
                    }

                    PathUnit.Position start;
                    bool startFound = PathManager.FindPathPosition(b.m_position, ItemClass.Service.Road, lanes,
                        VehicleInfo.VehicleType.Car, VehicleInfo.VehicleCategory.All, false, false, 32f, false, true, out start);
                    json.Append(first ? "" : ",").Append("{\"from\":").Append(i).Append(",\"to\":").Append(house);
                    first = false;
                    json.Append(",\"startLaneFound\":").Append(JsonUtil.Bool(startFound)).Append(",\"startSegment\":").Append(start.m_segment);
                    json.Append(",\"endLaneFound\":").Append(JsonUtil.Bool(endFound)).Append(",\"endSegment\":").Append(end.m_segment);
                    json.Append(",\"leavingHumanOk\":").Append(b.m_incomingProblemTimer).Append(",\"leavingHumanFailed\":").Append(b.m_seniors);
                    json.Append(",\"leavingDummyOk\":").Append(b.m_youngs).Append(",\"leavingDummyFailed\":").Append(b.m_education2).Append("}");
                    if (!startFound || !endFound)
                    {
                        continue;
                    }

                    for (int k = 0; k < ProbeLengths.Length; k++)
                    {
                        uint unit;
                        if (paths.CreatePath(out unit, ref simulation.m_randomizer, simulation.m_currentBuildIndex, start, default(PathUnit.Position),
                            end, default(PathUnit.Position), default(PathUnit.Position), lanes, VehicleInfo.VehicleType.Car, VehicleInfo.VehicleCategory.All,
                            ProbeLengths[k], false, false, false, false, false, false, false, false, false))
                        {
                            Probes.Add(new uint[] { unit, (uint)i, house, (uint)ProbeLengths[k] });
                        }
                    }
                }
            }
            json.Append("]");
        }

        // GET /state/growth: why does zoned land not develop? The demand the game really uses, whether it
        // has found a good place per zone, and how many zoned rows are free to build on.
        public static CommandResult BuildGrowthJson()
        {
            ZoneManager zones = Singleton<ZoneManager>.instance;
            StringBuilder json = new StringBuilder();
            json.Append("{\"ok\":true,\"actualDemand\":{\"residential\":").Append(zones.m_actualResidentialDemand);
            json.Append(",\"commercial\":").Append(zones.m_actualCommercialDemand);
            json.Append(",\"workplace\":").Append(zones.m_actualWorkplaceDemand).Append("}");

            // The numbers ZoneManager.CalculateResidentialDemand works from, for the whole city.
            District city = Singleton<DistrictManager>.instance.m_districts.m_buffer[0];
            json.Append(",\"jobs\":").Append(city.m_commercialData.m_finalHomeOrWorkCount + city.m_industrialData.m_finalHomeOrWorkCount + city.m_officeData.m_finalHomeOrWorkCount + city.m_playerData.m_finalHomeOrWorkCount);
            json.Append(",\"emptyJobs\":").Append(city.m_commercialData.m_finalEmptyCount + city.m_industrialData.m_finalEmptyCount + city.m_officeData.m_finalEmptyCount + city.m_playerData.m_finalEmptyCount);
            json.Append(",\"homePlaces\":").Append(city.m_residentialData.m_finalHomeOrWorkCount);
            json.Append(",\"emptyHomePlaces\":").Append(city.m_residentialData.m_finalEmptyCount);
            json.Append(",\"unemployed\":").Append(city.m_educated0Data.m_finalUnemployed + city.m_educated1Data.m_finalUnemployed + city.m_educated2Data.m_finalUnemployed + city.m_educated3Data.m_finalUnemployed);
            json.Append(",\"electricityCapacity\":").Append(city.GetElectricityCapacity());
            json.Append(",\"electricityConsumption\":").Append(city.GetElectricityConsumption());
            json.Append(",\"garbageAmount\":").Append(city.GetGarbageAmount());
            json.Append(",\"garbageCapacity\":").Append(city.GetGarbageCapacity());
            json.Append(",\"deadCount\":").Append(city.GetDeadCount());
            json.Append(",\"homeless\":").Append(city.m_educated0Data.m_finalHomeless + city.m_educated1Data.m_finalHomeless + city.m_educated2Data.m_finalHomeless + city.m_educated3Data.m_finalHomeless);

            System.Reflection.FieldInfo field = typeof(ZoneManager).GetField("m_goodAreaFound",
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic);
            short[] good = field == null ? null : field.GetValue(zones) as short[];

            int[] freeRows = new int[16];
            int[] blocks = new int[16];
            int created = 0;
            for (int i = 1; i < zones.m_blocks.m_buffer.Length; i++)
            {
                ZoneBlock block = zones.m_blocks.m_buffer[i];
                if ((block.m_flags & 1u) == 0)
                {
                    continue;
                }
                created++;
                ulong free = block.m_valid & ~(block.m_occupied1 | block.m_occupied2);
                bool counted = false;
                for (int row = 0; row < block.RowCount; row++)
                {
                    int zone = (int)block.GetZone(0, row);
                    if (zone <= 0 || zone >= 16)
                    {
                        continue;
                    }
                    if (!counted)
                    {
                        blocks[zone]++;
                        counted = true;
                    }
                    if ((free & (1UL << (row << 3))) != 0)
                    {
                        freeRows[zone]++;
                    }
                }
            }

            json.Append(",\"zoneBlocks\":").Append(created).Append(",\"zones\":[");
            bool first = true;
            for (int zone = 1; zone < 16; zone++)
            {
                if (blocks[zone] == 0)
                {
                    continue;
                }
                json.Append(first ? "" : ",").Append("{\"zone\":\"").Append((ItemClass.Zone)zone).Append("\"");
                first = false;
                json.Append(",\"blocks\":").Append(blocks[zone]).Append(",\"freeRows\":").Append(freeRows[zone]);
                json.Append(",\"goodAreaFound\":").Append(good != null && zone < good.Length ? good[zone].ToString() : "null").Append("}");
            }
            json.Append("]}");
            return CommandResult.FromJson(json.ToString());
        }

        private static void AppendPosition(StringBuilder json, Vector3 p)
        {
            json.Append("\"x\":").Append(JsonUtil.Number(p.x)).Append(",\"z\":").Append(JsonUtil.Number(p.z));
        }

        private static void AppendOutsideNodes(StringBuilder json)
        {
            NetManager net = NetManager.instance;
            json.Append(",\"outsideNodes\":[");
            bool first = true;
            for (int i = 1; i < net.m_nodes.m_buffer.Length; i++)
            {
                NetNode node = net.m_nodes.m_buffer[i];
                if ((node.m_flags & NetNode.Flags.Created) == 0 || (node.m_flags & NetNode.Flags.Outside) == 0 || node.Info == null)
                {
                    continue;
                }

                json.Append(first ? "" : ",").Append("{\"id\":").Append(i).Append(",");
                first = false;
                AppendPosition(json, node.m_position);
                json.Append(",\"service\":\"").Append(node.Info.m_class.m_service).Append("\"");
                json.Append(",\"building\":").Append(node.m_building);
                json.Append(",\"flags\":\"").Append(node.m_flags).Append("\",\"segments\":[");
                bool firstSegment = true;
                for (int s = 0; s < 8; s++)
                {
                    ushort segmentId = node.GetSegment(s);
                    if (segmentId == 0)
                    {
                        continue;
                    }

                    NetSegment segment = net.m_segments.m_buffer[segmentId];
                    int forward = 0;
                    int backward = 0;
                    NetInfo.Lane[] lanes = segment.Info.m_lanes;
                    for (int l = 0; lanes != null && l < lanes.Length; l++)
                    {
                        if ((lanes[l].m_laneType & NetInfo.LaneType.Vehicle) == 0)
                        {
                            continue;
                        }
                        if ((lanes[l].m_finalDirection & NetInfo.Direction.Forward) != 0) forward++;
                        if ((lanes[l].m_finalDirection & NetInfo.Direction.Backward) != 0) backward++;
                    }

                    json.Append(firstSegment ? "" : ",").Append("{\"id\":").Append(segmentId);
                    firstSegment = false;
                    json.Append(",\"prefab\":\"").Append(JsonUtil.Escape(segment.Info.name)).Append("\"");
                    json.Append(",\"nodeIsStart\":").Append(JsonUtil.Bool(segment.m_startNode == i));
                    json.Append(",\"invert\":").Append(JsonUtil.Bool((segment.m_flags & NetSegment.Flags.Invert) != 0));
                    json.Append(",\"forwardLanes\":").Append(forward).Append(",\"backwardLanes\":").Append(backward).Append("}");
                }
                json.Append("]}");
            }
            json.Append("]");
        }

        private static void AppendBuildings(StringBuilder json)
        {
            BuildingManager buildings = BuildingManager.instance;
            CitizenManager citizens = CitizenManager.instance;
            StringBuilder outside = new StringBuilder();
            int houses = 0, homes = 0, homesWithPeople = 0, residents = 0, movingIn = 0;

            for (int i = 1; i < buildings.m_buildings.m_buffer.Length; i++)
            {
                Building building = buildings.m_buildings.m_buffer[i];
                if ((building.m_flags & Building.Flags.Created) == 0 || building.Info == null)
                {
                    continue;
                }

                if (building.Info.m_buildingAI is OutsideConnectionAI)
                {
                    outside.Append(outside.Length == 0 ? "" : ",").Append("{\"id\":").Append(i).Append(",");
                    AppendPosition(outside, building.m_position);
                    outside.Append(",\"service\":\"").Append(building.Info.m_class.m_service).Append("\"");
                    outside.Append(",\"flags\":\"").Append(building.m_flags).Append("\"}");
                    continue;
                }

                if (building.Info.m_class.m_service != ItemClass.Service.Residential)
                {
                    continue;
                }

                houses++;
                uint unitId = building.m_citizenUnits;
                for (int guard = 0; unitId != 0 && guard < 1000; guard++)
                {
                    CitizenUnit unit = citizens.m_units.m_buffer[unitId];
                    if ((unit.m_flags & CitizenUnit.Flags.Home) != 0)
                    {
                        homes++;
                        bool any = false;
                        for (int c = 0; c < 5; c++)
                        {
                            uint citizenId = unit.GetCitizen(c);
                            if (citizenId == 0)
                            {
                                continue;
                            }
                            any = true;
                            residents++;
                            if ((citizens.m_citizens.m_buffer[citizenId].m_flags & Citizen.Flags.MovingIn) != 0) movingIn++;
                        }
                        if (any) homesWithPeople++;
                    }
                    unitId = unit.m_nextUnit;
                }
            }

            json.Append(",\"outsideBuildings\":[").Append(outside).Append("]");
            json.Append(",\"housing\":{\"houses\":").Append(houses).Append(",\"homes\":").Append(homes);
            json.Append(",\"homesWithPeople\":").Append(homesWithPeople).Append(",\"assignedResidents\":").Append(residents);
            json.Append(",\"stillMovingIn\":").Append(movingIn).Append("}");
        }

        private static void AppendCitizens(StringBuilder json)
        {
            CitizenManager citizens = CitizenManager.instance;
            BuildingManager buildings = BuildingManager.instance;
            int created = 0, withHome = 0, movingIn = 0, tourists = 0, dummy = 0, movingInWithInstance = 0, movingInWithVehicle = 0;
            StringBuilder samples = new StringBuilder();
            int sampled = 0;

            for (int i = 1; i < citizens.m_citizens.m_buffer.Length; i++)
            {
                Citizen citizen = citizens.m_citizens.m_buffer[i];
                if ((citizen.m_flags & Citizen.Flags.Created) == 0)
                {
                    continue;
                }

                created++;
                if (citizen.m_homeBuilding != 0) withHome++;
                if ((citizen.m_flags & Citizen.Flags.Tourist) != 0) tourists++;
                if ((citizen.m_flags & Citizen.Flags.DummyTraffic) != 0) dummy++;
                if ((citizen.m_flags & Citizen.Flags.MovingIn) == 0)
                {
                    continue;
                }

                movingIn++;
                if (citizen.m_instance != 0) movingInWithInstance++;
                if (citizen.m_vehicle != 0) movingInWithVehicle++;
                if (sampled >= MaxSamples)
                {
                    continue;
                }

                samples.Append(sampled == 0 ? "" : ",").Append("{\"citizen\":").Append(i);
                sampled++;
                samples.Append(",\"location\":\"").Append(citizen.CurrentLocation).Append("\"");
                samples.Append(",\"flags\":\"").Append(citizen.m_flags).Append("\"");
                samples.Append(",\"home\":").Append(citizen.m_homeBuilding);
                samples.Append(",\"homeAt\":{");
                AppendPosition(samples, buildings.m_buildings.m_buffer[citizen.m_homeBuilding].m_position);
                samples.Append("},\"vehicle\":").Append(citizen.m_vehicle);
                samples.Append(",\"instance\":").Append(citizen.m_instance);
                if (citizen.m_instance != 0)
                {
                    CitizenInstance instance = citizens.m_instances.m_buffer[citizen.m_instance];
                    samples.Append(",\"instanceFlags\":\"").Append(instance.m_flags).Append("\"");
                    samples.Append(",\"instancePath\":").Append(instance.m_path);
                    samples.Append(",\"target\":").Append(instance.m_targetBuilding);
                    samples.Append(",\"at\":{");
                    AppendPosition(samples, instance.GetLastFramePosition());
                    samples.Append("}");
                }
                samples.Append("}");
            }

            int instances = 0, instancesWaitingPath = 0;
            for (int i = 1; i < citizens.m_instances.m_buffer.Length; i++)
            {
                CitizenInstance.Flags flags = citizens.m_instances.m_buffer[i].m_flags;
                if ((flags & CitizenInstance.Flags.Created) == 0) continue;
                instances++;
                if ((flags & CitizenInstance.Flags.WaitingPath) != 0) instancesWaitingPath++;
            }

            VehicleManager vehicleManager = VehicleManager.instance;
            int vehicles = 0, vehiclesWaitingPath = 0;
            for (int i = 1; i < vehicleManager.m_vehicles.m_buffer.Length; i++)
            {
                Vehicle.Flags flags = vehicleManager.m_vehicles.m_buffer[i].m_flags;
                if ((flags & Vehicle.Flags.Created) == 0) continue;
                vehicles++;
                if ((flags & Vehicle.Flags.WaitingPath) != 0) vehiclesWaitingPath++;
            }

            json.Append(",\"citizens\":{\"created\":").Append(created).Append(",\"withHome\":").Append(withHome);
            json.Append(",\"tourists\":").Append(tourists).Append(",\"dummyTraffic\":").Append(dummy);
            json.Append(",\"movingIn\":").Append(movingIn).Append(",\"movingInWithInstance\":").Append(movingInWithInstance);
            json.Append(",\"movingInWithVehicle\":").Append(movingInWithVehicle).Append("}");
            json.Append(",\"instances\":{\"created\":").Append(instances).Append(",\"waitingPath\":").Append(instancesWaitingPath).Append("}");
            json.Append(",\"vehicles\":{\"created\":").Append(vehicles).Append(",\"waitingPath\":").Append(vehiclesWaitingPath).Append("}");
            json.Append(",\"movingInSamples\":[").Append(samples).Append("]");
        }
    }
}
