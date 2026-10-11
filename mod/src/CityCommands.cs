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

        // POST /commands/apply-style {"name":"Aarhus"}: every district, and the land outside all
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
                ",\"buildingsInStyle\":" + (index == 0 ? 0 : districts.m_Styles[index - 1].Count) + "}");
        }
    }
}
