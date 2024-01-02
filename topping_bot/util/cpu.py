import traceback
from multiprocessing.shared_memory import SharedMemory

from tqdm import tqdm

from topping_bot.optimize.reader import extract_topping_data, extract_unique_frames, write_toppings


def full_extraction(fp, topping_fp, shared_mem_name, solution, debug=False, verbose=False):
    shared_memory = SharedMemory(name=shared_mem_name)
    toppings = []

    pbar = tqdm(
        bar_format="|{bar:12}| {n_fmt}/{total_fmt}",
        leave=False,
    )

    byte_pbar = pbar.format_meter(**pbar.format_dict).encode(encoding="utf-8")
    shared_memory.buf[: len(byte_pbar)] = byte_pbar

    try:
        for topping in extract_topping_data(extract_unique_frames(fp), debug=debug, verbose=verbose):
            if pbar.update(1):
                byte_pbar = pbar.format_meter(**pbar.format_dict).encode(encoding="utf-8")
                shared_memory.buf[: len(byte_pbar)] = byte_pbar
            if topping is not None:
                toppings.append(topping)
    except ValueError:
        toppings = None

    shared_memory.close()
    pbar.close()

    if toppings is not None:
        write_toppings(toppings, topping_fp, append=True)
        solution.value = len(toppings)


def optimize_cookie(optimizer, cookie, shared_mem_name, solution):
    shared_memory = SharedMemory(name=shared_mem_name)

    pbar = tqdm(
        total=len(optimizer.inventory),
        mininterval=2,
        bar_format="|{bar:12}| {n_fmt}/{total_fmt}",
        leave=False,
    )

    byte_pbar = pbar.format_meter(**pbar.format_dict).encode(encoding="utf-8")
    shared_memory.buf[: len(byte_pbar)] = byte_pbar

    for _ in optimizer.solve(cookie):
        if shared_memory.buf[-1] == 1:
            break
        elif pbar.update(1):
            byte_pbar = pbar.format_meter(**pbar.format_dict).encode(encoding="utf-8")
            shared_memory.buf[: len(byte_pbar)] = byte_pbar

    shared_memory.close()
    pbar.close()

    if optimizer.solution:
        for i, topping in enumerate(optimizer.solution.toppings):
            solution[i] = optimizer.inventory.index(topping)
