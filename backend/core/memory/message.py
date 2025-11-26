from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel

# 定义消息角色的类型，限制其取值
MessageRole = Literal["user", "assistant", "system", "tool"]

class Message(BaseModel):
    """消息类"""
    
    content: str
    role: MessageRole
    timestamp: datetime = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Optional: name, tool_calls, tool_call_id for OpenAI compatibility in tool usage
    name: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None

    def __init__(self, content: str, role: MessageRole, **kwargs):
        super().__init__(
            content=content,
            role=role,
            timestamp=kwargs.get('timestamp', datetime.now()),
            metadata=kwargs.get('metadata', {}),
            name=kwargs.get('name'),
            tool_calls=kwargs.get('tool_calls'),
            tool_call_id=kwargs.get('tool_call_id')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（OpenAI API格式）"""
        msg = {
            "role": self.role,
            "content": self.content
        }
        if self.name:
            msg["name"] = self.name
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg
    
    def __str__(self) -> str:
        return f"[{self.role}] {self.content}"

class SystemMessage(Message):
    def __init__(self, content: str, **kwargs):
        super().__init__(content=content, role="system", **kwargs)

class UserMessage(Message):
    def __init__(self, content: str, **kwargs):
        super().__init__(content=content, role="user", **kwargs)

class AssistantMessage(Message):
    def __init__(self, content: str, **kwargs):
        super().__init__(content=content, role="assistant", **kwargs)

class ToolMessage(Message):
    def __init__(self, content: str, tool_call_id: str, **kwargs):
        super().__init__(content=content, role="tool", tool_call_id=tool_call_id, **kwargs)
