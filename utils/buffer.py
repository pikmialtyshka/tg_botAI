import asyncio

class Buffer:
    def __init__(self, delay=30):
        self.buffers = {}
        self.tasks = {}
        self.delay = delay

    async def add(self, user_id, text, callback):
        if user_id not in self.buffers:
            self.buffers[user_id] = []

        self.buffers[user_id].append(text)

        if user_id not in self.tasks:
            self.tasks[user_id] = asyncio.create_task(
                self.wait(user_id, callback)
            )

    async def wait(self, user_id, callback):
        await asyncio.sleep(self.delay)
        messages = self.buffers[user_id]
        await callback(user_id, messages)
        self.buffers[user_id] = []
        del self.tasks[user_id]