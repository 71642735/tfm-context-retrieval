from pathlib import Path

import docker
import swebench.harness.run_evaluation as swe_run


TASK_ID = "pytest-dev__pytest-5809"
PATCH_PATH = Path("pilot-bm25.patch")
RUN_ID = "pilot-bm25"
MODEL = "gemini-3.5-flash-lite"


def podman_compatible_cleanup(client, container, logger):
    """
    Compatibility adapter for Podman.

    SWE-bench 5.0.2 calls the `docker` CLI directly during cleanup.
    Docker is not available in this environment, so cleanup is performed
    through the Docker SDK, which communicates with Podman's compatible API.
    """
    if not container:
        return

    try:
        logger.info(
            f"Stopping container {container.name} through Docker SDK / Podman..."
        )
        container.stop(timeout=15)
    except Exception as exc:
        logger.warning(f"Could not stop container normally: {exc}")

        try:
            container.kill()
        except Exception as kill_exc:
            logger.warning(f"Could not kill container: {kill_exc}")

    try:
        logger.info(
            f"Removing container {container.name} through Docker SDK / Podman..."
        )
        container.remove(force=True)
    except Exception as exc:
        logger.warning(f"Could not remove container: {exc}")


def run_with_windows_podman_compatibility(
    test_spec,
    pred,
    client,
    run_id,
    timeout,
):
    """
    Run SWE-bench with two infrastructure-only compatibility adaptations:

    1. Force files written by Path.write_text() to use Unix LF endings.
    2. Replace SWE-bench's Docker CLI cleanup with Docker SDK cleanup.

    The SWE-bench evaluation script, tests and grading logic are unchanged.
    """
    original_write_text = Path.write_text
    original_cleanup = swe_run.cleanup_container

    def write_text_lf(self, data, encoding=None, errors=None, newline=None):
        return original_write_text(
            self,
            data,
            encoding=encoding,
            errors=errors,
            newline="\n",
        )

    try:
        Path.write_text = write_text_lf
        swe_run.cleanup_container = podman_compatible_cleanup

        return swe_run.run_instance(
            test_spec=test_spec,
            pred=pred,
            client=client,
            run_id=run_id,
            timeout=timeout,
            rewrite_reports=True,
        )
    finally:
        Path.write_text = original_write_text
        swe_run.cleanup_container = original_cleanup


def main() -> None:
    print(f"Cargando instancia oficial SWE-bench: {TASK_ID}")

    instances = swe_run.load_swebench_dataset(instance_ids=[TASK_ID])
    instance = instances[0]

    print("Construyendo TestSpec...")
    test_spec = swe_run.make_test_spec(instance)

    print(f"Leyendo patch: {PATCH_PATH}")
    patch = PATCH_PATH.read_text(encoding="utf-8")

    pred = {
        "instance_id": TASK_ID,
        "model_name_or_path": MODEL,
        "model_patch": patch,
    }

    print("Conectando con Podman mediante Docker SDK...")
    client = docker.from_env()

    print("Ejecutando evaluación SWE-bench...")
    result = run_with_windows_podman_compatibility(
        test_spec=test_spec,
        pred=pred,
        client=client,
        run_id=RUN_ID,
        timeout=1800,
    )

    print("\n=== RESULTADO ===")
    print(result)


if __name__ == "__main__":
    main()