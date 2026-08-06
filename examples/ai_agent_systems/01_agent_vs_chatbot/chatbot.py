from __future__ import annotations


class RuleBasedChatbot:
    """A chatbot returns one reply for one input and does not act on the world."""

    def reply(self, message: str) -> str:
        normalized = message.lower()
        if "agent" in normalized:
            return "Agent 通常会规划、调用工具、保存状态并处理失败。"
        if "chatbot" in normalized:
            return "Chatbot 通常只负责根据输入生成回复。"
        return "我可以回答问题，但不会主动调用工具或执行多步任务。"


if __name__ == "__main__":
    bot = RuleBasedChatbot()
    print(bot.reply("Agent 和 chatbot 有什么区别？"))
