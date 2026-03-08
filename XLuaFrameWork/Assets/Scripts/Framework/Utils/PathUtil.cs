using UnityEngine;

namespace Framework.Utils
{
    public class PathUtil
    {
        // 根目录
        private static readonly string AssetsPath = Application.dataPath;
        
        // 需要打Bundle的目录
        public static readonly string BuildResourcesPath = AssetsPath + "/BuildResources/";

        // Bundle输出目录
        public static readonly string BundleOutputPath = Application.streamingAssetsPath;
        
        /// <summary>
        /// 获取Unity的相对路径
        /// </summary>
        /// <param name="path">文件的绝对路径</param>
        /// <returns>相对路径</returns>
        public static string GetUnityPath(string path)
        {
            if(string.IsNullOrEmpty(path))
                return string.Empty;
            return path.Substring(path.IndexOf("Assets"));
        }

        /// <summary>
        /// 获取标准路径
        /// </summary>
        /// <param name="path">初始路径</param>
        /// <returns>标准路径</returns>
        public static string GetStandardPath(string path)
        {
            if(string.IsNullOrEmpty(path))
                return string.Empty;
            return path.Trim().Replace("\\", "/");
        }
    }
}