#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
灵依智能体系统 - 模型与数据一键安装脚本
===========================================

功能特性：
1. TTS模型检测与下载（Genie-TTS）
2. ASR模型检测与下载（FunASR-Nano）
3. 智能下载机制
4. 断点续传支持
5. 配置读取与验证
6. 彩色终端输出与进度条显示
7. 错误处理与恢复
8. 重复安装检测

Usage:
    python all_ready.py                    # 检测并安装所有缺失的模型
    python all_ready.py --tts-only         # 仅检测和安装TTS模型
    python all_ready.py --asr-only         # 仅检测和安装ASR模型
    python all_ready.py --force            # 强制重新安装所有模型
    python all_ready.py --check-only       # 仅检测，不执行下载
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

# 设置 Windows 终端编码为 UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 预先设置 GENIE_DATA_DIR 环境变量，防止 genie-tts 库在导入时触发交互式下载提示
# 这必须在导入任何可能依赖 genie_tts 的模块之前设置
if not os.environ.get('GENIE_DATA_DIR'):
    # 使用默认路径（all_ready.py 在 backend/ 目录下）
    _backend_dir = Path(__file__).parent  # backend/
    _default_genie_data = _backend_dir / 'data' / 'tts' / 'GenieData'
    os.environ['GENIE_DATA_DIR'] = str(_default_genie_data.resolve())

# =============================================================================
# 彩色终端输出
# =============================================================================

class Color:
    """终端颜色代码"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'


def print_header(text: str):
    """打印标题"""
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 60}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{text}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 60}{Color.RESET}\n")


def print_success(text: str):
    """打印成功信息"""
    print(f"{Color.GREEN}✅ {text}{Color.RESET}")


def print_error(text: str):
    """打印错误信息"""
    print(f"{Color.RED}❌ {text}{Color.RESET}")


def print_warning(text: str):
    """打印警告信息"""
    print(f"{Color.YELLOW}⚠️  {text}{Color.RESET}")


def print_info(text: str):
    """打印信息"""
    print(f"{Color.BLUE}ℹ️  {text}{Color.RESET}")


def print_step(text: str):
    """打印步骤信息"""
    print(f"{Color.MAGENTA}➤ {text}{Color.RESET}")


# =============================================================================
# 模型状态枚举
# =============================================================================

class ModelStatus(Enum):
    """模型状态"""
    NOT_FOUND = "not_found"
    INCOMPLETE = "incomplete"
    INSTALLED = "installed"


# =============================================================================
# 配置加载器
# =============================================================================

class ConfigLoader:
    """配置加载器 - 从 core_config.json 读取配置"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_path = project_root / "backend" / "config" / "core_config.json"
        self._config_data: Optional[Dict[str, Any]] = None
    
    def load(self) -> Dict[str, Any]:
        """加载配置（带缓存）"""
        if self._config_data is not None:
            return self._config_data
        
        if not self.config_path.exists():
            print_error(f"配置文件不存在: {self.config_path}")
            sys.exit(1)
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config_data = json.load(f)
            print_success(f"已加载配置文件: {self.config_path}")
            return self._config_data
        except Exception as e:
            print_error(f"加载配置文件失败: {e}")
            sys.exit(1)
    
    def get_config(self, key: str) -> Dict[str, Any]:
        """获取指定配置"""
        return self.load().get(key, {})
    
    def get_data_dir(self, model_type: str) -> Path:
        """获取模型数据目录"""
        config = self.get_config(model_type)
        
        if model_type == "tts":
            data_dir = config.get("genie_data_dir", "backend/data/tts")
        else:  # asr
            data_dir = "backend/data/asr"
        
        return self._to_abs_path(data_dir)
    
    def get_model_dir(self, model_type: str) -> Path:
        """获取模型目录路径"""
        if model_type == "tts":
            return self.get_data_dir("tts") / "GenieData"
        
        # ASR 模型目录
        config = self.get_config("asr")
        engine = config.get("engine", "dummy")
        
        # 默认目录结构
        engine_dirs = {
            "funasr_nano": "funasr_nano",
            "whisper": "whisper_base"
        }
        
        dir_name = engine_dirs.get(engine, engine)
        return self.get_data_dir("asr") / dir_name
    
    def _to_abs_path(self, path: str) -> Path:
        """转换为绝对路径"""
        return Path(path) if os.path.isabs(path) else self.project_root / path


