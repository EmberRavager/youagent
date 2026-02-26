import json
from typing import Any

from .agents import AgentProfile
from .llm import ChatClient
from .memory import SessionMemory
from .tools import ToolRegistry


class AgentRuntime:
    def __init__(
        self,
        agent: AgentProfile,
        client: ChatClient,
        tools: ToolRegistry,
        memory: SessionMemory | None = None,
    ):
        self.agent = agent
        self.client = client
        self.tools = tools
        self.memory = memory
        self.messages: list[dict[str, Any]] = self._load_messages()

    def _load_messages(self) -> list[dict[str, Any]]:
        if self.memory is None:
            return [{"role": "system", "content": self.agent.system_prompt}]

        loaded = self.memory.load()
        if not loaded:
            return [{"role": "system", "content": self.agent.system_prompt}]

        if loaded[0].get("role") != "system":
            loaded.insert(0, {"role": "system", "content": self.agent.system_prompt})
        else:
            loaded[0]["content"] = self.agent.system_prompt
        return loaded

    def _persist(self) -> None:
        if self.memory is not None:
            self.memory.save(self.messages)

    def ask(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})

        for _ in range(self.agent.max_tool_rounds):
            response = self.client.chat_completion(self.messages, self.tools.schemas())
            message = response["choices"][0]["message"]

            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                assistant_text = message.get("content", "")
                self.messages.append({"role": "assistant", "content": assistant_text})
                self._persist()
                return assistant_text

            self.messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )

            for call in tool_calls:
                name = call["function"]["name"]
                raw_args = call["function"].get("arguments", "{}")
                try:
                    parsed_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    parsed_args = {}

                result = self.tools.call(name, parsed_args)
                content = json.dumps(
                    {"ok": result.ok, "content": result.content}, ensure_ascii=True
                )

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": content,
                    }
                )
                self._persist()

        fallback = "Stopped after too many tool rounds. Please narrow the task."
        self.messages.append({"role": "assistant", "content": fallback})
        self._persist()
        return fallback
