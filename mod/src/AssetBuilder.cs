using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using ColossalFramework.Globalization;
using ColossalFramework.IO;
using ColossalFramework.Packaging;
using UnityEngine;

namespace SkylinesAgentBridge
{
    // POST /commands/create-asset
    // {"name":"Aarhus Domkirke","folder":"E:/path/to/files","template":"Statue of Shopping",
    //  "cellWidth":12,"cellLength":6,"description":"..."}
    // Builds a building asset from <folder>/model.obj, diffuse.png and lod.png and saves it as a .crp
    // in the game's local Assets folder, the way the Asset Editor's save does. The game loads it the
    // next time a city loads, under the prefab name "<name>.<name>_Data". Paths use forward slashes:
    // the bridge's JSON reader does not understand escapes.
    public static class AssetBuilder
    {
        public static CommandResult CreateAsset(string body)
        {
            string name = JsonUtil.GetString(body, "name", "");
            string folder = JsonUtil.GetString(body, "folder", "");
            string templateName = JsonUtil.GetString(body, "template", "Statue of Shopping");
            string description = JsonUtil.GetString(body, "description", name);
            int cellWidth = (int)JsonUtil.GetNumber(body, "cellWidth", 4f);
            int cellLength = (int)JsonUtil.GetNumber(body, "cellLength", 4f);
            if (name.Length == 0 || folder.Length == 0)
            {
                return CommandResult.Fail("name and folder are required.");
            }

            string objPath = Path.Combine(folder, "model.obj");
            string diffusePath = Path.Combine(folder, "diffuse.png");
            string lodPath = Path.Combine(folder, "lod.png");
            foreach (string path in new[] { objPath, diffusePath, lodPath })
            {
                if (!File.Exists(path))
                {
                    return CommandResult.Fail("File not found: " + path);
                }
            }

            BuildingInfo template = PrefabCollection<BuildingInfo>.FindLoaded(templateName);
            if (template == null)
            {
                return CommandResult.Fail("Template building was not found: " + templateName);
            }

            Mesh mesh = LoadObj(objPath, name);
            Mesh lodMesh = LoadObj(objPath, name + "_lod");

            GameObject asset = UnityEngine.Object.Instantiate(template.gameObject);
            asset.SetActive(false);
            asset.name = name + "_Data";
            BuildingInfo info = asset.GetComponent<BuildingInfo>();

            MeshRenderer renderer = asset.GetComponent<MeshRenderer>();
            asset.GetComponent<MeshFilter>().sharedMesh = mesh;
            renderer.sharedMaterial = Skin(renderer.sharedMaterial, LoadTexture(diffusePath), name);

            GameObject lod = new GameObject(name + "_LOD");
            lod.SetActive(false);
            lod.AddComponent<MeshFilter>().sharedMesh = lodMesh;
            Material lodTemplate = template.m_lodObject != null && template.m_lodObject.GetComponent<MeshRenderer>() != null
                ? template.m_lodObject.GetComponent<MeshRenderer>().sharedMaterial
                : renderer.sharedMaterial;
            lod.AddComponent<MeshRenderer>().sharedMaterial = Skin(lodTemplate, LoadTexture(lodPath), name + "_lod");
            info.m_lodObject = lod;

            // The template's colour variations would tint the whole facade (one copy in four came out blue).
            info.m_useColorVariations = false;
            info.m_color0 = Color.white;
            info.m_color1 = Color.white;
            info.m_color2 = Color.white;
            info.m_color3 = Color.white;
            info.m_cellWidth = cellWidth;
            info.m_cellLength = cellLength;
            info.m_props = new BuildingInfo.Prop[0];
            info.m_paths = new BuildingInfo.PathInfo[0];
            info.m_subBuildings = new BuildingInfo.SubInfo[0];

            Package package = new Package(name);
            package.packageMainAsset = name;
            CustomAssetMetaData meta = new CustomAssetMetaData();
            meta.name = name;
            meta.timeStamp = DateTime.Now;
            meta.templateName = templateName;
            meta.type = CustomAssetMetaData.Type.Building;
            meta.width = cellWidth;
            meta.length = cellLength;
            meta.service = info.GetService();
            meta.subService = info.GetSubService();
            meta.level = info.m_class != null ? info.m_class.m_level : ItemClass.Level.None;
            meta.steamTags = info.GetSteamTags();
            meta.triangles = mesh.triangles.Length / 3;
            meta.lodTriangles = lodMesh.triangles.Length / 3;
            meta.assetRef = package.AddAsset(name + "_Data", asset);
            package.AddAsset(name, meta, UserAssetType.CustomAssetMetaData);

            Locale locale = new Locale();
            foreach (string id in new[] { "BUILDING_TITLE", "BUILDING_DESC", "BUILDING_SHORT_DESC" })
            {
                Locale.Key key = new Locale.Key();
                key.m_Identifier = id;
                key.m_Key = name + "_Data";
                locale.AddLocalizedString(key, id == "BUILDING_TITLE" ? name : description);
            }
            package.AddAsset(name + "_Locale", locale);

            string savePath = Path.Combine(DataLocation.assetsPath, name + ".crp");
            package.Save(savePath);
            UnityEngine.Object.Destroy(asset);
            UnityEngine.Object.Destroy(lod);

            return CommandResult.FromJson("{\"ok\":true,\"file\":\"" + JsonUtil.Escape(savePath.Replace('\\', '/')) +
                "\",\"prefab\":\"" + JsonUtil.Escape(name + "." + name + "_Data") + "\",\"triangles\":" + meta.triangles + "}");
        }

