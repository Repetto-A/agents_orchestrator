from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseAgent(ABC):
    """
    Base class for all agents in the system.
    Every agent:
    - has a name
    - has a system prompt (role)
    - can run a task using an LLM
    """

    def __init__(
        self,
        name: str,
        llm,
        system_prompt: str,
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt

    @abstractmethod
    def build_prompt(self, user_input: str, context: Optional[str] = None) -> str:
        """
        Each agent decides how to build its own prompt.
        """
        pass

    def run(self, user_input: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the agent with given input and context.
        """
        prompt = self.build_prompt(user_input, context)

        response_text = self.llm(prompt, system_prompt=self.system_prompt or None)

        return {
            "agent": self.name,
            "response": response_text,
            "output": response_text,
            "data": None,
            "publicUrl": None,
            "downloadUrl": None,
            "meta": {},
        }
