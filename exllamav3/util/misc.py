import math
import threading
import time
import torch


lock = threading.RLock()

def synchronized(func):
    def wrapper(*args, **kwargs):
        with lock:
            return func(*args, **kwargs)
    return wrapper

def align_to(value, alignment):
    return int(math.ceil(value / alignment) * alignment)


class Timer:
    """
    Context manager to record duration
    """

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.interval = self.end_time - self.start_time


def cuda_sync_active():
    """
    Calling torch.cuda.synchronize() will create a CUDA context on CUDA:0 even if that device is not being used.
    This function synchronizes only devices actively used by Torch in the current process.
    """
    for device_id in range(torch.cuda.device_count()):
        device = torch.device(f'cuda:{device_id}')
        if torch.cuda.memory_allocated(device) > 0:
            torch.cuda.synchronize(device)


def next_power_of_2(x):
    return 1 if x == 0 else 2**(x - 1).bit_length()
