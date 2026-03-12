using System.Collections.Generic;
using System.IO;
using System.Linq;
using Framework;
using Framework.Utils;
using UnityEditor;
using UnityEngine;

public class BuildTool : Editor
{
    [MenuItem("NFATools/Build Windows Bundle")]
    static void BuildWindowsBundle()
    {
        Build(BuildTarget.StandaloneWindows64);
    }
    
    [MenuItem("NFATools/Build Android Bundle")]
    static void BuildAndroidBundle()
    {
        Build(BuildTarget.Android);
    }
    
    [MenuItem("NFATools/Build IOS Bundle")]
    static void BuildIOSBundle()
    {
        Build(BuildTarget.iOS);
    }
    
    static void Build(BuildTarget target)
    {
        List<AssetBundleBuild> assetBundleBuilds = new List<AssetBundleBuild>();
        
        // 文件信息列表
        List<string> bundleInfos = new List<string>();
        string[] files = Directory.GetFiles(PathUtil.BuildResourcesPath, "*", SearchOption.AllDirectories);
        for (int i = 0; i < files.Length; i++)
        {
            if (files[i].EndsWith(".meta"))
                continue;
            
            AssetBundleBuild assetBundle = new AssetBundleBuild();
            
            string fileName = PathUtil.GetStandardPath(files[i]);
            Debug.Log("file: " + fileName);
            
            string assetName = PathUtil.GetUnityPath(fileName);
            assetBundle.assetNames = new string[] { assetName };

            string bundleName = fileName.Replace(PathUtil.BuildResourcesPath, "").ToLower();
            
            
            assetBundle.assetBundleName = bundleName + AppConst.BundleExtension;
            
            assetBundleBuilds.Add(assetBundle);
            
            // 添加文件和依赖信息
            List<string> dependenceInfo = GetDependence(assetName);
            string bundleInfo = assetName + "|" + bundleName;
            
            if (dependenceInfo.Count > 0)
                bundleInfo = bundleInfo + "|" + string.Join("|", dependenceInfo);
            
            bundleInfos.Add(bundleInfo);
            
            AssetDatabase.Refresh();
        }
        
        if (Directory.Exists(PathUtil.BundleOutputPath))
            Directory.Delete(PathUtil.BundleOutputPath, true);
        Directory.CreateDirectory(PathUtil.BundleOutputPath);

        BuildPipeline.BuildAssetBundles(PathUtil.BundleOutputPath, assetBundleBuilds.ToArray(),
            BuildAssetBundleOptions.None, target);
        File.WriteAllLines(PathUtil.BundleOutputPath + "/" + AppConst.FileListName, bundleInfos);
    }

    /// <summary>
    /// 获取依赖文件列表
    /// </summary>
    /// <param name="curFile"></param>
    /// <returns></returns>
    static List<string> GetDependence(string curFile)
    {
        List<string> dependence = new List<string>();
        string[] files = AssetDatabase.GetDependencies(curFile);
        dependence = files.Where(file => !file.EndsWith(".cs") && !file.Equals(curFile)).ToList();
        return dependence;
    }
}
