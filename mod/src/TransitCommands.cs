using System;
using System.Collections.Generic;
using System.Text;
using ColossalFramework;
using ColossalFramework.Math;
using UnityEngine;

namespace SkylinesAgentBridge
{
    public static class TransitCommands
    {
        // POST /commands/create-line {"transport":"Metro","segments":"12,34,56"}
        // segments: station track segment ids in travel order. The line runs out along them and back,
        // stopping on the lane that points the way it is going, then closes on its first stop.
        public static CommandResult CreateLine(string body)
        {
            string transportText = JsonUtil.GetString(body, "transport", "Metro");
            string[] parts = JsonUtil.GetString(body, "segments", "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 2)
            {
                return CommandResult.Fail("segments needs at least two station track segment ids.");
            }

            TransportInfo.TransportType type;
            try
            {
                type = (TransportInfo.TransportType)Enum.Parse(typeof(TransportInfo.TransportType), transportText, true);
            }
            catch (ArgumentException)
            {
                return CommandResult.Fail("Unknown transport: " + transportText);
            }

            TransportManager transport = Singleton<TransportManager>.instance;
            TransportInfo info = transport.GetTransportInfo(type);
            if (info == null)
            {
                return CommandResult.Fail("Transport is not available: " + transportText);
            }

            NetManager net = NetManager.instance;
            ushort[] segments = new ushort[parts.Length];
            for (int i = 0; i < parts.Length; i++)
            {
                if (!ushort.TryParse(parts[i].Trim(), out segments[i]) || (net.m_segments.m_buffer[segments[i]].m_flags & NetSegment.Flags.Created) == 0)
                {
                    return CommandResult.Fail("Not a segment: " + parts[i]);
                }
            }

            // out: 0..n-1, back: n-2..1
            List<Vector3> stops = new List<Vector3>();
            for (int i = 0; i < segments.Length; i++)
            {
                stops.Add(StopPosition(segments, i, true));
            }
            for (int i = segments.Length - 2; i >= 1; i--)
            {
                stops.Add(StopPosition(segments, i, false));
            }

            SimulationManager simulation = Singleton<SimulationManager>.instance;
            ushort line;
            if (!transport.CreateLine(out line, ref simulation.m_randomizer, info, true))
            {
                return CommandResult.Fail("The game could not create a line.");
            }

            int added = 0;
            for (int i = 0; i < stops.Count; i++)
            {
                if (transport.m_lines.m_buffer[line].AddStop(line, -1, stops[i], false))
                {
                    added++;
                }
            }

            ushort first = transport.m_lines.m_buffer[line].m_stops;
            bool closed = first != 0 && added == stops.Count &&
                transport.m_lines.m_buffer[line].AddStop(line, -1, net.m_nodes.m_buffer[first].m_position, false);

            return CommandResult.FromJson("{\"ok\":" + JsonUtil.Bool(closed) + ",\"lineId\":" + line + ",\"stopsWanted\":" + stops.Count +
                ",\"stopsAdded\":" + added + ",\"closed\":" + JsonUtil.Bool(closed) +
                (closed ? "" : ",\"error\":\"The line was created but could not be completed.\"") + "}");
        }

        // The middle of the vehicle lane on a station track that points the way the line is travelling.
        private static Vector3 StopPosition(ushort[] segments, int index, bool outbound)
        {
            NetManager net = NetManager.instance;
            NetSegment segment = net.m_segments.m_buffer[segments[index]];
            int from = outbound ? Math.Max(index - 1, 0) : Math.Min(index + 1, segments.Length - 1);
            int to = outbound ? Math.Min(index + 1, segments.Length - 1) : Math.Max(index - 1, 0);
            Vector3 travel = net.m_segments.m_buffer[segments[to]].m_middlePosition - net.m_segments.m_buffer[segments[from]].m_middlePosition;
            Vector3 along = net.m_nodes.m_buffer[segment.m_endNode].m_position - net.m_nodes.m_buffer[segment.m_startNode].m_position;
            bool wantForward = Vector3.Dot(travel, along) >= 0f;
            if ((segment.m_flags & NetSegment.Flags.Invert) != 0)
            {
                wantForward = !wantForward;
            }

            NetInfo.Lane[] lanes = segment.Info.m_lanes;
            uint laneId = segment.m_lanes;
            Vector3 fallback = segment.m_middlePosition;
            for (int l = 0; lanes != null && l < lanes.Length && laneId != 0; l++)
            {
                if ((lanes[l].m_laneType & NetInfo.LaneType.Vehicle) != 0)
                {
                    Vector3 position = net.m_lanes.m_buffer[laneId].CalculatePosition(0.5f);
                    fallback = position;
                    bool forward = (lanes[l].m_finalDirection & NetInfo.Direction.Forward) != 0;
                    if (forward == wantForward)
                    {
                        return position;
                    }
                }
                laneId = net.m_lanes.m_buffer[laneId].m_nextLane;
            }
            return fallback;
        }

        // POST /commands/unlock-area {"x":-3400,"z":-600}: buys the map tile under a world position.
        // Zoned land outside the owned tiles never develops. The tile must touch one already owned.
        public static CommandResult UnlockArea(string body)
        {
            GameAreaManager areas = Singleton<GameAreaManager>.instance;
            Vector3 position = new Vector3(JsonUtil.GetNumber(body, "x", 0f), 0f, JsonUtil.GetNumber(body, "z", 0f));
            int tileX;
            int tileZ;
            areas.GetTileXZ(position, out tileX, out tileZ);
            bool already = areas.IsUnlocked(tileX, tileZ);
            bool unlocked = already || areas.UnlockArea(areas.GetTileIndex(tileX, tileZ));
            return CommandResult.FromJson("{\"ok\":" + JsonUtil.Bool(unlocked) + ",\"tileX\":" + tileX + ",\"tileZ\":" + tileZ +
                ",\"alreadyOwned\":" + JsonUtil.Bool(already) + ",\"ownedTiles\":" + areas.m_areaCount + ",\"maxTiles\":" + areas.MaxAreaCount +
                (unlocked ? "" : ",\"error\":\"The game refused: the tile must touch an owned tile and the tile limit must not be reached.\"") + "}");
        }

        // GET /state/lines
        public static CommandResult BuildLinesJson()
        {
            TransportManager transport = Singleton<TransportManager>.instance;
            StringBuilder json = new StringBuilder();
            json.Append("{\"ok\":true,\"lines\":[");
            bool first = true;
            for (int i = 1; i < transport.m_lines.m_buffer.Length; i++)
            {
                TransportLine line = transport.m_lines.m_buffer[i];
                if ((line.m_flags & TransportLine.Flags.Created) == 0 || line.Info == null)
                {
                    continue;
                }

                json.Append(first ? "" : ",").Append("{\"id\":").Append(i);
                first = false;
                json.Append(",\"transport\":\"").Append(line.Info.m_transportType).Append("\"");
                json.Append(",\"flags\":\"").Append(line.m_flags).Append("\"");
                json.Append(",\"stops\":").Append(line.CountStops((ushort)i));
                json.Append(",\"vehicles\":").Append(line.CountVehicles((ushort)i));
                json.Append(",\"lengthMeters\":").Append(JsonUtil.Number(line.m_totalLength));
                json.Append(",\"passengersLastWeek\":").Append(line.m_passengers.m_residentPassengers.m_averageCount + line.m_passengers.m_touristPassengers.m_averageCount);
                json.Append(",\"stopList\":[");
                NetManager net = NetManager.instance;
                int count = line.CountStops((ushort)i);
                for (int s = 0; s < count; s++)
                {
                    ushort stop = line.GetStop(s);
                    NetNode node = net.m_nodes.m_buffer[stop];
                    json.Append(s == 0 ? "" : ",").Append("{\"node\":").Append(stop);
                    json.Append(",\"x\":").Append(JsonUtil.Number(node.m_position.x)).Append(",\"z\":").Append(JsonUtil.Number(node.m_position.z));
                    json.Append(",\"y\":").Append(JsonUtil.Number(node.m_position.y));
                    json.Append(",\"platformLane\":").Append(node.m_lane);
                    json.Append(",\"platformSegment\":").Append(node.m_lane == 0 ? 0 : net.m_lanes.m_buffer[node.m_lane].m_segment);
                    for (int k = 0; k < 8; k++)
                    {
                        ushort leg = node.GetSegment(k);
                        if (leg != 0 && net.m_segments.m_buffer[leg].m_startNode == stop)
                        {
                            NetSegment legData = net.m_segments.m_buffer[leg];
                            json.Append(",\"legFlags\":\"").Append(legData.m_flags).Append("\",\"legPath\":").Append(legData.m_path);
                            json.Append(",\"legProblems\":\"").Append(legData.m_problems.ToString()).Append("\"");
                        }
                    }
                    json.Append("}");
                }
                json.Append("]}");
            }
            json.Append("]}");
            return CommandResult.FromJson(json.ToString());
        }
    }
}
