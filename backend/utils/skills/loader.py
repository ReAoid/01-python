"""
Skill 加载器
负责加载和解析 skill 定义文件
"""

import os
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field
import yaml

logger = logging.getLogger(__name__)

# Skill 目录
SKILLS_DIR = os.path.dirname(__file__)


@dataclass
class SkillConfig:
    """Skill 配置"""
    name: str
    description: str
    version: str = "1.0.0"
    content: str = ""  # SKILL.md 的完整内容
    references: Dict[str, str] = field(default_factory=dict)  # 引用文档


class SkillLoader:
    """Skill 加载器"""
    
    def __init__(self, skills_dir: str = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self._cache: Dict[str, SkillConfig] = {}
    
    def load_skill(self, skill_name: str) -> Optional[SkillConfig]:
        """
        加载指定的 skill
        
        Args:
            skill_name: skill 名称（目录名）
            
        Returns:
            SkillConfig 或 None
        """
        if skill_name in self._cache:
            return self._cache[skill_name]
        
        skill_path = os.path.join(self.skills_dir, skill_name)
        skill_file = os.path.join(skill_path, "SKILL.md")
        
        if not os.path.exists(skill_file):
            logger.warning(f"Skill 文件不存在: {skill_file}")
            return None
        
        try:
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 frontmatter
            config = self._parse_frontmatter(content)
            config.content = content
            
            # 加载引用文档
            refs_dir = os.path.join(skill_path, "references")
            if os.path.exists(refs_dir):
                for ref_file in os.listdir(refs_dir):
                    if ref_file.endswith('.md'):
                        ref_path = os.path.join(refs_dir, ref_file)
                        with open(ref_path, 'r', encoding='utf-8') as f:
                            config.references[ref_file] = f.read()
            
            self._cache[skill_name] = config
            logger.info(f"加载 Skill: {skill_name}")
            return config
            
        except Exception as e:
            logger.error(f"加载 Skill 失败 {skill_name}: {e}")
            return None
    
    def _parse_frontmatter(self, content: str) -> SkillConfig:
        """解析 YAML frontmatter"""
        if not content.startswith('---'):
            return SkillConfig(name="unknown", description="")
        
        try:
            # 找到第二个 ---
            end_idx = content.find('---', 3)
            if end_idx == -1:
                return SkillConfig(name="unknown", description="")
            
            frontmatter = content[3:end_idx].strip()
            data = yaml.safe_load(frontmatter)
            
            return SkillConfig(
                name=data.get('name', 'unknown'),
                description=data.get('description', ''),
                version=data.get('version', '1.0.0')
            )
        except Exception as e:
            logger.warning(f"解析 frontmatter 失败: {e}")
            return SkillConfig(name="unknown", description="")
    
    def list_skills(self) -> List[str]:
        """列出所有可用的 skill"""
        skills = []
        for item in os.listdir(self.skills_dir):
            item_path = os.path.join(self.skills_dir, item)
            if os.path.isdir(item_path):
                skill_file = os.path.join(item_path, "SKILL.md")
                if os.path.exists(skill_file):
                    skills.append(item)
        return skills
    
    def get_skill_prompt(self, skill_name: str) -> str:
        """
        获取 skill 的系统提示词
        
        将 SKILL.md 内容和引用文档组合成完整的提示词
        """
        skill = self.load_skill(skill_name)
        if not skill:
            return ""
        
        prompt_parts = [skill.content]
        
        # 添加引用文档
        if skill.references:
            prompt_parts.append("\n\n## Reference Documents\n")
            for ref_name, ref_content in skill.references.items():
                prompt_parts.append(f"\n### {ref_name}\n{ref_content}")
        
        return "\n".join(prompt_parts)


# 全局单例
_loader_instance: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """获取全局 SkillLoader 单例"""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = SkillLoader()
    return _loader_instance
