using System;
using System.Collections.Generic;
using System.Reflection;
using System.Text;
using ColossalFramework;
using UnityEngine;

namespace SkylinesAgentBridge
{
    public static class CityCommands
    {
        // POST /commands/unlock-area {"x":-3400,"z":-600}: buys the map tile under a world position.
        // Zoned land outside the owned tiles never develops. The tile must touch one already owned.
        // The game also wants a population milestone per tile; with 81 Tiles installed its own
        // "ignore unlocking" switch is turned on for the duration of the call.
        public static CommandResult UnlockArea(string body)
        {
            GameAreaManager areas = Singleton<GameAreaManager>.instance;
            Vector3 position = new Vector3(JsonUtil.GetNumber(body, "x", 0f), 0f, JsonUtil.GetNumber(body, "z", 0f));
            int tileX;
            int tileZ;
            areas.GetTileXZ(position, out tileX, out tileZ);
            bool already = areas.IsUnlocked(tileX, tileZ);
            bool unlocked = already;
            if (!already)
            {
                PropertyInfo ignore = FindIgnoreUnlocking();
                object before = ignore == null ? null : ignore.GetValue(null, null);
                try
                {
                    if (ignore != null)
                    {
                        ignore.SetValue(null, true, null);
                    }
                    // 81 Tiles widens the grid from 5 to 9 tiles a side.
                    int side = areas.MaxAreaCount > 25 ? 9 : 5;
                    unlocked = areas.UnlockArea(tileZ * side + tileX);
                }
                finally
                {
                    if (ignore != null)
                    {
                        ignore.SetValue(null, before, null);
                    }
                }
            }

            return CommandResult.FromJson("{\"ok\":" + JsonUtil.Bool(unlocked) + ",\"tileX\":" + tileX + ",\"tileZ\":" + tileZ +
                ",\"alreadyOwned\":" + JsonUtil.Bool(already) + ",\"ownedTiles\":" + areas.m_areaCount + ",\"maxTiles\":" + areas.MaxAreaCount +
                (unlocked ? "" : ",\"error\":\"The game refused: the tile must touch an owned tile and the tile limit must not be reached.\"") + "}");
        }

        private static PropertyInfo FindIgnoreUnlocking()
        {
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (assembly.GetName().Name != "EightyOne2")
                {
                    continue;
                }
                foreach (Type type in assembly.GetTypes())
                {
                    if (type.Name == "GameAreaManagerPatches")
                    {
                        return type.GetProperty("IgnoreUnlocking", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
                    }
                }
            }
            return null;
        }

        // POST /commands/create-district {"name":"Trøjborg","x":-900,"z":1400,"radius":300}
        // Paints a round district and names it.
        public static CommandResult CreateDistrict(string body)
        {
            string name = JsonUtil.GetString(body, "name", "");
            float radius = Mathf.Clamp(JsonUtil.GetNumber(body, "radius", 200f), 32f, 2000f);
            Vector3 position = new Vector3(JsonUtil.GetNumber(body, "x", 0f), 0f, JsonUtil.GetNumber(body, "z", 0f));
            if (name.Length == 0)
            {
                return CommandResult.Fail("name is required.");
            }

            DistrictManager districts = Singleton<DistrictManager>.instance;
            byte district;
            if (!districts.CreateDistrict(out district))
            {
                return CommandResult.Fail("The game could not create a district (the limit is 127).");
            }

            DistrictTool.ApplyBrush(DistrictTool.Layer.Districts, district, radius, position, position);
            IEnumerator<bool> rename = districts.SetDistrictName(district, name);
            while (rename.MoveNext())
            {
            }

            return CommandResult.FromJson("{\"ok\":true,\"district\":" + district + ",\"name\":\"" + JsonUtil.Escape(name) + "\"}");
        }

