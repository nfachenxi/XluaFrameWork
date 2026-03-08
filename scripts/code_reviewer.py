#!/usr/bin/env python3
"""
Unity Code Review Tool
三轮评估：代码质量 -> Unity最佳实践 -> 综合评估
"""

import os
import sys
import json
import requests
from typing import List, Dict, Any
from openai import OpenAI
import git


class CodeReviewer:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.api_base = os.getenv('OPENAI_API_BASE', 'https://api.deepseek.com/v1')
        self.webhook_url = os.getenv('WEBHOOK_URL')
        
        # Unity 项目路径配置（相对于仓库根目录）
        # 例如：'XLuaFrameWork' 或 'XLuaFrameWork/Assets'
        self.unity_project_path = os.getenv('UNITY_PROJECT_PATH', '.')
        
        # 排除的目录（不进行审查）
        self.exclude_dirs = os.getenv('EXCLUDE_DIRS', 'Library,Temp,Logs,obj,bin').split(',')
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not self.webhook_url:
            raise ValueError("WEBHOOK_URL environment variable is required")
        
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_base)
        self.repo = git.Repo('.')
        
        print(f"📁 Unity 项目路径: {self.unity_project_path}")
        print(f"🚫 排除目录: {', '.join(self.exclude_dirs)}")
        
        # 加载提示词模板
        self.prompt_round1 = self._load_prompt('prompts/round1_code_quality.txt')
        self.prompt_round2 = self._load_prompt('prompts/round2_unity_practices.txt')
        self.prompt_round3 = self._load_prompt('prompts/round3_comprehensive.txt')
    
    def _load_prompt(self, filepath: str) -> str:
        """加载提示词文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"⚠️ Warning: Prompt file not found: {filepath}")
            return ""
        except Exception as e:
            print(f"⚠️ Warning: Error loading prompt file {filepath}: {e}")
            return ""
    
    def _should_exclude_path(self, file_path: str) -> bool:
        """检查文件路径是否应该被排除"""
        # 标准化路径
        normalized_path = file_path.replace('\\', '/')
        
        # 检查是否在排除目录中
        for exclude_dir in self.exclude_dirs:
            exclude_dir = exclude_dir.strip()
            if f'/{exclude_dir}/' in f'/{normalized_path}/' or normalized_path.startswith(f'{exclude_dir}/'):
                return True
        
        # 检查是否在指定的 Unity 项目路径内
        if self.unity_project_path != '.':
            unity_path = self.unity_project_path.replace('\\', '/')
            if not normalized_path.startswith(unity_path):
                return True
        
        return False
    
    def get_changed_files(self) -> List[Dict[str, Any]]:
        """获取变更的文件及其内容"""
        changed_files = []
        
        try:
            # 获取最新的commit
            if len(list(self.repo.iter_commits())) < 2:
                print("Repository has less than 2 commits, reviewing all C# files")
                # 如果是首次提交，检查所有C#文件
                search_path = self.unity_project_path if self.unity_project_path != '.' else '.'
                
                for root, dirs, files in os.walk(search_path):
                    # 过滤排除的目录
                    dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
                    
                    for file in files:
                        if file.endswith('.cs'):
                            file_path = os.path.join(root, file).replace('\\', '/')
                            
                            # 检查是否应该排除
                            if self._should_exclude_path(file_path):
                                continue
                            
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                changed_files.append({
                                    'path': file_path,
                                    'content': content,
                                    'status': 'new'
                                })
                            except Exception as e:
                                print(f"Error reading {file_path}: {e}")
            else:
                # 获取最近两次commit之间的差异
                commits = list(self.repo.iter_commits(max_count=2))
                latest_commit = commits[0]
                previous_commit = commits[1]
                
                diff = previous_commit.diff(latest_commit)
                
                for item in diff:
                    # 只处理C#文件
                    if not (item.a_path and item.a_path.endswith('.cs')):
                        continue
                    
                    # 检查是否应该排除
                    if self._should_exclude_path(item.a_path):
                        print(f"⏭️  Skipping excluded file: {item.a_path}")
                        continue
                    
                    file_info = {'path': item.a_path}
                    
                    if item.change_type == 'A':  # 新增文件
                        file_info['status'] = 'new'
                        file_info['content'] = item.b_blob.data_stream.read().decode('utf-8', errors='ignore')
                    elif item.change_type == 'M':  # 修改文件
                        file_info['status'] = 'modified'
                        file_info['content'] = item.b_blob.data_stream.read().decode('utf-8', errors='ignore')
                        file_info['old_content'] = item.a_blob.data_stream.read().decode('utf-8', errors='ignore')
                    elif item.change_type == 'D':  # 删除文件
                        continue  # 跳过删除的文件
                    
                    changed_files.append(file_info)
        
        except Exception as e:
            print(f"Error getting changed files: {e}")
            return []
        
        return changed_files

    def review_round_1_quality(self, file_info: Dict[str, Any]) -> str:
        """第一轮评估：代码质量（命名规范、结构清晰度）"""
        code_context = f"""
## 待评估代码信息

**文件路径：** {file_info['path']}
**文件状态：** {file_info['status']}

