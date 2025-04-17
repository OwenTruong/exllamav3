## EXL3 conversion script for docker

See [non-docker convert doc](/doc/convert.md) first.

---

### Prerequisites

Dependencies
* Make sure you have installed [Nvidia CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit) for your OS.
* Docker Desktop / Engine installed and running.


Note
* You may need to add the following line to the Docker `daemon.json` config. Path in Linux is `/etc/docker/daemon.json`. For Windows, it is located in the settings page for Docker Desktop.
```json
{
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    },
    "default-runtime": "nvidia", // optional to set default-runtime to nvidia
}
```

---

### Building
Make sure you are at the root directory of the repository, then run the below.
```bash
python ./docker/convert/cuda/build.py
```

#### Alternative to building
Building can takes a while and may require more storage for storing the intermediary images mid-building.

Because of that, images are also available on [Docker Hub](https://hub.docker.com/repository/docker/owentruong/exllamav3).

To use an image from Docker Hub, replace `exllamav3` image in the create step below with the name and tag of the image on Docker Hub. For example:
```bash
docker create \
  ... \
  johndoe/exllamav3:preview-4-17-25--cuda12.8.1
```

---

### Creating
Next, we create the container so that we can reuse it. Replace all instances of `/path/to/host/dir` with the root directory where you store all of your llm files on your host machine.

Note that the `-v` option allows us to map the host's directory path to the container's directory path (i.e. `-v /path/to/host/dir:/path/to/container/dir`). 

The path provided for `/path/of/container/dir` should be an absolute path, while `/path/of/host/dir` can be absolute or relative. It is recommended to provide the same path for both `/path/to/host/dir` and `/path/to/container/dir` to avoid confusion when trying to provide paths for `--in_dir`, `--out_dir` and `--work_dir`. However, if the path to all of the directories are too long, you may find it more useful to use relative path for `/path/to/container/dir`.

```bash
docker create \
  --name exl3-container \
  --runtime=nvidia \
  --gpus all \
  -v /path/to/host/dir:/path/to/container/dir \
  exllamav3

docker start exl3-container
```

Example:
```bash
docker create \
  --name exl3-container \
  --gpus all \
  -v /mnt/llm:/mnt/llm \
  exllamav3
  
docker start exl3-container
```

Note, if you need a separate path for cache (i.e. work directory), add another path for the cache directory.
```bash
docker create \
  --name exl3-container \
  --gpus all \
  -v /path/to/host/dir:/path/to/container/dir \
  -v /path/to/host/cache/dir:/path/to/container/cache/dir \
  exllamav3

docker start exl3-container
```

---

### Running
To run the container, provide `<arg>` at the end. Note that it might hang for a few seconds before it outputs anything.
```bash
docker exec exl3-container python3 convert.py <arg>
```

Example:
```bash
docker exec exl3-container python3 convert.py \
  --in_dir /mnt/llm/full_models/Llama-3.2-1B-Instruct \
  --work_dir /mnt/llm/work \
  --out_dir /mnt/llm/quants/Llama-3.2-1B-Instruct/4.0 \
  --bits 4.0
```

---

### Closing Thoughts
It is possible to run scripts other than `convert.py`, like the `/examples/`, but `/eval/` may be difficult due to conflicting requirements in `requirements_eval.txt`.

To publish an image, username/organization plus tag will be needed. For example:
```bash
# Make sure to login with "docker login" first!
docker tag exllamav3 johndoe/exllamav3:latest
docker tag exllamav3 johndoe/exllamav3:preview-4-17-25--cuda12.8.1
docker push johndoe/exllamav3:latest
docker push johndoe/exllamav3:preview-4-17-25--cuda12.8.1
```

#### Full Windows Example
```powershell
python ./docker/convert/cuda/build.py

docker create \
  --name exl3-container \
  --gpus all \
  -v D:\Applications\@Docker\exllamav3\data:/data \ # relative host path
  exllamav3
  
docker start exl3-container

docker exec exl3-container python3 convert.py \
  --in_dir /data/full_models/Llama-3.2-1B-Instruct \
  --work_dir /data/cache \
  --out_dir /data/quants/Llama-3.2-1B-Instruct/4.0 \
  --bits 4.0
```