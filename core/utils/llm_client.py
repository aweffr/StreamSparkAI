import json
import logging
import requests
from django.conf import settings
from enum import Enum, auto

logger = logging.getLogger(__name__)

def trim_multiple_line_indent(text):
    """
    移除多行文本中共同的前导空格，同时保留整体缩进结构
    
    Args:
        text (str): 需要处理的多行文本
        
    Returns:
        str: 处理后的文本，保留相对缩进
    """
    if not text:
        return ""
    
    # 分割成行并移除头尾空行
    lines = text.strip().split('\n')
    
    # 找出所有非空行的前导空格的最小数量
    min_indent = None
    for line in lines:
        # 跳过空行
        stripped = line.lstrip()
        if not stripped:
            continue
        
        # 计算前导空格数量
        indent = len(line) - len(stripped)
        if min_indent is None or indent < min_indent:
            min_indent = indent
    
    # 如果没有找到最小缩进（如全是空行），返回原文
    if min_indent is None:
        return text.strip()
    
    # 移除每行开头的共同缩进
    result = []
    for line in lines:
        if line.strip():  # 非空行
            result.append(line[min_indent:] if len(line) >= min_indent else line)
        else:  # 空行保留
            result.append("")
    
    # 重新组合成文本
    return '\n'.join(result)

class SummaryType(Enum):
    """枚举不同类型的总结模板"""
    GENERAL = auto()          # 一般性总结
    GENERAL_DETAIL = auto()   # 详细版总结
    KEY_POINTS = auto()       # 关键点提取
    MEETING_MINUTES = auto()  # 会议纪要格式
    INTERVIEW = auto()        # 采访总结
    QA = auto()               # 问答提取

def get_prompt_template(summary_type):
    """根据总结类型获取提示词模板"""
    templates = {
        SummaryType.GENERAL: trim_multiple_line_indent("""
            请总结以下转录文本的主要内容，使用简明的语言，并保持第三人称客观视角。
            
            {context_info}
            
            转录文本:
            {text}
            """),
            
        SummaryType.GENERAL_DETAIL: trim_multiple_line_indent("""
            请对以下转录文本进行详细总结，包括关键讨论点、重要决定和主要观点。使用第三人称客观视角，保持准确性，并提供比一般总结更丰富的信息和细节。
            
            请记住：
            1. 只总结文本中实际存在的内容，不要添加任何不在原文中的信息
            2. 如果内容有模糊不清或不确定的部分，请明确指出
            3. 保持总结与原文的一致性，避免任何形式的夸大或推测
            
            {context_info}
            
            转录文本:
            {text}
            """),
            
        SummaryType.KEY_POINTS: trim_multiple_line_indent("""
            请从以下转录文本中提取5-10个关键点，以要点形式列出，并对每个关键点做简短解释。
            
            {context_info}
            
            转录文本:
            {text}
            """),
            
        SummaryType.MEETING_MINUTES: trim_multiple_line_indent("""
            请将以下会议转录整理为标准会议纪要格式，包含以下部分：
            1. 会议主题
            2. 与会者（从转录中推断）
            3. 讨论的主要议题
            4. 决定的事项
            5. 后续行动
            
            {context_info}
            
            转录文本:
            {text}
            """),
            
        SummaryType.INTERVIEW: trim_multiple_line_indent("""
            请将以下采访转录总结为一篇文章，包含：
            1. 采访主题
            2. 主要观点
            3. 值得关注的引述（使用引号标注）
            4. 结论
            
            {context_info}
            
            转录文本:
            {text}
            """),
            
        SummaryType.QA: trim_multiple_line_indent("""
            请从以下转录文本中提取所有问题和回答，并按以下格式整理：
            
            问题1: [问题内容]
            回答1: [回答内容]
            
            问题2: [问题内容]
            回答2: [回答内容]
            
            {context_info}
            
            转录文本:
            {text}
            """)
    }
    
    return templates.get(summary_type, templates[SummaryType.GENERAL])

class LLMClient:
    """与LLM API交互的客户端基类"""
    
    @staticmethod
    def get_client(provider="openai"):
        """工厂方法：根据提供商返回对应的客户端实例"""
        if provider.lower() == "openai":
            return OpenAIClient()
        elif provider.lower() == "alibaba":
            return AlibabaClient()
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")

    def summarize(self, text, summary_type=SummaryType.GENERAL, context_info=""):
        """使用LLM总结文本内容"""
        raise NotImplementedError("子类必须实现此方法")
    
    def health_check(self):
        """
        发送测试请求以检查LLM API是否正常工作
        
        Returns:
            tuple: (成功标志, 响应内容)
        """
        try:
            # 发送简单的测试提问
            test_prompt = "你好!你是什么模型?"
            logger.info(f"发送健康检查请求: '{test_prompt}'")
            
            # 直接实现健康检查，子类可以重写此方法
            response = self._send_health_check_request(test_prompt)
            
            if response and isinstance(response, str) and response.strip():
                logger.info(f"健康检查成功，模型响应: {response[:100]}...")
                return True, response
            else:
                logger.warning("健康检查失败: 未收到有效响应")
                return False, "未收到有效响应"
                
        except Exception as e:
            logger.exception(f"健康检查失败: {str(e)}")
            return False, f"发生错误: {str(e)}"
    
    def _send_health_check_request(self, prompt):
        """
        发送健康检查请求，子类需要实现此方法
        
        Args:
            prompt (str): 测试提示文本
            
        Returns:
            str: 模型响应文本
        """
        raise NotImplementedError("子类必须实现此方法")