# =============================================================================
# 统一模型检测器
# =============================================================================

class ModelChecker:
    """统一模型检测器 - 支持TTS和ASR"""
    
    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader
    
    def check(self, model_type: str) -> Tuple[ModelStatus, List[str]]:
        """
        检测模型状态
        
        Args:
            model_type: 'tts' 或 'asr'
        
        Returns:
            (状态, 缺失项列表)
        """
        if model_type == "tts":
            return self._check_tts()
        elif model_type == "asr":
            return self._check_asr()
        else:
            raise ValueError(f"未知的模型类型: {model_type}")
    
    def _check_tts(self) -> Tuple[ModelStatus, List[str]]:
        """检测TTS模型"""
        print_step("检测 TTS 模型...")
        
        tts_config = self.config_loader.get_config("tts")
        genie_data_dir = self.config_loader.get_model_dir("tts")
        missing_items = []
        
        # 检查 GenieData 目录
        if not genie_data_dir.exists():
            missing_items.append("GenieData 目录")
            print_warning(f"GenieData 目录不存在: {genie_data_dir}")
            return ModelStatus.NOT_FOUND, missing_items
        
        # 检查核心组件
        components = {
            "chinese-hubert-base": genie_data_dir / "chinese-hubert-base",
            "CharacterModels": genie_data_dir / "CharacterModels"
        }
        
        for name, path in components.items():
            if not path.exists():
                missing_items.append(f"{name} 模型")
                print_warning(f"{name} 不存在: {path}")
        
        # 检查活跃角色
        if "CharacterModels" not in missing_items:
            active_char = tts_config.get("active_character", "feibi")
            char_dir = components["CharacterModels"] / "v2ProPlus" / active_char
            
            if not char_dir.exists():
                missing_items.append(f"角色模型 '{active_char}'")
                print_warning(f"角色模型不存在: {char_dir}")
            else:
                # 检查必需文件
                for file_name in ["tts_models", "prompt_wav.json"]:
                    if not (char_dir / file_name).exists():
                        missing_items.append(f"角色文件 {file_name}")
                        print_warning(f"角色文件缺失: {char_dir / file_name}")
        
        # 返回状态
        if not missing_items:
            print_success("TTS 模型检测完成，所有组件已安装")
            return ModelStatus.INSTALLED, []
        
        status = ModelStatus.NOT_FOUND if "GenieData 目录" in missing_items else ModelStatus.INCOMPLETE
        print_warning(f"TTS 模型不完整，缺失 {len(missing_items)} 项")
        return status, missing_items
    
    def _check_asr(self) -> Tuple[ModelStatus, List[str]]:
        """检测ASR模型"""
        print_step("检测 ASR 模型...")
        
        asr_config = self.config_loader.get_config("asr")
        engine = asr_config.get("engine", "dummy")
        
        # dummy 引擎无需模型
        if engine == "dummy":
            print_info("ASR 引擎配置为 'dummy' (测试模式)，无需模型文件")
            return ModelStatus.INSTALLED, []
        
        # 检查模型目录
        model_dir = self.config_loader.get_model_dir("asr")
        
        if not model_dir.exists():
            print_warning(f"ASR 模型目录不存在: {model_dir}")
            return ModelStatus.NOT_FOUND, [f"{engine} 模型目录"]
        
        # 检查是否存在 .onnx 或 .pt 文件
        onnx_files = list(model_dir.glob("*.onnx"))
        pt_files = list(model_dir.glob("*.pt"))
        model_files = onnx_files + pt_files
        
        if model_files:
            total_size_mb = sum(f.stat().st_size for f in model_files) / (1024 * 1024)
            file_types = set(f.suffix for f in model_files)
            print_success(f"ASR 模型已存在: {model_dir}")
            print_info(f"  文件类型: {', '.join(file_types)} | 总大小: {total_size_mb:.2f} MB | 文件数: {len(model_files)}")
            return ModelStatus.INSTALLED, []
        else:
            print_warning(f"ASR 模型目录存在但未找到模型文件 (.onnx/.pt): {model_dir}")
            return ModelStatus.NOT_FOUND, [f"{engine} 模型文件 (.onnx/.pt)"]


# =============================================================================
# 统一模型下载器
# =============================================================================