**代码内容：**
```csharp
{file_info['content']}
```

---

请按照上述评估标准对这段代码进行详细评审。
"""
        
        full_prompt = self.prompt_round1 + "\n\n" + code_context
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"评估失败: {str(e)}"
    
    def review_round_2_unity(self, file_info: Dict[str, Any]) -> str:
        """第二轮评估：Unity最佳实践（性能、内存管理）"""
        code_context = f"""
## 待评估代码信息

**文件路径：** {file_info['path']}
**文件状态：** {file_info['status']}

**代码内容：**
```csharp
{file_info['content']}
```

---

请按照上述评估标准对这段Unity代码进行详细评审。
"""
        
        full_prompt = self.prompt_round2 + "\n\n" + code_context
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"评估失败: {str(e)}"
    
    def review_round_3_comprehensive(self, file_info: Dict[str, Any], 
                                     round1_result: str, round2_result: str) -> Dict[str, str]:
        """第三轮评估：综合评估并给出最终建议"""
        code_context = f"""
## 待综合评估的代码信息

**文件路径：** {file_info['path']}
**文件状态：** {file_info['status']}

**第一轮评估结果（代码质量）：**
{round1_result}

**第二轮评估结果（Unity最佳实践）：**
{round2_result}

**代码内容：**
```csharp
{file_info['content']}
```

---

请基于以上两轮评估结果，按照评估标准给出综合评审意见。
"""
        
        full_prompt = self.prompt_round3 + "\n\n" + code_context
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.3
            )
            
            final_result = response.choices[0].message.content
            
            return {
                'file_path': file_info['path'],
                'file_status': file_info['status'],
                'round1_quality': round1_result,
                'round2_unity': round2_result,
                'final_review': final_result
            }
        except Exception as e:
            return {
                'file_path': file_info['path'],
                'file_status': file_info['status'],
                'error': f"综合评估失败: {str(e)}"
            }

    def format_webhook_message(self, results: List[Dict[str, str]]) -> Dict[str, str]:
        """格式化webhook消息，符合KoiShi机器人的模板格式"""
        if not results:
            return {
                'title': 'Unity代码审查',
                'summary': '没有检测到C#代码变更',
                'details': '本次提交未包含需要审查的C#文件'
            }
        
        # 构建摘要
        total_files = len(results)
        new_files = sum(1 for r in results if r.get('file_status') == 'new')
        modified_files = sum(1 for r in results if r.get('file_status') == 'modified')
        
        summary = f"共审查 {total_files} 个文件（新增: {new_files}, 修改: {modified_files}）"
        
        # 构建详细信息
        details_parts = []
        for idx, result in enumerate(results, 1):
            if 'error' in result:
                details_parts.append(f"[{idx}] {result['file_path']}\n错误: {result['error']}")
                continue
            
            file_detail = f"""[{idx}] {result['file_path']} ({result['file_status']})

📊 第一轮-代码质量评估:
{result['round1_quality'][:300]}...

🎮 第二轮-Unity最佳实践:
{result['round2_unity'][:300]}...

✅ 综合评估与建议:
{result['final_review'][:500]}...
"""
            details_parts.append(file_detail)
        
        details = "\n\n" + "="*50 + "\n\n".join(details_parts)
        
        return {
            'title': 'Unity代码审查报告',
            'summary': summary,
            'details': details,
            'repo': os.getenv('GITHUB_REPOSITORY', 'Unknown'),
            'commit': os.getenv('GITHUB_SHA', 'Unknown')[:7]
        }
    
    def send_webhook(self, message: Dict[str, str]):
        """发送webhook到KoiShi机器人平台"""
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                print("✅ Webhook sent successfully")
            else:
                print(f"⚠️ Webhook returned status code: {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"❌ Failed to send webhook: {e}")
    
    def run(self):
        """执行完整的代码审查流程"""
        print("🚀 Starting Unity Code Review...")
        
        # 获取变更的文件
        changed_files = self.get_changed_files()
        
        if not changed_files:
            print("ℹ️ No C# files changed")
            message = self.format_webhook_message([])
            self.send_webhook(message)
            return
        
        print(f"📝 Found {len(changed_files)} changed C# file(s)")
        
        # 对每个文件进行三轮评估
        results = []
        for idx, file_info in enumerate(changed_files, 1):
            print(f"\n[{idx}/{len(changed_files)}] Reviewing: {file_info['path']}")
            
            print("  - Round 1: Code Quality...")
            round1_result = self.review_round_1_quality(file_info)
            
            print("  - Round 2: Unity Best Practices...")
            round2_result = self.review_round_2_unity(file_info)
            
            print("  - Round 3: Comprehensive Review...")
            round3_result = self.review_round_3_comprehensive(
                file_info, round1_result, round2_result
            )
            
            results.append(round3_result)
        
        # 格式化并发送webhook
        print("\n📤 Sending webhook...")
        message = self.format_webhook_message(results)
        self.send_webhook(message)
        
        print("\n✨ Code review completed!")


def main():
    try:
        reviewer = CodeReviewer()
        reviewer.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