        // The template's material with our facade on it and flat helper maps: no bumps, no shine,
        // fully solid, no colour variation, no lit windows.
        private static Material Skin(Material template, Texture2D diffuse, string name)
        {
            Material material = new Material(template);
            material.name = name;
            material.SetTexture("_MainTex", diffuse);
            // the game rejects an asset whose helper maps are not the facade's size
            material.SetTexture("_XYSMap", Flat(new Color32(128, 128, 255, 255), diffuse.width, diffuse.height, name + "_xys"));
            material.SetTexture("_ACIMap", Flat(new Color32(0, 0, 0, 255), diffuse.width, diffuse.height, name + "_aci"));
            return material;
        }

        private static Texture2D Flat(Color32 colour, int width, int height, string name)
        {
            Texture2D texture = new Texture2D(width, height, TextureFormat.RGB24, false);
            Color32[] pixels = new Color32[width * height];
            for (int i = 0; i < pixels.Length; i++)
            {
                pixels[i] = colour;
            }
            texture.SetPixels32(pixels);
            texture.Apply();
            texture.name = name;
            return texture;
        }

        private static Texture2D LoadTexture(string path)
        {
            Texture2D texture = new Texture2D(2, 2, TextureFormat.RGB24, false);
            texture.LoadImage(File.ReadAllBytes(path));
            texture.wrapMode = TextureWrapMode.Repeat;
            texture.name = Path.GetFileNameWithoutExtension(path);
            return texture;
        }

        // Reads the plain OBJ that tools/landmarks writes: v, vt and vn lines and triangles "f a/b/c ...".
        private static Mesh LoadObj(string path, string name)
        {
            List<Vector3> positions = new List<Vector3>();
            List<Vector2> uvs = new List<Vector2>();
            List<Vector3> normals = new List<Vector3>();
            List<Vector3> meshPositions = new List<Vector3>();
            List<Vector2> meshUvs = new List<Vector2>();
            List<Vector3> meshNormals = new List<Vector3>();
            List<int> triangles = new List<int>();

            foreach (string line in File.ReadAllLines(path))
            {
                string[] p = line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                if (p.Length == 0)
                {
                    continue;
                }
                if (p[0] == "v")
                {
                    positions.Add(new Vector3(Number(p[1]), Number(p[2]), Number(p[3])));
                }
                else if (p[0] == "vt")
                {
                    uvs.Add(new Vector2(Number(p[1]), Number(p[2])));
                }
                else if (p[0] == "vn")
                {
                    normals.Add(new Vector3(Number(p[1]), Number(p[2]), Number(p[3])));
                }
                else if (p[0] == "f")
                {
                    for (int corner = 1; corner <= 3; corner++)
                    {
                        string[] index = p[corner].Split('/');
                        meshPositions.Add(positions[int.Parse(index[0]) - 1]);
                        meshUvs.Add(uvs[int.Parse(index[1]) - 1]);
                        meshNormals.Add(normals[int.Parse(index[2]) - 1]);
                        triangles.Add(triangles.Count);
                    }
                }
            }

            Mesh mesh = new Mesh();
            mesh.name = name;
            mesh.vertices = meshPositions.ToArray();
            mesh.uv = meshUvs.ToArray();
            mesh.normals = meshNormals.ToArray();
            mesh.triangles = triangles.ToArray();
            // The game rejects a mesh without tangents. The helper maps are flat, so any tangent
            // at right angles to the normal will do.
            Vector4[] tangents = new Vector4[meshNormals.Count];
            for (int i = 0; i < tangents.Length; i++)
            {
                Vector3 side = Vector3.Cross(meshNormals[i], Vector3.up);
                if (side.sqrMagnitude < 0.0001f)
                {
                    side = Vector3.right;
                }
                side.Normalize();
                tangents[i] = new Vector4(side.x, side.y, side.z, 1f);
            }
            mesh.tangents = tangents;
            mesh.RecalculateBounds();
            return mesh;
        }

        private static float Number(string text)
        {
            return float.Parse(text, CultureInfo.InvariantCulture);
        }
    }
}
