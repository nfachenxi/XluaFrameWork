using System.Collections;
using System.Collections.Generic;
using Framework.Utils;
using UnityEngine;

public class Test : MonoBehaviour
{
    // Start is called before the first frame update
    IEnumerator Start()
    {
        AssetBundleCreateRequest request = AssetBundle.LoadFromFileAsync(PathUtil.BundleOutputPath+ "/ui/prefab/testui.prefab.nfa");
        yield return request;
        
        AssetBundleCreateRequest request1 = AssetBundle.LoadFromFileAsync(PathUtil.BundleOutputPath+ "/ui/res/button_150.png.nfa");
        yield return request1;
        
        AssetBundleRequest bundleRequest = request.assetBundle.LoadAssetAsync("Assets/BuildResources/UI/Prefab/TestUI.prefab");
        yield return bundleRequest;
        
        GameObject go = Instantiate(bundleRequest.asset) as GameObject;
        go.transform.SetParent(this.transform);
        go.SetActive(true);
        go.transform.localPosition = Vector3.zero;
    }

    // Update is called once per frame
    void Update()
    {
        
    }
}
