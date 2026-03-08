#!/usr/bin/env python3
"""
Unity Code Review Tool
三轮评估：代码质量 -> Unity最佳实践 -> 综合评估
支持多线程并发评估，每个文件单独发送 Webhook
"""

import os
import sys
import json
import requests
from typing import List, Dict, Any
from openai import OpenAI
import git
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class CodeReviewer:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.api_base = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
        self.webhook_url = os.getenv('WEBHOOK_URL')
        
        # AI 模型配置
        self.model = os.getenv('AI_MODEL', 'deepseek-chat')
        
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
        
        print(f"🤖 AI 模型: {self.model}")
        print(f"📁 Unity 项目路径: {self.unity_project_path}")
        print(f"🚫 排除目录: {', '.join(self.exclude_dirs)}")
        
        # 线程锁，用于保护 Webhook 发送
        self.webhook_lock = threading.Lock()
        
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
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.3
            )
            result = response.choices[0].message.content
            if not result or len(result) < 50:
                return f"评估失败: API 返回内容过短或为空 (长度: {len(result) if result else 0})"
            return result
        except Exception as e:
            error_detail = f"API调用失败: {type(e).__name__}: {str(e)}"
            print(f"    ⚠️ {error_detail}")
            return f"评估失败: {error_detail}"
    
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
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.3
            )
            result = response.choices[0].message.content
            if not result or len(result) < 50:
                return f"评估失败: API 返回内容过短或为空 (长度: {len(result) if result else 0})"
            return result
        except Exception as e:
            error_detail = f"API调用失败: {type(e).__name__}: {str(e)}"
            print(f"    ⚠️ {error_detail}")
            return f"评估失败: {error_detail}"
    
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
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.3
            )
            
            final_result = response.choices[0].message.content
            
            if not final_result or len(final_result) < 50:
                return {
                    'file_path': file_info['path'],
                    'file_status': file_info['status'],
                    'error': f"API 返回内容过短或为空 (长度: {len(final_result) if final_result else 0})"
                }
            
            return {
                'file_path': file_info['path'],
                'file_status': file_info['status'],
                'round1_quality': round1_result,
                'round2_unity': round2_result,
                'final_review': final_result
            }
        except Exception as e:
            error_detail = f"API调用失败: {type(e).__name__}: {str(e)}"
            print(f"    ⚠️ {error_detail}")
            return {
                'file_path': file_info['path'],
                'file_status': file_info['status'],
                'error': error_detail
            }

    def format_webhook_message(self, file_path: str, file_status: str, 
                              round1_result: str, round2_result: str, 
                              round3_result: str, file_index: int, total_files: int) -> Dict[str, str]:
        """格式化单个文件的 webhook 消息（简化版，避免截断）"""
        
        # 提取关键信息（评分）
        def extract_score(text: str) -> str:
            """提取评分信息"""
            lines = text.split('\n')
            scores = []
            for line in lines[:15]:  # 只看前15行
                if '评分' in line or '得分' in line or '/100' in line:
                    scores.append(line.strip())
            return '\n'.join(scores[:5]) if scores else '评分信息未找到'
        
        # 提取关键问题
        def extract_key_issues(text: str) -> str:
            """提取关键问题（前500字符）"""
            # 查找问题部分
            if 'P0' in text or '必须立即修复' in text:
                start = text.find('P0')
                if start != -1:
                    return text[start:start+500] + '...'
            
            # 否则返回前500字符
            return text[:500] + '...' if len(text) > 500 else text
        
        # 构建简化消息
        title = f"📄 文件 [{file_index}/{total_files}]: {os.path.basename(file_path)}"
        
        summary = f"""状态: {file_status}
路径: {file_path}

📊 评分摘要:
{extract_score(round3_result)}

⚠️ 关键问题:
{extract_key_issues(round3_result)}

💡 提示: 完整报告请查看 GitHub Actions 日志"""
        
        return {
            'title': title,
            'summary': summary,
            'file_path': file_path,
            'file_status': file_status,
            'file_index': str(file_index),
            'total_files': str(total_files),
            'repo': os.getenv('GITHUB_REPOSITORY', 'Unknown'),
            'commit': os.getenv('GITHUB_SHA', 'Unknown')[:7]
        }
    
    def send_webhook(self, message: Dict[str, str]):
        """发送 webhook 到 KoiShi 机器人平台（线程安全）"""
        with self.webhook_lock:
            try:
                response = requests.post(
                    self.webhook_url,
                    json=message,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if response.status_code == 200:
                    print(f"  ✅ Webhook sent: {message.get('title', 'Unknown')}")
                else:
                    print(f"  ⚠️ Webhook returned status code: {response.status_code}")
            except Exception as e:
                print(f"  ❌ Failed to send webhook: {e}")
    
    def review_single_file(self, file_info: Dict[str, Any], file_index: int, total_files: int) -> Dict[str, Any]:
        """评估单个文件（三轮评估）"""
        file_path = file_info['path']
        print(f"\n[{file_index}/{total_files}] 🔍 Reviewing: {file_path}")
        
        try:
            # 第一轮：代码质量
            print(f"  - Round 1: Code Quality...")
            round1_result = self.review_round_1_quality(file_info)
            
            # 检查第一轮是否失败
            if round1_result.startswith("评估失败"):
                raise Exception(f"Round 1 failed: {round1_result}")
            
            # 第二轮：Unity 最佳实践
            print(f"  - Round 2: Unity Best Practices...")
            round2_result = self.review_round_2_unity(file_info)
            
            # 检查第二轮是否失败
            if round2_result.startswith("评估失败"):
                raise Exception(f"Round 2 failed: {round2_result}")
            
            # 第三轮：综合评估
            print(f"  - Round 3: Comprehensive Review...")
            round3_result = self.review_round_3_comprehensive(
                file_info, round1_result, round2_result
            )
            
            # 检查第三轮是否失败
            if isinstance(round3_result, dict) and 'error' in round3_result:
                raise Exception(f"Round 3 failed: {round3_result['error']}")
            
            # 提取最终评估结果
            if isinstance(round3_result, dict):
                final_review = round3_result.get('final_review', '')
                if not final_review:
                    raise Exception("Round 3 returned empty final_review")
            else:
                final_review = str(round3_result)
            
            # 立即发送 Webhook（每个文件单独发送）
            print(f"  - Sending webhook...")
            message = self.format_webhook_message(
                file_path=file_info['path'],
                file_status=file_info['status'],
                round1_result=round1_result,
                round2_result=round2_result,
                round3_result=final_review,
                file_index=file_index,
                total_files=total_files
            )
            self.send_webhook(message)
            
            print(f"  ✅ Review completed successfully")
            return round3_result
            
        except Exception as e:
            error_msg = f"评估失败: {str(e)}"
            print(f"  ❌ {error_msg}")
            
            # 打印详细的错误堆栈（用于调试）
            import traceback
            print(f"  📋 Error details:")
            traceback.print_exc()
            
            # 发送错误通知
            error_message = {
                'title': f"❌ 文件 [{file_index}/{total_files}]: {os.path.basename(file_path)}",
                'summary': f"评估失败\n路径: {file_path}\n错误: {error_msg}",
                'file_path': file_path,
                'error': error_msg
            }
            self.send_webhook(error_message)
            
            return {
                'file_path': file_path,
                'file_status': file_info['status'],
                'error': error_msg
            }
    
    def run(self):
        """执行完整的代码审查流程（多线程版本）"""
        print("🚀 Starting Unity Code Review...")
        
        # 获取变更的文件
        changed_files = self.get_changed_files()
        
        if not changed_files:
            print("ℹ️ No C# files changed")
            # 发送无变更通知
            message = {
                'title': '✅ Unity代码审查',
                'summary': '没有检测到C#代码变更',
                'repo': os.getenv('GITHUB_REPOSITORY', 'Unknown'),
                'commit': os.getenv('GITHUB_SHA', 'Unknown')[:7]
            }
            self.send_webhook(message)
            return
        
        total_files = len(changed_files)
        print(f"📝 Found {total_files} changed C# file(s)")
        
        # 发送开始通知
        start_message = {
            'title': '🚀 Unity代码审查开始',
            'summary': f'共 {total_files} 个文件待审查\n仓库: {os.getenv("GITHUB_REPOSITORY", "Unknown")}\n提交: {os.getenv("GITHUB_SHA", "Unknown")[:7]}',
            'total_files': str(total_files)
        }
        self.send_webhook(start_message)
        
        # 使用线程池并发评估（最多4个线程）
        max_workers = min(4, total_files)
        print(f"⚡ Using {max_workers} threads for parallel review")
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_file = {
                executor.submit(self.review_single_file, file_info, idx, total_files): file_info
                for idx, file_info in enumerate(changed_files, 1)
            }
            
            # 等待所有任务完成
            for future in as_completed(future_to_file):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"❌ Thread execution error: {e}")
        
        # 发送完成通知
        success_count = sum(1 for r in results if 'error' not in r)
        error_count = len(results) - success_count
        
        completion_message = {
            'title': '✨ Unity代码审查完成',
            'summary': f'总计: {total_files} 个文件\n成功: {success_count} 个\n失败: {error_count} 个\n\n详细报告已分别发送',
            'repo': os.getenv('GITHUB_REPOSITORY', 'Unknown'),
            'commit': os.getenv('GITHUB_SHA', 'Unknown')[:7]
        }
        self.send_webhook(completion_message)
        
        print(f"\n✨ Code review completed!")
        print(f"   Success: {success_count}/{total_files}")
        print(f"   Failed: {error_count}/{total_files}")


def main():
    try:
        reviewer = CodeReviewer()
        reviewer.run()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