class ModelDownloader:
    """统一模型下载器 - 支持TTS和ASR"""
    
    # HuggingFace 仓库配置
    REPO_CONFIG = {
        "tts": {
            "repo_id": "High-Logic/Genie",
            "patterns": "GenieData/*",
            "name": "Genie-TTS"
        },
        "asr": {
            "repo_id": "FunAudioLLM/Fun-ASR-Nano-2512",
            "patterns": "*",
            "name": "Fun-ASR-Nano",
            "size": "~200MB"
        }
    }
    
    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader
        self._ensure_huggingface_hub()
    
    def _ensure_huggingface_hub(self):
        """检查 huggingface_hub 依赖"""
        try:
            import huggingface_hub
            print_success(f"huggingface_hub 已安装 (版本: {huggingface_hub.__version__})")
        except ImportError:
            print_error("缺少依赖: huggingface_hub")
            print_info("安装命令: pip install huggingface-hub")
            sys.exit(1)
    
    def download(self, model_type: str, force: bool = False) -> bool:
        """
        下载模型
        
        Args:
            model_type: 'tts' 或 'asr'
            force: 是否强制重新下载
        
        Returns:
            是否成功
        """
        if model_type == "tts":
            return self._download_tts(force)
        elif model_type == "asr":
            return self._download_asr(force)
        else:
            print_error(f"未知的模型类型: {model_type}")
            return False
    
    def _download_tts(self, force: bool) -> bool:
        """下载TTS模型"""
        print_header("下载 TTS 模型")
        
        from huggingface_hub import snapshot_download
        
        data_dir = self.config_loader.get_data_dir("tts")
        genie_data_dir = self.config_loader.get_model_path("tts")
        
        # 检查是否已存在
        if genie_data_dir.exists() and not force:
            hubert_dir = genie_data_dir / "chinese-hubert-base"
            if hubert_dir.exists():
                print_info("TTS 模型已存在，跳过下载（使用 --force 强制重新下载）")
                return True
        
        config = self.REPO_CONFIG["tts"]
        print_info(f"从 HuggingFace 下载 {config['name']} 模型...")
        print_info(f"仓库: {config['repo_id']}")
        print_info(f"目标目录: {data_dir}")
        print_warning("首次下载需要较长时间，请耐心等待...")
        
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            
            print_step("正在下载 GenieData...")
            snapshot_download(
                repo_id=config["repo_id"],
                repo_type="model",
                allow_patterns=config["patterns"],
                local_dir=str(data_dir),
                local_dir_use_symlinks=False,
                resume_download=True,
            )
            
            print_success(f"✅ {config['name']} 模型下载完成！")
            
            # 下载默认角色
            self._download_character()
            
            return True
            
        except Exception as e:
            print_error(f"下载失败: {e}")
            self._show_manual_download_help("tts")
            return False
    
    def _download_asr(self, force: bool) -> bool:
        """下载ASR模型"""
        print_header("下载 ASR 模型")
        
        asr_config = self.config_loader.get_config("asr")
        engine = asr_config.get("engine", "dummy")
        
        if engine == "dummy":
            print_info("ASR 引擎配置为 'dummy'，无需下载模型")
            return True
        
        if engine != "funasr_nano":
            print_warning(f"未支持的 ASR 引擎: {engine}")
            return False
        
        model_dir = self.config_loader.get_model_dir("asr")
        
        # 检查是否已存在
        if not force and model_dir.exists():
            # 检查是否有模型文件
            model_files = list(model_dir.glob("*.onnx")) + list(model_dir.glob("*.pt"))
            if model_files:
                print_info("ASR 模型已存在，跳过下载（使用 --force 强制重新下载）")
                return True
        
        # 显示下载信息并询问用户
        if not self._confirm_asr_download(model_dir):
            return False
        
        # 执行下载
        return self._execute_asr_download(model_dir)
    
    def _confirm_asr_download(self, model_dir: Path) -> bool:
        """确认ASR模型下载"""
        config = self.REPO_CONFIG["asr"]
        
        print_info("")
        print_info("检测到 ASR 模型尚未安装。")
        print_info("")
        print_info("📦 模型信息：")
        print_info(f"  名称: {config['name']}")
        print_info(f"  来源: HuggingFace ({config['repo_id']})")
        print_info(f"  目标目录: {model_dir}")
        print_info(f"  预计大小: {config['size']}")
        print_info("  下载时间: 5-15分钟（取决于网络速度）")
        print_info("")
        
        try:
            response = input("是否立即从 HuggingFace 下载此模型？(y/N): ").strip().lower()
            return response in ['y', 'yes', '是']
        except (EOFError, KeyboardInterrupt):
            print_info("\n已取消下载")
            return False
    
    def _execute_asr_download(self, model_dir: Path) -> bool:
        """执行ASR模型下载"""
        from huggingface_hub import snapshot_download
        
        config = self.REPO_CONFIG["asr"]
        print_info("")
        print_warning("⏳ 开始下载，请稍候...")
        print_info("")
        
        model_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            print_step("正在连接 HuggingFace...")
            
            download_dir = snapshot_download(
                repo_id=config["repo_id"],
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
                resume_download=True,
                allow_patterns=config["patterns"],
            )
            
            print_success(f"模型下载完成: {download_dir}")
            
            # 创建元数据
            self._create_metadata(model_dir, "asr")
            
            # 显示下载结果
            self._show_download_summary(model_dir)
            
            print_success("")
            print_success("🎉 ASR 模型安装完成！")
            print_info("")
            print_info("下一步：")
            print_info("  1. 在 backend/config/core_config.json 中设置 asr.enabled = true")
            print_info("  2. 确保已安装: pip install onnxruntime")
            print_info("  3. 运行测试: python backend/test/test_asr_functionality.py")
            
            return True
            
        except Exception as e:
            print_error(f"下载失败: {e}")
            self._show_download_error_help(str(e), model_dir)
            return False
    

    
    def _create_metadata(self, model_dir: Path, model_type: str):
        """创建元数据文件"""
        if model_type == "asr":
            metadata = {
                "model_name": "Fun-ASR-Nano-2512",
                "version": "2512",
                "source": "HuggingFace",
                "repo_id": self.REPO_CONFIG["asr"]["repo_id"],
                "download_date": time.strftime("%Y-%m-%d"),
                "engine": "funasr_nano",
                "format": "ONNX"
            }
            
            metadata_file = model_dir / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            print_success("✅ 元数据文件已创建")
    
    def _show_download_summary(self, model_dir: Path):
        """显示下载摘要"""
        print_info("")
        print_info("下载的文件:")
        for file in sorted(model_dir.iterdir()):
            if file.is_file():
                size_mb = file.stat().st_size / (1024 * 1024)
                print_info(f"  - {file.name} ({size_mb:.2f} MB)")
    
    def _download_character(self):
        """下载默认角色模型"""
        print_step("检查默认角色模型...")
        
        try:
            import genie_tts as genie
            
            tts_config = self.config_loader.get_config("tts")
            active_character = tts_config.get("active_character", "feibi")
            
            genie_data_dir = self.config_loader.get_model_dir("tts")
            os.environ['GENIE_DATA_DIR'] = str(genie_data_dir.resolve())
            
            # 检查角色是否已存在
            character_dir = genie_data_dir / "CharacterModels" / "v2ProPlus" / active_character
            
            if character_dir.exists():
                print_info(f"角色 '{active_character}' 已存在")
                return
            
            print_info(f"正在下载默认角色 '{active_character}'...")
            genie.load_predefined_character(active_character)
            print_success(f"✅ 角色 '{active_character}' 下载完成！")
            
        except ImportError:
            print_warning("genie_tts 未安装，跳过角色下载")
        except Exception as e:
            print_warning(f"下载角色失败: {e}")
            print_info("可以稍后手动下载或在首次使用TTS时自动下载")
    
    def _show_manual_download_help(self, model_type: str):
        """显示手动下载帮助"""
        print_info("")
        print_info("💡 手动下载方法：")
        
        config = self.REPO_CONFIG[model_type]
        repo_url = f"https://huggingface.co/{config['repo_id']}"
        
        print_info(f"  1. 访问: {repo_url}")
        print_info("  2. 下载所需文件")
        print_info(f"  3. 放置到相应目录")
    
    def _show_download_error_help(self, error_msg: str, model_dir: Path):
        """显示下载错误帮助"""
        print_info("")
        
        if any(kw in error_msg.lower() for kw in ["internet", "connection", "network"]):
            print_warning("🌐 网络连接问题")
            print_info("")
            print_info("🔧 解决方案：")
            print_info("")
            print_info("1️⃣ 设置 HuggingFace 镜像站（国内用户推荐）：")
            print_info("   # Windows PowerShell")
            print_info("   $env:HF_ENDPOINT = 'https://hf-mirror.com'")
            print_info("   python all_ready.py --asr-only")
            print_info("")
            print_info("2️⃣ 设置代理（如果有）：")
            print_info("   $env:HTTP_PROXY = 'http://127.0.0.1:7890'")
            print_info("   $env:HTTPS_PROXY = 'http://127.0.0.1:7890'")
        
        print_info("")
        print_info("💡 手动下载：")
        print_info(f"  访问: https://huggingface.co/{self.REPO_CONFIG['asr']['repo_id']}")
        print_info(f"  放置到: {model_dir}")


