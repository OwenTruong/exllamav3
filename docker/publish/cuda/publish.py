import argparse
import os
from pathlib import Path
import importlib.util
import datetime

parser = argparse.ArgumentParser(description="Build, tag, publish docker image.")
parser.add_argument("org_name", help="DockerHub org/namespace; For example, johndoe is the namespace: johndoe/exllamav3:latest")
parser.add_argument("tags", type=str, nargs='*', default=[], help="Specify desired quants")


def import_module(module_name, filepath):
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def publish(org_name, tags):
    script_dir = Path(__file__).resolve().parent
    docker_dir = script_dir.parent.parent
    root_dir = docker_dir.parent

    version_filepath = os.path.join(root_dir, "exllamav3", "version.py")
    build_cuda_filepath = os.path.join(docker_dir, "convert", "cuda", "build.py")

    version_module = import_module("exllamav3", version_filepath)
    build_module = import_module("docker", build_cuda_filepath)

    version = version_module.__version__
    build = build_module.build
    run = build_module.run

    repo_name = "exllamav3"
    date = datetime.date.today()
    if len(tags) == 0:
        tags = [f"v{version}--cuda--{date}", "latest"]

    build(org_name, repo_name, tags[0])

    for i, tag in enumerate(tags):
    #   build(org_name, repo_name, tag)
        img_name = f"{ org_name + '/' if org_name else ''}{repo_name}"
        if i != 0:
            run(f"docker tag {img_name}:{tags[0]} {img_name}:{tag}")
        run(f"docker push {img_name}:{tag}")




if __name__ == "__main__":
    args = parser.parse_args()
    publish(args.org_name, args.tags)
