import asyncio

SEMAPHORE = asyncio.Semaphore(1)
RUNNING_CPU_TASK = {}