class OpenAIClient(LLMClient):
    """OpenAI API客户端"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not self.api_key:
            raise ValueError("设置中未找到OpenAI API密钥")
        
        self.api_base = getattr(settings, 'OPENAI_API_BASE', "https://api.openai.com/v1")
        self.model = getattr(settings, 'OPENAI_MODEL', "gpt-4o")
    
    @classmethod
    def _send_request(cls, api_key, api_base, model, messages, temperature=0.3):
        """
        发送请求到OpenAI API
        
        Args:
            api_key (str): API密钥
            api_base (str): API基础URL
            model (str): 模型名称
            messages (list): 消息列表
            temperature (float): 温度参数
            
        Returns:
            dict: API响应结果
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        url = f"{api_base}/chat/completions"
        
        # 日志记录请求详情
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        logger.debug(f"OpenAI请求URL: {url}")
        logger.debug(f"OpenAI请求头: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}")
        logger.debug(f"OpenAI请求内容: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        logger.info(f"正在调用OpenAI API，模型: {model}")
        response = requests.post(url, headers=headers, json=data)
        
        # 日志记录响应详情
        logger.debug(f"OpenAI响应状态码: {response.status_code}")
        try:
            response_json = response.json()
            logger.debug(f"OpenAI响应内容: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
        except ValueError:
            logger.debug(f"OpenAI响应内容(非JSON): {response.text[:500]}...")
        
        response.raise_for_status()
        return response.json()
    
    def summarize(self, text, summary_type=SummaryType.GENERAL, context_info=""):
        """使用OpenAI API总结文本内容"""
        prompt = get_prompt_template(summary_type).format(text=text, context_info=context_info)
        
        messages = [
            {"role": "system", "content": "你是一个专业的内容总结助手。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            logger.info("正在调用OpenAI API进行内容总结")
            result = self._send_request(
                self.api_key, 
                self.api_base, 
                self.model, 
                messages
            )
            
            summary = result["choices"][0]["message"]["content"]
            logger.info("成功生成内容总结")
            
            return {
                "summary": summary,
                "raw_response": result
            }
            
        except Exception as e:
            logger.exception(f"调用OpenAI API时出错: {e}")
            return {
                "summary": f"内容总结失败: {str(e)}",
                "raw_response": None
            }
    
    def _send_health_check_request(self, prompt):
        """发送健康检查请求到OpenAI API"""
        try:
            messages = [
                {"role": "system", "content": "你是一个AI助手。"},
                {"role": "user", "content": prompt}
            ]
            
            result = self._send_request(
                self.api_key, 
                self.api_base, 
                self.model, 
                messages
            )
            
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.exception(f"健康检查请求失败: {e}")
            return None


class AlibabaClient(LLMClient):
    """阿里巴巴达摩院API客户端"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'ALIBABA_DASHSCOPE_API_KEY', None)
        if not self.api_key:
            raise ValueError("设置中未找到阿里巴巴DashScope API密钥")
        
        self.model = getattr(settings, 'ALIBABA_LLM_MODEL', "qwen-max")
    
    @classmethod
    def _send_request(cls, api_key, model, messages, temperature=0.3):
        """
        发送请求到阿里巴巴达摩院API
        
        Args:
            api_key (str): API密钥
            model (str): 模型名称
            messages (list): 消息列表
            temperature (float): 温度参数
            
        Returns:
            dict: API响应结果
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "temperature": temperature
            }
        }
        
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        
        # 日志记录请求详情
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        logger.debug(f"阿里巴巴请求URL: {url}")
        logger.debug(f"阿里巴巴请求头: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}")
        logger.debug(f"阿里巴巴请求内容: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        logger.info(f"正在调用阿里巴巴API，模型: {model}")
        response = requests.post(url, headers=headers, json=data)
        
        # 日志记录响应详情
        logger.debug(f"阿里巴巴响应状态码: {response.status_code}")
        try:
            response_json = response.json()
            logger.debug(f"阿里巴巴响应内容: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
        except ValueError:
            logger.debug(f"阿里巴巴响应内容(非JSON): {response.text[:500]}...")
        
        response.raise_for_status()
        return response.json()
        
    def summarize(self, text, summary_type=SummaryType.GENERAL, context_info=""):
        """使用阿里巴巴达摩院API总结文本内容"""
        prompt = get_prompt_template(summary_type).format(text=text, context_info=context_info)
        
        messages = [
            {"role": "system", "content": "你是一个专业的内容总结助手。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            logger.info("正在调用阿里巴巴API进行内容总结")
            result = self._send_request(
                self.api_key,
                self.model,
                messages
            )
            
            summary = result["output"]["text"]
            logger.info("成功生成内容总结")
            
            return {
                "summary": summary,
                "raw_response": result
            }
            
        except Exception as e:
            logger.exception(f"调用阿里巴巴API时出错: {e}")
            return {
                "summary": f"内容总结失败: {str(e)}",
                "raw_response": None
            }
            
    def _send_health_check_request(self, prompt):
        """发送健康检查请求到阿里巴巴达摩院API"""
        try:
            messages = [
                {"role": "system", "content": "你是一个AI助手。"},
                {"role": "user", "content": prompt}
            ]
            
            result = self._send_request(
                self.api_key,
                self.model,
                messages
            )
            
            return result["output"]["text"]
        except Exception as e:
            logger.exception(f"健康检查请求失败: {e}")
            return None