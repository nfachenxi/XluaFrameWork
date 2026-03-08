using System.Collections.Generic;
using System.IO;
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
        string[] files = Directory.GetFiles(PathUtil.BuildResourcesPath, "*", SearchOption.AllDirectories);
        // 不处理meta文件
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
            
            
            assetBundle.assetBundleName = bundleName + ".nfa";
            
            assetBundleBuilds.Add(assetBundle);
        }
        
        if (Directory.Exists(PathUtil.BundleOutputPath))
            Directory.Delete(PathUtil.BundleOutputPath, true);
        Directory.CreateDirectory(PathUtil.BundleOutputPath);
        
        BuildPipeline.BuildAssetBundles(PathUtil.BundleOutputPath, assetBundleBuilds.ToArray(),
            BuildAssetBundleOptions.None, target);
        
    }
}