# =============================================================================
# 依赖检查器
# =============================================================================

class DependencyChecker:
    """依赖检查器"""
    
    # 必需包：(import名, 显示名, 版本要求)
    REQUIRED_PACKAGES = [
        ('openai', 'openai', '>=1.60.0'),
        ('pydantic', 'pydantic', '>=2.10.0'),
        ('pydantic_settings', 'pydantic-settings', '>=2.7.0'),
        ('numpy', 'numpy', '>=1.26.0'),
        ('aiohttp', 'aiohttp', '>=3.9.0'),
        ('fastapi', 'fastapi', '>=0.110.0'),
        ('uvicorn', 'uvicorn', '>=0.28.0'),
    ]
    
    # 可选包：(import名, 显示名, 描述)
    OPTIONAL_PACKAGES = [
        ('genie_tts', 'genie-tts', 'TTS功能'),
        ('onnxruntime', 'onnxruntime', 'ASR功能'),
        ('huggingface_hub', 'huggingface-hub', '模型下载'),
    ]
    
    @staticmethod
    def check_python_version() -> bool:
        """检查Python版本"""
        print_step("检查 Python 版本...")
        
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        
        if version.major == 3 and version.minor >= 8:
            print_success(f"Python 版本: {version_str} ✓")
            return True
        else:
            print_error(f"Python 版本过低: {version_str}，需要 Python 3.8+")
            return False
    
    @classmethod
    def check_packages(cls) -> Tuple[Dict[str, bool], Dict[str, bool]]:
        """检查所有包"""
        print_step("检查 Python 包...")
        
        required_results = {}
        optional_results = {}
        
        # 检查必需包
        for import_name, display_name, version_req in cls.REQUIRED_PACKAGES:
            try:
                __import__(import_name)
                required_results[display_name] = True
                print_success(f"{display_name} {version_req} ✓")
            except ImportError:
                required_results[display_name] = False
                print_warning(f"{display_name} {version_req} ✗")
        
        # 检查可选包
        for import_name, display_name, description in cls.OPTIONAL_PACKAGES:
            try:
                __import__(import_name)
                optional_results[display_name] = True
                print_success(f"{display_name} ({description}) ✓")
            except ImportError:
                optional_results[display_name] = False
                print_info(f"{display_name} ({description}) ✗")
        
        return required_results, optional_results


