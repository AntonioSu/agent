#!/usr/bin/env python3
"""
DeepSeek API 兼容性修复
使用 monkey patching 自动修复角色问题
"""


import logging
from typing import Dict, List, Any
from unittest.mock import patch
logger = logging.getLogger(__name__)

def fix_messages_for_deepseek(messages):
    """
    修复消息中的角色问题
    将 'developer' 角色转换为 'system' 角色
    """
    fixed_messages = []
    
    for message in messages:
        # 处理不同类型的消息对象
        if hasattr(message, 'model_dump'):
            # Pydantic 对象
            message_dict = message.model_dump()
        elif hasattr(message, 'dict'):
            # 其他对象的 dict 方法
            message_dict = message.dict()
        elif isinstance(message, dict):
            # 已经是字典
            message_dict = message.copy()
        else:
            # 尝试转换为字典
            message_dict = {
                'role': getattr(message, 'role', 'user'),
                'content': getattr(message, 'content', str(message))
            }
        
        # 修复不支持的角色
        if message_dict.get('role') == 'developer':
            message_dict['role'] = 'system'
            logger.debug("DeepSeek Fix: 将 developer 角色转换为 system 角色")
        
        fixed_messages.append(message_dict)
    
    return fixed_messages

def apply_deepseek_compatibility_patch():
    """
    应用 DeepSeek 兼容性补丁
    """
    try:
        import openai.resources.chat.completions.completions as completions_module
        
        # 保存原始方法
        original_create = completions_module.Completions.create
        
        def patched_create(self, **kwargs):
            """修补后的 create 方法"""
            if 'messages' in kwargs:
                # 修复消息格式
                kwargs['messages'] = fix_messages_for_deepseek(kwargs['messages'])
                
                # 移除可能导致问题的参数
                problematic_params = [
                    'frequency_penalty', 'presence_penalty', 'logit_bias', 
                    'logprobs', 'top_logprobs', 'suffix', 'user', 'tools', 
                    'tool_choice', 'response_format'
                ]
                
                for param in problematic_params:
                    if param in kwargs and kwargs[param] is None:
                        del kwargs[param]
            
            # 调用原始方法
            return original_create(self, **kwargs)
        
        # 应用补丁
        completions_module.Completions.create = patched_create
        logger.info("DeepSeek 兼容性补丁已应用")
        return True
        
    except Exception as e:
        logger.error(f"应用 DeepSeek 兼容性补丁失败: {e}")
        return False

# 自动应用补丁
if apply_deepseek_compatibility_patch():
    logger.info("DeepSeek 兼容性修复已启用")
else:
    logger.warning("DeepSeek 兼容性修复启用失败")