        // POST /commands/refresh-water-grid: recomputes which ground every water pipe serves, for the
        // whole map. The game redoes this only round a pipe that changes, and then finds other pipes
        // by their middle point, so a long pipe loses ground wherever another pipe is built or removed
        // far from its middle. Call it after any pipe work when pipes are long.
        public static CommandResult RefreshWaterGrid()
        {
            Singleton<WaterManager>.instance.UpdateGrid(-8640f, -8640f, 8640f, 8640f);
            return CommandResult.FromJson("{\"ok\":true}");
        }

        // POST /commands/name-park {"name":"Tivoli Friheden","x":..,"z":..,"radius":200}: names the park
        // area at a position. Where there is none, an amusement park area of that radius is made first.
        public static CommandResult NamePark(string body)
        {
            string name = JsonUtil.GetString(body, "name", "");
            float radius = Mathf.Clamp(JsonUtil.GetNumber(body, "radius", 200f), 32f, 2000f);
            Vector3 position = new Vector3(JsonUtil.GetNumber(body, "x", 0f), 0f, JsonUtil.GetNumber(body, "z", 0f));
            DistrictManager districts = Singleton<DistrictManager>.instance;

            // {"id":n} tells that park area's name; {"id":n,"release":true} removes the area;
            // {"id":n,"name":".."} renames it. Without id the area is found by position.
            int id = (int)JsonUtil.GetNumber(body, "id", 0f);
            if (id > 0 && id < districts.m_parks.m_buffer.Length)
            {
                if ((districts.m_parks.m_buffer[id].m_flags & DistrictPark.Flags.Created) == 0)
                {
                    return CommandResult.FromJson("{\"ok\":true,\"park\":" + id + ",\"exists\":false}");
                }
                if (JsonUtil.GetBool(body, "release", false))
                {
                    districts.ReleasePark((byte)id);
                    return CommandResult.FromJson("{\"ok\":true,\"park\":" + id + ",\"released\":true}");
                }
                if (name.Length == 0)
                {
                    Vector3 at = districts.m_parks.m_buffer[id].m_nameLocation;
                    return CommandResult.FromJson("{\"ok\":true,\"park\":" + id + ",\"exists\":true,\"name\":\"" + JsonUtil.Escape(districts.GetParkName(id)) +
                        "\",\"x\":" + Mathf.RoundToInt(at.x) + ",\"z\":" + Mathf.RoundToInt(at.z) + "}");
                }
                IEnumerator<bool> renameById = districts.SetParkName(id, name);
                while (renameById.MoveNext())
                {
                }
                return CommandResult.FromJson("{\"ok\":true,\"park\":" + id + ",\"name\":\"" + JsonUtil.Escape(name) + "\"}");
            }
            if (name.Length == 0)
            {
                return CommandResult.Fail("name is required.");
            }

            byte park = districts.GetPark(position);
            bool created = park == 0;
            if (created)
            {
                if (!districts.CreatePark(out park, DistrictPark.ParkType.AmusementPark, DistrictPark.ParkLevel.Level1))
                {
                    return CommandResult.Fail("The game could not create a park area.");
                }
                DistrictTool.ApplyBrush(DistrictTool.Layer.Parks, park, radius, position, position);
            }
            IEnumerator<bool> rename = districts.SetParkName(park, name);
            while (rename.MoveNext())
            {
            }

            return CommandResult.FromJson("{\"ok\":true,\"park\":" + park + ",\"created\":" + JsonUtil.Bool(created) + ",\"name\":\"" + JsonUtil.Escape(name) + "\"}");
        }

