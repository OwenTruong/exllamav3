import argparse
import subprocess
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description="Build and tag docker image.")
parser.add_argument("tag", nargs="?", default="latest", help="Image tag (default: latest)")
parser.add_argument("org_name", nargs="?", default="", help="Optional DockerHub org/namespace")

def run(cmd, shell=True):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=shell)
    if result.returncode != 0:
        sys.exit(result.returncode)

def build(org_name, repo_name, tag):

    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent.parent.parent

    base_image_name = "exllamav3-base"
    base_container_name = "exllamav3-base-temp-3813"
    mid_image_name = "exllamav3-mid"

    final_image_base = repo_name
    final_image_name = f"{org_name + '/' if org_name else ''}{final_image_base}:{tag}"

    print(f"Final image name: {final_image_name}")

    # Step 1: Build base image
    run(f"docker build -f \"{script_dir}/Dockerfile.start\" -t {base_image_name} \"{root_dir}\"")

    # Step 2: Run container
    run(f"docker run --gpus all --name {base_container_name} -d {base_image_name} tail -f /dev/null")

    # Step 3: Install dependencies inside container
    run(f"docker exec {base_container_name} pip3 install --no-cache-dir packaging torch")
    run(f"docker exec {base_container_name} pip3 install --no-cache-dir -r requirements.txt")
    run(f"docker exec {base_container_name} pip3 install --no-cache-dir -r requirements_examples.txt")

    run(f"docker exec {base_container_name} pip3 install --no-cache-dir .")

    # Step 4: Commit container to mid image
    run(f"docker commit {base_container_name} {mid_image_name}")

    # Step 5: Cleanup base container
    run(f"docker stop {base_container_name}")
    run(f"docker rm {base_container_name}")
    run(f"docker image rm {base_image_name}")

    # Step 6: Build final image
    run(f"docker build -f \"{script_dir}/Dockerfile.end\" -t {final_image_name} \"{root_dir}\"")

    # Step 7: Remove intermediate image
    run(f"docker image rm {mid_image_name}")

if __name__ == "__main__":
    args = parser.parse_args()
    build(args.org_name, 'exllamav3', args.tag)