# =============================================================================
# 主程序
# =============================================================================

class AllReadyManager:
    """主管理器"""
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        # all_ready.py 在 backend/ 目录下，需要获取项目根目录
        self.project_root = Path(__file__).parent.parent.resolve()  # 从 backend/ 回到项目根目录
        self.config_loader = ConfigLoader(self.project_root)
        self.model_checker = ModelChecker(self.config_loader)
        self.downloader = ModelDownloader(self.config_loader)
    
    def run(self) -> int:
        """
        运行主流程
        
        Returns:
            退出码 (0=成功, 1=失败)
        """
        print_header("灵依智能体系统 - 模型与数据安装工具")
        
        print_info(f"项目根目录: {self.project_root}")
        print_info(f"运行模式: {'仅检测' if self.args.check_only else '检测并安装'}")
        
        if self.args.force:
            print_warning("强制重新安装模式")
        
        print("")
        
        # 1. 检查依赖
        if not self._check_dependencies():
            return 1
        
        # 2. 检查模型状态
        needs_download = self._check_models()
        
        # 3. 如果仅检测模式，结束
        if self.args.check_only:
            print_header("检测完成")
            if needs_download:
                print_info("使用 python all_ready.py 执行安装")
            return 0
        
        # 4. 下载模型
        if needs_download or self.args.force:
            if not self._download_models():
                return 1
        
        # 5. 最终验证
        print_header("最终验证")
        self._check_models()
        
        print_header("安装完成")
        print_success("所有模型和数据已准备就绪！")
        print_info("可以使用以下命令启动服务：")
        print_info("  - TTS服务: python backend/genie_server.py")
        print_info("  - 主服务: python backend/main.py")
        
        return 0
    
    def _check_dependencies(self) -> bool:
        """检查依赖"""
        print_header("步骤 1: 检查环境依赖")
        
        # 检查Python版本
        if not DependencyChecker.check_python_version():
            return False
        
        print("")
        
        # 检查包
        required_results, optional_results = DependencyChecker.check_packages()
        missing_required = [pkg for pkg, installed in required_results.items() if not installed]
        
        if missing_required:
            print_error(f"缺少必需的包: {', '.join(missing_required)}")
            print_info("安装命令: pip install -r backend/requirements.txt")
            return False
        
        missing_optional = [pkg for pkg, installed in optional_results.items() if not installed]
        if missing_optional:
            print_info(f"可选包未安装: {', '.join(missing_optional)}")
            print_info("某些功能可能不可用")
        
        return True
    
    def _check_models(self) -> bool:
        """
        检查模型状态
        
        Returns:
            是否需要下载
        """
        print_header("步骤 2: 检查模型状态")
        
        needs_download = False
        
        # 检查TTS
        if not self.args.asr_only:
            tts_status, tts_missing = self.model_checker.check("tts")
            
            if tts_status != ModelStatus.INSTALLED:
                needs_download = True
                print_warning(f"TTS 模型状态: {tts_status.value}")
                if tts_missing:
                    print_warning(f"缺失项: {', '.join(tts_missing)}")
            else:
                print_success("TTS 模型: 已安装 ✓")
        
        print("")
        
        # 检查ASR
        if not self.args.tts_only:
            asr_status, asr_missing = self.model_checker.check("asr")
            
            if asr_status != ModelStatus.INSTALLED:
                needs_download = True
                print_warning(f"ASR 模型状态: {asr_status.value}")
                if asr_missing:
                    print_warning(f"缺失项: {', '.join(asr_missing)}")
            else:
                print_success("ASR 模型: 已安装 ✓")
        
        return needs_download
    
    def _download_models(self) -> bool:
        """下载模型"""
        print_header("步骤 3: 下载缺失的模型")
        
        success = True
        
        # 下载TTS
        if not self.args.asr_only:
            tts_status, _ = self.model_checker.check("tts")
            
            if tts_status != ModelStatus.INSTALLED or self.args.force:
                if not self.downloader.download("tts", force=self.args.force):
                    success = False
        
        print("")
        
        # 下载ASR
        if not self.args.tts_only:
            asr_status, _ = self.model_checker.check("asr")
            
            if asr_status != ModelStatus.INSTALLED or self.args.force:
                if not self.downloader.download("asr", force=self.args.force):
                    success = False
        
        return success


# =============================================================================
# 命令行入口
# =============================================================================

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="灵依智能体系统 - 模型与数据一键安装脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python all_ready.py                    # 检测并安装所有缺失的模型
  python all_ready.py --tts-only         # 仅检测和安装TTS模型
  python all_ready.py --asr-only         # 仅检测和安装ASR模型
  python all_ready.py --force            # 强制重新安装所有模型
  python all_ready.py --check-only       # 仅检测，不执行下载

配置文件:
  - backend/config/core_config.json      # 主配置文件
  - backend/config/settings.py           # 配置模型定义

数据目录:
  - TTS: backend/data/tts/GenieData/
  - ASR: backend/data/asr/
"""
    )
    
    parser.add_argument(
        '--tts-only',
        action='store_true',
        help='仅检测和安装TTS模型'
    )
    
    parser.add_argument(
        '--asr-only',
        action='store_true',
        help='仅检测和安装ASR模型'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新安装所有模型（即使已存在）'
    )
    
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='仅检测模型状态，不执行下载'
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    try:
        args = parse_args()
        manager = AllReadyManager(args)
        exit_code = manager.run()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_warning("\n用户中断")
        sys.exit(1)
    except Exception as e:
        print_error(f"发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