        // POST /commands/create-style {"name":"Aarhus","prefabs":"a_Data;b_Data;..."}
        // Saves a district style, the game's own way of saying which buildings may grow, holding the
        // named building prefabs. The game reads it at the next city load. A style only steers the
        // kinds of building it contains (say, low density housing of levels 1 and 3); the rest of
        // the city keeps growing the game's own buildings.
        public static CommandResult CreateStyle(string body)
        {
            string name = JsonUtil.GetString(body, "name", "");
            string[] prefabs = JsonUtil.GetString(body, "prefabs", "").Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries);
            if (name.Length == 0 || prefabs.Length == 0)
            {
                return CommandResult.Fail("name and prefabs are required.");
            }
            List<string> found = new List<string>();
            foreach (string prefab in prefabs)
            {
                if (PrefabCollection<BuildingInfo>.FindLoaded(prefab.Trim()) != null)
                {
                    // the game adds "_Data" itself when it reads the style
                    string asset = prefab.Trim();
                    found.Add(asset.EndsWith("_Data") ? asset.Substring(0, asset.Length - 5) : asset);
                }
            }
            if (found.Count == 0)
            {
                return CommandResult.Fail("None of the prefabs is loaded.");
            }
            DistrictStyleMetaData style = new DistrictStyleMetaData();
            style.name = name;
            style.builtin = false;
            style.assets = found.ToArray();
            style.steamTags = new string[0];
            StylesHelper.SaveStyle(style, name, false, null);
            return CommandResult.FromJson("{\"ok\":true,\"style\":\"" + JsonUtil.Escape(name) + "\",\"buildings\":" + found.Count +
                ",\"notLoaded\":" + (prefabs.Length - found.Count) + "}");
        }

        // POST /commands/apply-style {"name":"Aarhus","extra":"L1 1x1 Detached;..."}: every district, and the land outside all
        // districts, grows from this style. An empty name goes back to the game's own buildings.
        public static CommandResult ApplyStyle(string body)
        {
            string name = JsonUtil.GetString(body, "name", "");
            DistrictManager districts = Singleton<DistrictManager>.instance;
            ushort index = 0;
            StringBuilder known = new StringBuilder();
            for (int i = 0; districts.m_Styles != null && i < districts.m_Styles.Length; i++)
            {
                known.Append(i == 0 ? "" : ", ").Append(districts.m_Styles[i].Name);
                if (name.Length > 0 && (districts.m_Styles[i].Name == name || districts.m_Styles[i].FullName == name))
                {
                    index = (ushort)(i + 1);
                }
            }
            if (name.Length > 0 && index == 0)
            {
                return CommandResult.Fail("Style was not found: " + name + ". Loaded styles: " + known);
            }
            // A style file can only name custom assets. "extra" adds the game's own buildings to the
            // loaded style, for this session only: send it again after every load.
            int added = 0;
            string extra = JsonUtil.GetString(body, "extra", "");
            if (index != 0 && extra.Length > 0)
            {
                DistrictStyle style = districts.m_Styles[index - 1];
                // Not FindLoaded: for a name that is not loaded it crashes here, inside Loading Screen Mod's name resolver.
                System.Collections.Generic.HashSet<string> wanted = new System.Collections.Generic.HashSet<string>(extra.Split(';'));
                int loaded = PrefabCollection<BuildingInfo>.LoadedCount();
                for (uint i = 0; i < loaded; i++)
                {
                    BuildingInfo info = PrefabCollection<BuildingInfo>.GetLoaded(i);
                    if (info != null && wanted.Contains(info.name) && !style.Contains(info))
                    {
                        style.Add(info);
                        added++;
                    }
                }
                typeof(BuildingManager).GetMethod("RefreshStyleBuildings", BindingFlags.Instance | BindingFlags.NonPublic)
                    .Invoke(Singleton<BuildingManager>.instance, null);
            }
            int changed = 0;
            for (int d = 0; d < districts.m_districts.m_buffer.Length; d++)
            {
                if (d == 0 || (districts.m_districts.m_buffer[d].m_flags & District.Flags.Created) != 0)
                {
                    districts.m_districts.m_buffer[d].m_Style = index;
                    changed++;
                }
            }
            return CommandResult.FromJson("{\"ok\":true,\"style\":\"" + JsonUtil.Escape(name) + "\",\"districts\":" + changed +
                ",\"added\":" + added +
                ",\"buildingsInStyle\":" + (index == 0 ? 0 : districts.m_Styles[index - 1].Count) + "}");
        }
    }
}
